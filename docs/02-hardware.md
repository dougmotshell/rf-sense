# 02 — Hardware disponível

<sub>Levantado em 2026-08-23</sub>

---

## Laptop — Dell Latitude 3400

Detectado automaticamente na máquina:

| Item | Valor | Implicação para imageamento |
|---|---|---|
| Wi-Fi | Qualcomm Atheros **QCA6174** 802.11ac `[168c:003e]` | 2x2 MIMO, 2,4 e 5 GHz |
| Driver | `ath10k_pci` / `ath10k_core` | ❌ **sem CSI** → sem fase → sem holografia/SAR |
| Interface | `wlp2s0` | |
| `CONFIG_ATH10K_SPECTRAL` | **`y`** ✅ | bins de FFT do baseband disponíveis (magnitude) |
| `CONFIG_ATH10K_DEBUGFS` | **`y`** ✅ | debugfs montado ✅ |
| Bluetooth | Qualcomm, **HCI/LMP 4.2** | ❌ sem AoA/AoD (5.1) · ❌ sem Channel Sounding (6.0) |
| Ethernet | `enp1s0` ✅ | essencial: mantém internet enquanto o Wi-Fi vira sensor |
| `nmcli` | ✅ funcionando | coleta de RSSI sem root |
| `numpy` | ✅ instalado | reconstrução tomográfica |
| `tcpdump` | ✅ instalado | captura em modo monitor |
| `python3` | ✅ instalado | |
| `matplotlib` | ❌ ausente | opcional — o `reconstruct.py` já renderiza em ASCII e PGM |
| `scipy` | ❌ ausente | não é necessário (solver implementado em numpy puro) |
| `iw` | ❌ **ausente** | necessário só para a fase de BFI — `sudo apt install iw` |
| `sudo` sem senha | não | fases que usam debugfs/monitor vão pedir senha |

### A limitação que define o projeto

**O QCA6174 não expõe fase.** Consequência direta:

- ❌ Holografia de Wi-Fi (Holl & Reinhard) — exige gravação fase-coerente
- ❌ SAR / abertura sintética coerente
- ❌ Qualquer nuvem de pontos 3D
- ✅ Tomografia por atenuação (só precisa de potência)
- ✅ Mapeamento geométrico estilo *Structure from WiFi*
- 🟡 Informação angular via BFI (ângulos comprimidos, não fase bruta)

Não existe workaround por software. É uma limitação de firmware/silício.

### A segunda limitação: um único ponto de vista

O laptop é **estático**. Tomografia precisa de **muitos raios em ângulos diferentes** cruzando
o ambiente. Um receptor parado gera um raio por AP e nada mais.

**Por isso o celular é o componente mais importante do projeto**, não o laptop. Ele é a
diversidade espacial. O laptop é a estação-base e a máquina de processamento.

## Celular — a caracterizar

Preencha esta tabela rodando os testes no seu aparelho:

| Checar | Como | Por que importa |
|---|---|---|
| Versão do Android | Ajustes → Sobre | Wi-Fi RTT exige 9+ (API 28); 802.11az exige 15+ |
| Suporta Wi-Fi RTT? | App **WifiRttScan** (Google, gratuito) | Destrava **distância real** — resolveria o problema de posição |
| Seu AP suporta FTM? | O próprio WifiRttScan marca os APs "RTT capable" | ⚠️ gargalo mais provável; poucos roteadores domésticos suportam |
| Versão do Bluetooth | Ficha do modelo | 5.1+ → AoA · 6.0+ → Channel Sounding |
| Termux instalável? | F-Droid (gratuito) | Permite rodar o coletor direto no celular |
| Tem LiDAR / ARCore? | Depende do modelo | Fornece **ground truth** de graça para validar o mapa RF |

> CSI em celular é, na prática, inviável: exige NIC específica e firmware modificado (Nexmon
> cobre alguns Broadcom/Cypress, mas exige root). Assuma o celular como fonte de
> **RSSI + BLE + (talvez) RTT + IMU**.

## Instalações necessárias (gratuitas, de repositório)

```bash
sudo apt install iw        # só para a fase de BFI
sudo apt install tshark    # opcional, ajuda a dissecar beamforming
pip install matplotlib     # opcional, gráficos bonitos
```

Nada disso é obrigatório para as fases 0–2.

## Se um dia o orçamento deixar de ser zero

Registrado como referência, **fora do escopo atual**:

| Item | ~Custo | O que destrava |
|---|---|---|
| **ESP32-S3** | **US$ 5–8** | **CSI de verdade** — muda o projeto de categoria |
| Intel AX210 M.2 | US$ 25 | CSI 802.11ax até 160 MHz via PicoScenes, banda 6 GHz |
| Raspberry Pi | US$ 40 | Nexmon CSI + nó de captura 24/7 |
| HackRF One | US$ 150 | IQ bruto → **holografia de Wi-Fi fica possível** |

O salto conceitual real está no HackRF: é o único item da lista que devolve a **fase** e,
portanto, o único que destrava imageamento coerente de verdade.
