#!/usr/bin/env python3
"""
fontes.py — backends de aquisição, um por modo de modos.py.

Todas as fontes expõem a mesma interface, para que probe.py e os demais não
saibam de qual camada de sinal os números vieram:

    fonte = abrir("free")
    for registro in fonte.amostrar():      # uma varredura / um quadro
        registro["canal"]  # id do canal: BSSID hasheado, subportadora, alvo...
        registro["valor"]  # o número
        registro["unidade"]# "dBm" | "m" | "adim"

Honestidade de engenharia: só `sim`, `nmcli` e `replay` foram exercitados de
verdade. Os outros têm o parser escrito a partir da documentação do protocolo e
NUNCA rodaram contra o hardware — estão marcados com VERIFICADO = False e cada
um oferece `dump_bruto()`, que mostra os bytes crus. Se o parser estiver errado,
o dump continua certo, e é por ele que se começa a depurar.

Sem dependências além de numpy (opcional) e pyserial (opcional, só serial).
"""

import json
import math
import os
import random
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import modos as _modos           # noqa: E402


# --------------------------------------------------------------- transporte

def abrir_bytes(spec, timeout=2.0):
    """
    Abre uma origem de bytes. Aceita:
      caminho de arquivo     -> replay de captura
      /dev/tty*  ou  serial: -> pyserial
      udp:PORTA              -> escuta datagramas
      -                      -> stdin binário
    """
    if spec in ("-", "stdin"):
        return sys.stdin.buffer
    if spec.startswith("udp:"):
        porta = int(spec.split(":", 1)[1])
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("0.0.0.0", porta))
        s.settimeout(timeout)
        return _UdpBytes(s)
    if spec.startswith("/dev/tty") or spec.startswith("serial:"):
        dev = spec.split(":", 1)[1] if spec.startswith("serial:") else spec
        try:
            import serial
        except ImportError:
            raise RuntimeError(
                f"para ler de {dev} é preciso pyserial: pip install pyserial\n"
                f"  alternativa sem hardware: grave os bytes num arquivo e use "
                f"--fonte-dev <arquivo>")
        return serial.Serial(dev, 256000, timeout=timeout)
    return open(spec, "rb")


class _UdpBytes:
    """Adapta um socket UDP à interface read() que os parsers esperam."""

    def __init__(self, sock):
        self.sock = sock
        self.buf = b""

    def read(self, n=4096):
        while len(self.buf) < n:
            try:
                dados, _ = self.sock.recvfrom(65535)
            except socket.timeout:
                break
            self.buf += dados
        saida, self.buf = self.buf[:n], self.buf[n:]
        return saida

    def readline(self):
        while b"\n" not in self.buf:
            try:
                dados, _ = self.sock.recvfrom(65535)
            except socket.timeout:
                return b""
            self.buf += dados
        linha, _, self.buf = self.buf.partition(b"\n")
        return linha + b"\n"

    def close(self):
        self.sock.close()


# ------------------------------------------------------------------- base

class Fonte:
    id = "?"
    unidade = "dBm"
    VERIFICADO = False
    descricao = ""

    def amostrar(self):
        """Uma varredura. Devolve lista de registros dict."""
        raise NotImplementedError

    def dump_bruto(self, n=5):
        """Mostra os dados crus, sem interpretação. Sempre correto."""
        print(f"(fonte {self.id} não implementa dump_bruto)")

    def fechar(self):
        pass

    def _reg(self, canal, valor, **extra):
        r = {"ts": round(time.time(), 3), "fonte": self.id,
             "canal": canal, "valor": float(valor), "unidade": self.unidade}
        r.update(extra)
        return r


# ---------------------------------------------------------------- free: nmcli

class FonteNmcli(Fonte):
    id = "nmcli"
    unidade = "dBm"
    VERIFICADO = True
    descricao = "RSSI de beacon de todos os APs visíveis, via NetworkManager"

    def __init__(self, keep_bssid=False, rescan=True, **_):
        import survey
        self._survey = survey
        self.keep_bssid = keep_bssid
        self.rescan = rescan

    def amostrar(self):
        redes = self._survey.nmcli_scan(force=self.rescan)
        saida = []
        for bssid, sinal, freq, chan in redes:
            canal = bssid if self.keep_bssid else self._survey.anon(bssid)
            saida.append(self._reg(canal, self._survey.qualidade_para_dbm(sinal),
                                   quality=sinal, freq_mhz=freq, chan=chan))
        return saida

    def dump_bruto(self, n=5):
        for i in range(n):
            print(f"--- varredura {i+1} ---")
            for bssid, sinal, freq, chan in self._survey.nmcli_scan():
                print(f"  {bssid}  qualidade={sinal:3d}  {freq} MHz  ch{chan}")


# --------------------------------------------------------- sim: sem hardware

class FonteSim(Fonte):
    """
    Survey sintético COM oclusor móvel — a peça que torna docs/15 §1 e §2
    verificáveis sem sair da cadeira.

    O oclusor é um corpo humano idealizado: um disco de raio `raio_m` que
    caminha em linha reta e subtrai até `atenuacao_db` do sinal de qualquer raio
    AP->receptor que ele intercepta. A atenuação decai suavemente com a
    distância à reta, porque um corpo não tem borda dura em RF.
    """
    id = "sim"
    unidade = "dBm"
    VERIFICADO = True
    descricao = "planta conhecida + oclusor móvel; a resposta certa é conhecida"

    def __init__(self, x=0.0, y=0.0, ruido=2.0, seed=42,
                 oclusor=None, atenuacao_db=5.0, raio_m=0.35,
                 duracao=20.0, **_):
        import simulate
        self.sim = simulate
        self.pos = (float(x), float(y))
        self.ruido = ruido
        self.rng = random.Random(seed)
        self.t0 = time.time()
        self.duracao = duracao
        self.atenuacao_db = atenuacao_db
        self.raio_m = raio_m
        # oclusor = (x_ini, y_ini, x_fim, y_fim) ou None
        self.oclusor = tuple(oclusor) if oclusor else None

    def _pos_oclusor(self, t):
        if not self.oclusor:
            return None
        f = min(max((t - self.t0) / self.duracao, 0.0), 1.0)
        x0, y0, x1, y1 = self.oclusor
        return (x0 + f * (x1 - x0), y0 + f * (y1 - y0))

    @staticmethod
    def _dist_ponto_segmento(p, a, b):
        ax, ay = a
        bx, by = b
        px, py = p
        dx, dy = bx - ax, by - ay
        den = dx * dx + dy * dy
        if den < 1e-12:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / den))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    def amostrar(self):
        agora = time.time()
        oc = self._pos_oclusor(agora)
        saida = []
        for ap in self.sim.APS_EXEMPLO:
            rssi = self.sim.rssi_sintetico(ap, self.pos, self.sim.PLANTA_EXEMPLO,
                                           self.ruido, self.rng)
            bloqueio = 0.0
            if oc is not None:
                d = self._dist_ponto_segmento(oc, (ap[1], ap[2]), self.pos)
                if d < self.raio_m:
                    bloqueio = self.atenuacao_db * (1.0 - d / self.raio_m)
            saida.append(self._reg(ap[0], rssi - bloqueio,
                                   freq_mhz=2412, chan=1,
                                   oclusor_x=None if oc is None else round(oc[0], 3),
                                   oclusor_y=None if oc is None else round(oc[1], 3),
                                   bloqueio_db=round(bloqueio, 2)))
        return saida

    def dump_bruto(self, n=5):
        for _ in range(n):
            for r in self.amostrar():
                print(f"  {r['canal']:14} {r['valor']:7.2f} dBm  "
                      f"bloqueio={r['bloqueio_db']:.2f} dB")
            time.sleep(0.2)


# ------------------------------------------------------------ replay: arquivo

class FonteReplay(Fonte):
    id = "replay"
    VERIFICADO = True
    descricao = "reproduz um JSONL gravado; herda a camada do modo que o gerou"

    def __init__(self, arquivo=None, tempo_real=False, **_):
        if not arquivo:
            raise RuntimeError("modo replay exige --arquivo <jsonl gravado>")
        self.caminho = Path(arquivo)
        if not self.caminho.exists():
            raise RuntimeError(f"arquivo não encontrado: {arquivo}")
        self.tempo_real = tempo_real
        self._grupos = self._agrupar()
        self._i = 0
        if self._grupos:
            self.unidade = self._grupos[0][0].get("unidade", "dBm")

    def _agrupar(self):
        """Agrupa por timestamp: cada grupo é uma 'varredura' original."""
        grupos, atual, ts_atual = [], [], None
        with open(self.caminho) as f:
            for linha in f:
                if not linha.strip():
                    continue
                r = json.loads(linha)
                r.setdefault("canal", r.get("ap", "?"))
                r.setdefault("valor", r.get("rssi_dbm", 0.0))
                r.setdefault("unidade", "dBm")
                ts = r.get("ts", 0.0)
                if ts_atual is not None and ts != ts_atual and atual:
                    grupos.append(atual)
                    atual = []
                ts_atual = ts
                atual.append(r)
        if atual:
            grupos.append(atual)
        return grupos

    def amostrar(self):
        if self._i >= len(self._grupos):
            return []
        g = self._grupos[self._i]
        if self.tempo_real and self._i + 1 < len(self._grupos):
            dt = self._grupos[self._i + 1][0].get("ts", 0) - g[0].get("ts", 0)
            if 0 < dt < 5:
                time.sleep(dt)
        self._i += 1
        return g

    @property
    def esgotada(self):
        return self._i >= len(self._grupos)

    def dump_bruto(self, n=5):
        for g in self._grupos[:n]:
            print(f"--- ts={g[0].get('ts')} ({len(g)} registros) ---")
            for r in g[:8]:
                print(f"  {r['canal']:14} {r['valor']:8.2f} {r.get('unidade','')}")


# ------------------------------------------------------ free-root: ath10k FFT

class FonteSpectral(Fonte):
    """
    Bins de FFT do baseband do ath10k, lidos do debugfs.

    Layout de fft_sample_ath10k (spectral_common.h do kernel), big-endian:
      tlv: u8 type, be16 length            (3 bytes)
      u8 chan_width_mhz
      be16 freq1, freq2, noise, max_magnitude, total_gain_db, base_pwr_db
      be64 tsf
      s8 max_index; u8 rssi, relpwr_db, avgpwr_db, max_exp
      u8 data[]                            (bins)
    Cabeçalho = 29 bytes; bins = length - 26.
    """
    id = "spectral"
    unidade = "adim"
    VERIFICADO = False
    descricao = "magnitude por bin de FFT, taxa alta; sem fase"

    CAB = 29
    TIPO_ATH10K = 1

    def __init__(self, fonte_dev=None, **_):
        self.spec = fonte_dev or self._descobrir()
        self.f = abrir_bytes(self.spec)
        self.resto = b""

    @staticmethod
    def _descobrir():
        import glob
        alvos = glob.glob("/sys/kernel/debug/ieee80211/*/ath10k/spectral_scan0")
        if not alvos:
            raise RuntimeError(
                "não achei spectral_scan0 no debugfs. Habilite antes:\n"
                "  PHY=$(ls /sys/kernel/debug/ieee80211/)\n"
                "  echo background > /sys/kernel/debug/ieee80211/$PHY/ath10k/spectral_scan_ctl\n"
                "  echo trigger    > /sys/kernel/debug/ieee80211/$PHY/ath10k/spectral_scan_ctl")
        return alvos[0]

    def _quadros(self, blocos=8192):
        dados = self.f.read(blocos)
        if not dados:
            return []
        self.resto += dados
        saida = []
        while len(self.resto) >= 3:
            tipo, length = struct.unpack(">BH", self.resto[:3])
            total = 3 + length
            if length == 0 or total > len(self.resto):
                break
            quadro, self.resto = self.resto[:total], self.resto[total:]
            saida.append((tipo, length, quadro))
        return saida

    def amostrar(self):
        saida = []
        for tipo, length, quadro in self._quadros():
            if tipo != self.TIPO_ATH10K or len(quadro) < self.CAB:
                continue
            (largura, freq1, freq2, ruido, max_mag, ganho, base_pwr,
             tsf, max_idx, rssi, relpwr, avgpwr, max_exp) = struct.unpack(
                ">BHHhHHHQbBBBB", quadro[3:self.CAB])
            bins = quadro[self.CAB:]
            if not bins:
                continue
            # potência relativa por bin, na escala do próprio hardware
            fator = float(1 << max_exp) if max_exp < 24 else 1.0
            mags = [b * fator for b in bins]
            total = sum(m * m for m in mags)
            saida.append(self._reg(f"{freq1}MHz", 10.0 * math.log10(max(total, 1e-9)),
                                   tipo="spectral", freq_mhz=freq1, largura_mhz=largura,
                                   noise=ruido, rssi=rssi - 256 if rssi > 127 else rssi,
                                   n_bins=len(bins), tsf=tsf,
                                   max_magnitude=max_mag, max_index=max_idx,
                                   bins=[round(m, 2) for m in mags]))
        return saida

    def dump_bruto(self, n=5):
        vistos = 0
        while vistos < n:
            qs = self._quadros()
            if not qs:
                print("(sem dados — o scan está em 'background'/'trigger'?)")
                return
            for tipo, length, quadro in qs:
                print(f"  TLV tipo={tipo} length={length} bytes_totais={len(quadro)} "
                      f"bins={max(len(quadro)-self.CAB, 0)}")
                print(f"    hex[:32] = {quadro[:32].hex(' ')}")
                vistos += 1
                if vistos >= n:
                    return

    def fechar(self):
        try:
            self.f.close()
        except Exception:
            pass


# ---------------------------------------------------------- pago-csi: ESP32

class FonteEsp32Csi(Fonte):
    """
    Linhas CSV do ESP32 CSI Toolkit: 'CSI_DATA,<campos...>,[i0 q0 i1 q1 ...]'.

    O array final é o CSI cru intercalado I/Q por subportadora. Daí saem as duas
    grandezas que importam: amplitude por subportadora e — o ponto inteiro de
    comprar isto — FASE, que RSSI nenhum entrega (docs/01 §1).
    """
    id = "esp32csi"
    unidade = "dBm"
    VERIFICADO = False
    descricao = "CSI: amplitude + fase por subportadora (o único barato com fase)"

    def __init__(self, fonte_dev=None, **_):
        self.spec = fonte_dev or "-"
        self.f = abrir_bytes(self.spec)

    def _linhas(self, n=1):
        out = []
        for _ in range(n):
            linha = self.f.readline()
            if not linha:
                break
            out.append(linha.decode("utf-8", "replace").strip())
        return out

    @staticmethod
    def _parse(linha):
        if "CSI_DATA" not in linha or "[" not in linha:
            return None
        cabeca, _, cauda = linha.partition("[")
        campos = [c for c in cabeca.split(",") if c != ""]
        crus = [int(v) for v in cauda.strip().rstrip("]").split() if v.lstrip("-").isdigit()]
        if len(crus) < 4:
            return None
        # o toolkit emite pares (imag, real) por subportadora
        pares = [(crus[i], crus[i + 1]) for i in range(0, len(crus) - 1, 2)]
        amp = [math.hypot(re, im) for im, re in pares]
        fase = [math.atan2(im, re) for im, re in pares]
        rssi = None
        for c in campos[1:6]:
            try:
                v = int(c)
            except ValueError:
                continue
            if -100 <= v <= -10:
                rssi = v
                break
        mac = next((c for c in campos if c.count(":") == 5), "esp32")
        return {"mac": mac, "rssi": rssi, "amp": amp, "fase": fase}

    def amostrar(self):
        saida = []
        for linha in self._linhas(8):
            p = self._parse(linha)
            if not p:
                continue
            amp_med = sum(p["amp"]) / len(p["amp"])
            saida.append(self._reg(
                p["mac"], p["rssi"] if p["rssi"] is not None else 20 * math.log10(max(amp_med, 1e-9)),
                tipo="csi", n_subportadoras=len(p["amp"]),
                csi_amp_media=round(amp_med, 3),
                csi_amp=[round(v, 2) for v in p["amp"]],
                csi_fase=[round(v, 4) for v in p["fase"]],
                tem_fase=True))
        return saida

    def dump_bruto(self, n=5):
        for linha in self._linhas(n):
            print(f"  {linha[:160]}")

    def fechar(self):
        try:
            self.f.close()
        except Exception:
            pass


# ------------------------------------------------------ pago-mmwave: UART

class FonteMmwave(Fonte):
    """
    Módulos de radar 24 GHz por UART.

    protocolo=ld2450: quadro AA FF 03 00 + 3 alvos de 8 bytes + 55 CC.
      Cada alvo: x (int16), y (int16), velocidade (int16), resolução (uint16),
      todos little-endian, com o sinal codificado no bit alto: se v >= 0x8000
      o valor é (v - 0x8000), senão é -v. Devolve POSIÇÃO do alvo em mm.

    ARMADILHA, e é a razão de docs/15 §5 existir: isto é uma LISTA DE ALVOS já
    decidida pelo módulo, não perfil de alcance. Serve para camadas 1 e 2 e não
    contribui em nada para reconstruir geometria.
    """
    id = "mmwave"
    unidade = "m"
    VERIFICADO = False
    descricao = "lista de alvos (x, y) decidida pelo módulo; sem perfil de alcance"

    CAB_LD2450 = b"\xaa\xff\x03\x00"
    FIM_LD2450 = b"\x55\xcc"

    def __init__(self, fonte_dev=None, protocolo="ld2450", **_):
        self.spec = fonte_dev or "/dev/ttyUSB0"
        self.protocolo = protocolo
        if protocolo != "ld2450":
            raise RuntimeError(
                f"protocolo '{protocolo}' não implementado. Só ld2450.\n"
                f"  o LD2410 usa outro quadro (F4F3F2F1...F8F7F6F5) e não está escrito.\n"
                f"  use --dump-bruto para ver os bytes e escrever o parser.")
        self.f = abrir_bytes(self.spec)
        self.resto = b""

    @staticmethod
    def _coord(raw):
        return (raw - 0x8000) if raw >= 0x8000 else -raw

    def _quadros(self):
        dados = self.f.read(4096)
        if not dados:
            return []
        self.resto += dados
        saida = []
        while True:
            i = self.resto.find(self.CAB_LD2450)
            if i < 0:
                self.resto = self.resto[-64:]
                break
            j = self.resto.find(self.FIM_LD2450, i)
            if j < 0:
                self.resto = self.resto[i:]
                break
            saida.append(self.resto[i + 4:j])
            self.resto = self.resto[j + 2:]
        return saida

    def amostrar(self):
        saida = []
        for corpo in self._quadros():
            for k in range(min(3, len(corpo) // 8)):
                x, y, vel, res = struct.unpack("<HHHH", corpo[k * 8:(k + 1) * 8])
                if x == 0 and y == 0:
                    continue                       # slot de alvo vazio
                xm = self._coord(x) / 1000.0
                ym = self._coord(y) / 1000.0
                saida.append(self._reg(f"alvo{k}", math.hypot(xm, ym),
                                       tipo="alvo", alvo_x=round(xm, 3),
                                       alvo_y=round(ym, 3),
                                       vel_mps=round(self._coord(vel) / 1000.0, 3),
                                       resolucao_mm=res))
        return saida

    def dump_bruto(self, n=5):
        vistos = 0
        while vistos < n:
            qs = self._quadros()
            if not qs:
                print("(sem quadros — confira baudrate 256000 e a fiação)")
                return
            for corpo in qs:
                print(f"  corpo={len(corpo)}B  hex = {corpo.hex(' ')}")
                vistos += 1
                if vistos >= n:
                    return

    def fechar(self):
        try:
            self.f.close()
        except Exception:
            pass


# ----------------------------------------------------------- free-rtt: FTM

class FonteRtt(Fonte):
    """
    Distâncias medidas por tempo de voo, exportadas do celular.

    Não há backend local possível: quem tem a API é o Android (WifiRttManager).
    O caminho é exportar do aparelho um JSONL com um objeto por medição:

        {"ts": 1e9, "ap": "<bssid ou hash>", "dist_m": 4.12, "stddev_m": 0.9}

    e apontar --arquivo para ele. Isso não melhora a resolução do mapa; remove
    o maior erro sistemático dele, que é a posição ESTIMADA dos APs (docs/15 §6).
    """
    id = "rtt"
    unidade = "m"
    VERIFICADO = False
    descricao = "distância real por tempo de voo, exportada do celular"

    def __init__(self, arquivo=None, **_):
        if not arquivo:
            raise RuntimeError(
                "modo free-rtt exige --arquivo com o export do celular.\n"
                "  schema: {\"ts\":.., \"ap\":\"..\", \"dist_m\":.., \"stddev_m\":..}\n"
                "  teste primeiro se o seu AP suporta FTM com o app WifiRttScan.")
        self.caminho = Path(arquivo)
        self.registros = []
        with open(self.caminho) as f:
            for linha in f:
                if linha.strip():
                    self.registros.append(json.loads(linha))
        self._i = 0

    def amostrar(self):
        if self._i >= len(self.registros):
            return []
        r = self.registros[self._i]
        self._i += 1
        return [self._reg(r.get("ap", "?"), r["dist_m"], tipo="rtt",
                          stddev_m=r.get("stddev_m"))]

    def dump_bruto(self, n=5):
        for r in self.registros[:n]:
            print(f"  {r}")


# ----------------------------------------------------------- free-bfi: CBFR

class FonteBfi(Fonte):
    """
    Compressed Beamforming Reports capturados em modo monitor.

    A extração dos ângulos exige desempacotar bits de largura variável conforme
    Nc/Nr e a banda — é o trabalho que a Wi-BFI já faz, e reimplementá-lo aqui
    seria refazer pior. O que esta fonte entrega é o passo anterior, que é o que
    decide a Fase 4: CONTAR se a sua rede produz CBFR (docs/03, Fase 4).
    """
    id = "bfi"
    unidade = "adim"
    VERIFICADO = False
    descricao = "conta frames de beamforming; extração de ângulos fica na Wi-BFI"

    def __init__(self, arquivo=None, **_):
        if not arquivo:
            raise RuntimeError(
                "modo free-bfi exige --arquivo <captura.pcap>.\n"
                "  capture antes:  sudo tcpdump -i <iface em monitor> -w data/raw/bfi.pcap")
        self.caminho = arquivo
        if not os.path.exists(arquivo):
            raise RuntimeError(f"pcap não encontrado: {arquivo}")

    def _tshark(self, filtro, campos=()):
        cmd = ["tshark", "-r", self.caminho, "-Y", filtro]
        for c in campos:
            cmd += ["-T", "fields", "-e", c]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except FileNotFoundError:
            raise RuntimeError(
                "tshark ausente: sudo apt install tshark\n"
                "  sem ele não há como dissecar os frames de beamforming.")
        return [l for l in out.stdout.splitlines() if l.strip()]

    def amostrar(self):
        # action no-ack + VHT/HE compressed beamforming
        linhas = self._tshark("wlan.fixed.category_code == 21 || wlan.vht.action == 0")
        return [self._reg("cbfr", len(linhas), tipo="bfi_contagem",
                          pcap=self.caminho)]

    def dump_bruto(self, n=5):
        for l in self._tshark("wlan.fc.type == 0")[:n]:
            print(f"  {l[:160]}")


# --------------------------------------------------------- pago-sdr: IQ bruto

class FonteIq(Fonte):
    """
    IQ bruto int8 intercalado (formato do hackrf_transfer).

    Entrega potência versus tempo — camada 1 com resolução temporal altíssima.
    NÃO faz holografia: isso exige uma antena de REFERÊNCIA de fase e um
    varrimento fase-coerente (docs/01 §2), que é hardware e procedimento, não
    parser. Aqui a fase existe no dado e não é usada; é o gancho para D1.
    """
    id = "iq"
    unidade = "dBm"
    VERIFICADO = False
    descricao = "potência vs. tempo a partir de IQ; fase presente, não explorada"

    def __init__(self, fonte_dev=None, bloco=32768, **_):
        self.spec = fonte_dev or "-"
        self.f = abrir_bytes(self.spec)
        self.bloco = bloco

    def amostrar(self):
        dados = self.f.read(self.bloco)
        if not dados or len(dados) < 2:
            return []
        vals = memoryview(dados)
        n = len(vals) // 2
        soma = 0.0
        for k in range(n):
            i = vals[2 * k] - 256 if vals[2 * k] > 127 else vals[2 * k]
            q = vals[2 * k + 1] - 256 if vals[2 * k + 1] > 127 else vals[2 * k + 1]
            soma += i * i + q * q
        pot = soma / max(n, 1)
        return [self._reg("iq", 10.0 * math.log10(max(pot, 1e-9)),
                          tipo="iq_potencia", n_amostras=n,
                          nota="dBFS relativo, não dBm calibrado")]

    def dump_bruto(self, n=5):
        for _ in range(n):
            d = self.f.read(32)
            if not d:
                return
            print(f"  {d.hex(' ')}")

    def fechar(self):
        try:
            self.f.close()
        except Exception:
            pass


# ------------------------------------------------------------------ fábrica

BACKENDS = {
    "nmcli": FonteNmcli,
    "sim": FonteSim,
    "replay": FonteReplay,
    "spectral": FonteSpectral,
    "esp32csi": FonteEsp32Csi,
    "mmwave": FonteMmwave,
    "rtt": FonteRtt,
    "bfi": FonteBfi,
    "iq": FonteIq,
}


def abrir(nome_modo, **kw):
    """Resolve o modo, checa requisitos e devolve a fonte pronta."""
    m = _modos.exigir(nome_modo)
    cls = BACKENDS.get(m.fonte)
    if cls is None:
        raise RuntimeError(f"modo '{nome_modo}' aponta para backend '{m.fonte}', "
                           f"que não existe em fontes.py")
    fonte = cls(**kw)
    fonte.modo = m
    return fonte


def main():
    import argparse
    p = argparse.ArgumentParser(description="Inspeciona uma fonte de dados crua.")
    p.add_argument("--modo", default="sim")
    p.add_argument("--fonte-dev", default=None,
                   help="arquivo, /dev/ttyUSB0, udp:5566 ou - (stdin)")
    p.add_argument("--arquivo", default=None, help="para replay/rtt/bfi")
    p.add_argument("--bruto", action="store_true", help="mostra os bytes/linhas crus")
    p.add_argument("--n", type=int, default=3)
    a = p.parse_args()

    f = abrir(a.modo, fonte_dev=a.fonte_dev, arquivo=a.arquivo)
    print(f"fonte {f.id}: {f.descricao}")
    print(f"verificado com hardware real: {'sim' if f.VERIFICADO else 'NÃO'}\n")
    if a.bruto:
        f.dump_bruto(a.n)
    else:
        for i in range(a.n):
            regs = f.amostrar()
            print(f"--- amostra {i+1}: {len(regs)} registros ---")
            for r in regs[:6]:
                print(f"  {r['canal']:14} {r['valor']:8.2f} {r['unidade']}")
    f.fechar()


if __name__ == "__main__":
    main()
