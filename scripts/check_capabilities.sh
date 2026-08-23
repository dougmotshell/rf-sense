#!/usr/bin/env bash
# check_capabilities.sh — o que o rádio desta máquina permite fazer.
# Não altera nada no sistema. Roda sem root (avisa o que precisaria de root).

# sem 'pipefail': 'grep -q' fecha o pipe cedo e o produtor morre com SIGPIPE,
# o que faria o pipeline inteiro reportar falha indevidamente.
set -u

ok()   { printf '  \033[32m[ ok ]\033[0m %s\n' "$1"; }
nao()  { printf '  \033[31m[ -- ]\033[0m %s\n' "$1"; }
info() { printf '  \033[33m[ ?? ]\033[0m %s\n' "$1"; }
tit()  { printf '\n\033[1m%s\033[0m\n' "$1"; }

echo "rf-sense — diagnóstico de capacidades"
echo "======================================"

tit "Hardware Wi-Fi"
placa=$(lspci -nn 2>/dev/null | grep -iE 'network|wireless' | head -1)
[ -n "$placa" ] && ok "${placa#*: }" || nao "nenhuma placa Wi-Fi PCI encontrada"

mods=$(lsmod 2>/dev/null)
drv=""
for d in ath10k_pci ath9k iwlwifi rtw88_pci mt7921e brcmfmac; do
  if grep -q "^$d " <<<"$mods"; then drv=$d; break; fi
done
[ -n "$drv" ] && ok "driver: $drv" || info "driver não identificado"

case "$drv" in
  ath9k)   ok  "CSI possível — Atheros CSI Tool suporta ath9k" ;;
  iwlwifi) ok  "CSI possível — via PicoScenes (AX200/AX210) ou CSITool (5300)" ;;
  brcmfmac) ok "CSI possível — Nexmon suporta alguns Broadcom/Cypress" ;;
  ath10k_pci) nao "CSI indisponível — ath10k não tem ferramenta de CSI utilizável" ;;
  *)       info "verifique manualmente se há tool de CSI para este driver" ;;
esac

tit "Fase (o que decide se imageamento coerente é possível)"
nao "NICs comuns não expõem fase — holografia/SAR exigem SDR ou CSI calibrado"
echo "       -> este projeto usa tomografia por atenuação, que só precisa de potência"

tit "Spectral scan (bins de FFT do baseband)"
cfg="/boot/config-$(uname -r)"
if [ -r "$cfg" ]; then
  grep -q '^CONFIG_ATH10K_SPECTRAL=y' "$cfg" && ok "CONFIG_ATH10K_SPECTRAL=y" \
    || nao "CONFIG_ATH10K_SPECTRAL não habilitado"
  grep -q '^CONFIG_ATH9K_COMMON_SPECTRAL=y' "$cfg" && ok "CONFIG_ATH9K_COMMON_SPECTRAL=y"
else
  info "config do kernel não legível em $cfg"
fi
mount | grep -q debugfs && ok "debugfs montado" || nao "debugfs não montado"
if [ -r /sys/kernel/debug/ieee80211 ]; then
  found=$(find /sys/kernel/debug/ieee80211 -maxdepth 3 -name 'spectral_scan_ctl' 2>/dev/null | head -1)
  [ -n "$found" ] && ok "controle: $found" || info "spectral_scan_ctl não encontrado"
else
  info "debugfs exige root para inspecionar (rode com sudo para ver mais)"
fi

tit "Modo monitor (necessário para capturar BFI)"
if command -v iw >/dev/null 2>&1; then
  ok "iw instalado"
  iw list 2>/dev/null | grep -A12 'Supported interface modes' | grep -q monitor \
    && ok "modo monitor suportado" || info "não foi possível confirmar (tente com sudo)"
else
  nao "iw ausente — instale com: sudo apt install iw"
fi
command -v tcpdump >/dev/null 2>&1 && ok "tcpdump instalado" || nao "tcpdump ausente"
command -v tshark  >/dev/null 2>&1 && ok "tshark instalado"  || info "tshark ausente (opcional)"

tit "Bluetooth"
if command -v hciconfig >/dev/null 2>&1; then
  ver=$(hciconfig -a 2>/dev/null | grep -m1 'LMP Version' | sed 's/^[[:space:]]*//')
  [ -n "$ver" ] && ok "$ver" || info "adaptador não encontrado"
  case "$ver" in
    *"5.1"*|*"5.2"*|*"5.3"*|*"5.4"*|*"6."*) ok "AoA/AoD possível (BT 5.1+)" ;;
    *) nao "sem AoA/AoD — exige BT 5.1+ ; sem Channel Sounding — exige BT 6.0+" ;;
  esac
else
  info "hciconfig ausente (pacote bluez)"
fi

tit "Software de análise"
for m in numpy matplotlib scipy; do
  python3 -c "import $m" 2>/dev/null && ok "python3-$m" || {
    [ "$m" = numpy ] && nao "python3-numpy AUSENTE (obrigatório)" || info "python3-$m ausente (opcional)"; }
done
command -v nmcli >/dev/null 2>&1 && ok "nmcli (coleta de RSSI sem root)" || nao "nmcli ausente"

tit "Rede cabeada (para manter internet durante capturas)"
cabo=$(ls /sys/class/net | grep -E '^(eth|en)' | head -1)
[ -n "$cabo" ] && ok "interface cabeada: $cabo" || nao "sem interface cabeada — capturas vão derrubar sua conexão"

tit "Veredito"
echo "  Fases 0-3 (survey + tomografia) : viáveis com o que há aqui"
echo "  Fase 4 (BFI)                    : depende de 'iw' e de tráfego 802.11ac na rede"
echo "  Fase 5 (spectral scan)          : depende de root + CONFIG_ATH10K_SPECTRAL"
echo "  Holografia / SAR / CSI          : fora de alcance sem hardware adicional"
echo
