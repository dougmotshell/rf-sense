#!/usr/bin/env python3
"""
modos.py — registro de modos de operação (free / pago) e do que cada um destrava.

Todo o resto do projeto consulta este arquivo. Um "modo" é um par
(fonte de dados, camada de sinal que ela entrega), e ele determina três coisas:

  1. Qual CAMADA da escada de RF sensing fica ao alcance (docs/14 §14.2).
  2. Qual RESOLUÇÃO EM ALCANCE a física permite, dada a largura de banda
     disponível: ΔR = c / (2·B). Sem espectro, B -> 0 e ΔR -> infinito, ou seja
     nenhuma resolução ao longo do raio (docs/14 §14.4).
  3. O que precisa existir na máquina, ou ser comprado, para o modo funcionar.

O objetivo deste arquivo é impedir a confusão que docs/01 e docs/04 combatem: o
modo declara o que ele PODE fazer, e se o hardware não está aqui ele diz
exatamente o que falta em vez de produzir um resultado inventado.

Nenhuma dependência além da biblioteca padrão.
"""

import argparse
import glob
import math
import os
import shutil
import sys
from dataclasses import dataclass, field

C_LUZ = 299_792_458.0

# Estados possíveis de uma camada dentro de um modo.
OK = "ok"          # funciona e é verificável aqui
PARCIAL = "parcial"  # funciona de forma degradada ou indireta
ESPEC = "espec"    # código escrito, sem hardware para verificar
NAO = "nao"        # fora de alcance neste modo

SIMBOLO = {OK: "ok", PARCIAL: "~", ESPEC: "espec", NAO: "-"}

CAMADAS = {
    1: "presenca/movimento",
    2: "localizacao/geometria",
    3: "sinais vitais",
    4: "pose/gesto",
    5: "identidade",
}


def resolucao_alcance(banda_hz):
    """ΔR = c/(2B). banda_hz None ou 0 significa: nenhuma resolução em alcance."""
    if not banda_hz:
        return math.inf
    return C_LUZ / (2.0 * banda_hz)


# ------------------------------------------------------------------- requisitos

@dataclass
class Requisito:
    """Algo que precisa existir para o modo funcionar. `checar()` diz se existe."""
    tipo: str          # binario | arquivo | glob | modulo | root | compra | externo
    alvo: str
    dica: str = ""

    def checar(self):
        """Devolve (ok: bool | None, detalhe: str). None = não verificável aqui."""
        if self.tipo == "binario":
            caminho = shutil.which(self.alvo)
            return (caminho is not None), (caminho or "não encontrado no PATH")
        if self.tipo == "arquivo":
            return os.path.exists(self.alvo), self.alvo
        if self.tipo == "glob":
            achados = glob.glob(self.alvo)
            return bool(achados), (", ".join(achados[:3]) if achados else f"nada em {self.alvo}")
        if self.tipo == "modulo":
            try:
                __import__(self.alvo)
                return True, "importável"
            except ImportError:
                return False, f"módulo python '{self.alvo}' ausente"
        if self.tipo == "root":
            ok = hasattr(os, "geteuid") and os.geteuid() == 0
            return ok, ("rodando como root" if ok else "precisa de sudo")
        if self.tipo == "compra":
            return None, self.alvo          # nunca detectável por software
        return None, self.alvo


@dataclass
class Modo:
    nome: str
    titulo: str
    custo_usd: float
    fonte: str                       # id do backend em fontes.py
    banda_hz: float | None           # largura de banda do sinal disponível
    tem_fase: bool
    camadas: dict = field(default_factory=dict)
    requisitos: list = field(default_factory=list)
    doc: str = ""
    nota: str = ""
    verificado: bool = True          # False = código escrito, hardware não testado

    @property
    def gratis(self):
        return self.custo_usd == 0

    @property
    def delta_r(self):
        return resolucao_alcance(self.banda_hz)

    def camada(self, n):
        return self.camadas.get(n, NAO)

    def disponivel(self):
        """
        Devolve (estado, [(requisito, ok, detalhe)]).

        estado é um de: "pronto" | "comprar" | "falta" | "incerto".

        A precedência importa e não é a ordem da lista. Um requisito de COMPRA
        vence um binário ausente, porque não se instala o caminho para fora de
        não possuir o equipamento: dizer "falta hackrf_transfer" a quem não tem
        um HackRF é diagnóstico errado.
        """
        linhas = [(r, *r.checar()) for r in self.requisitos]
        if any(r.tipo == "compra" for r, _, _ in linhas):
            return "comprar", linhas
        if any(ok is False for _, ok, _ in linhas):
            return "falta", linhas
        if any(r.tipo == "externo" for r, _, _ in linhas):
            return "incerto", linhas
        return "pronto", linhas


# ----------------------------------------------------------------- o registro

MODOS = {}


def _reg(m):
    MODOS[m.nome] = m
    return m


_reg(Modo(
    nome="sim",
    titulo="Sintético — planta conhecida, sem hardware nenhum",
    custo_usd=0,
    fonte="sim",
    banda_hz=None,
    tem_fase=False,
    camadas={1: OK, 2: OK, 3: NAO, 4: NAO, 5: NAO},
    requisitos=[],
    doc="docs/10",
    nota="Valida a MATEMÁTICA, não a física (D10). É o único modo em que você "
         "conhece a resposta certa, então é onde todo teste novo começa.",
))

_reg(Modo(
    nome="free",
    titulo="RSSI de beacon via nmcli — o modo padrão do projeto",
    custo_usd=0,
    fonte="nmcli",
    banda_hz=None,          # um número de potência por beacon: sem espectro
    tem_fase=False,
    camadas={1: OK, 2: PARCIAL, 3: NAO, 4: NAO, 5: NAO},
    requisitos=[Requisito("binario", "nmcli", "faz parte do NetworkManager")],
    doc="docs/01 §4.1, docs/15 §1",
    nota="Camada 2 é PARCIAL e invertida: em vez de localizar pessoas a partir de "
         "posições conhecidas, recupera geometria a partir de posições que você "
         "informa. Toda a resolução vem do cruzamento de raios (docs/14 §14.4).",
))

_reg(Modo(
    nome="replay",
    titulo="Reprodução de um arquivo já gravado",
    custo_usd=0,
    fonte="replay",
    banda_hz=None,
    tem_fase=False,
    camadas={1: OK, 2: OK, 3: ESPEC, 4: ESPEC, 5: NAO},
    requisitos=[],
    doc="docs/09",
    nota="Herda as camadas do modo que gravou o arquivo. Existe para exercitar "
         "os modos pagos sem ter o hardware — e para reanalisar coleta antiga.",
))

_reg(Modo(
    nome="free-root",
    titulo="Spectral scan do ath10k — bins de FFT do baseband",
    custo_usd=0,
    fonte="spectral",
    banda_hz=80e6,          # VHT80; cai para 20/40 MHz conforme o canal
    tem_fase=False,         # magnitude apenas
    camadas={1: OK, 2: NAO, 3: NAO, 4: NAO, 5: NAO},
    requisitos=[
        Requisito("root", "", "debugfs do ath10k exige privilégio"),
        Requisito("glob", "/sys/kernel/debug/ieee80211/*/ath10k/spectral_scan_ctl",
                  "kernel com CONFIG_ATH10K_SPECTRAL=y e debugfs montado"),
    ],
    doc="docs/03 Fase 5",
    verificado=False,
    nota="Taxa temporal alta, ótimo para camada 1. Magnitude sem fase, então não "
         "reabre imageamento coerente. O hardware ignora spectral_count e envia "
         "amostras indefinidamente: limite por TEMPO.",
))

_reg(Modo(
    nome="free-bfi",
    titulo="Beamforming Feedback Information em modo monitor",
    custo_usd=0,
    fonte="bfi",
    banda_hz=80e6,
    tem_fase=PARCIAL,       # ângulos comprimidos, não fase bruta
    camadas={1: OK, 2: ESPEC, 3: NAO, 4: NAO, 5: NAO},
    requisitos=[
        Requisito("root", "", "modo monitor exige privilégio"),
        Requisito("binario", "iw", "sudo apt install iw"),
        Requisito("binario", "tcpdump", "captura dos frames"),
        Requisito("externo", "tráfego 802.11ac/ax com sounding na rede",
                  "rede ociosa em 2,4 GHz não gera CBFR nenhum"),
    ],
    doc="docs/01 §4.3, docs/03 Fase 4",
    verificado=False,
    nota="Os CBFR trafegam antes da criptografia, então qualquer receptor próximo "
         "os captura. Dão informação ANGULAR (AoA aproximado), que é o mais perto "
         "de eco que este hardware alcança. Extração com a Wi-BFI.",
))

_reg(Modo(
    nome="free-rtt",
    titulo="Wi-Fi RTT / FTM (802.11mc) pelo celular",
    custo_usd=0,
    fonte="rtt",
    banda_hz=None,
    tem_fase=False,
    camadas={1: PARCIAL, 2: OK, 3: NAO, 4: NAO, 5: NAO},
    requisitos=[
        Requisito("externo", "Android 9+ (API 28) com WifiRttManager", "app WifiRttScan"),
        Requisito("externo", "AP com suporte a FTM",
                  "gargalo mais provável: poucos roteadores domésticos suportam"),
    ],
    doc="docs/01 §4.4, docs/15 §6",
    verificado=False,
    nota="Distância REAL por tempo de voo, 1–2 m com 3+ APs. Não melhora a "
         "resolução do mapa, mas remove o maior erro sistemático dele: a posição "
         "estimada dos APs passa a ser medida. É o melhor ganho gratuito que existe.",
))

_reg(Modo(
    nome="pago-csi",
    titulo="ESP32-S3 + ESP32 CSI Toolkit — amplitude E FASE por subportadora",
    custo_usd=8,
    fonte="esp32csi",
    banda_hz=40e6,
    tem_fase=True,
    camadas={1: OK, 2: OK, 3: ESPEC, 4: ESPEC, 5: NAO},
    requisitos=[
        Requisito("compra", "ESP32-S3 (US$ 5–8) com o ESP32 CSI Toolkit gravado"),
        Requisito("externo", "porta serial ou stream UDP do nó", "ver --fonte-dev"),
    ],
    doc="docs/02, docs/15 §5",
    verificado=False,
    nota="A MELHOR COMPRA do projeto e a única barata que devolve FASE — o divisor "
         "de águas de docs/01 §1. Muda o projeto de categoria: reabre camadas 3 e 4 "
         "e, com dois nós, informação coerente entre eles.",
))

_reg(Modo(
    nome="pago-mmwave",
    titulo="Módulo de radar 24/60 GHz por UART (LD2410 / LD2450 / MR60)",
    custo_usd=22,
    fonte="mmwave",
    banda_hz=250e6,         # 24,00–24,25 GHz narrowband; módulos 60 GHz chegam a ~4 GHz
    tem_fase=False,         # o módulo não expõe o IQ, só a decisão
    camadas={1: OK, 2: OK, 3: PARCIAL, 4: NAO, 5: NAO},
    requisitos=[
        Requisito("compra", "módulo 24/60 GHz (US$ 7–30) + adaptador USB-serial"),
        Requisito("modulo", "serial", "pip install pyserial (ou use replay de arquivo)"),
        Requisito("glob", "/dev/ttyUSB*", "adaptador serial conectado"),
    ],
    doc="docs/15 §5, docs/15 §8",
    verificado=False,
    nota="ARMADILHA: quase todos esses módulos entregam DECISÕES (presença, "
         "distância, taxa de respiração), não perfil de alcance bruto. Resolvem "
         "camadas 1–2 e não contribuem para geometria. Antes de comprar, confirme "
         "que o módulo expõe range-Doppler ou ADC. Ver docs/15 §8 sobre espectro.",
))

_reg(Modo(
    nome="pago-sdr",
    titulo="SDR / EVM com IQ bruto (HackRF, TI IWR6843)",
    custo_usd=150,
    fonte="iq",
    banda_hz=20e6,          # HackRF; o TI IWR6843 chega a ~4 GHz em 60 GHz
    tem_fase=True,
    camadas={1: OK, 2: OK, 3: ESPEC, 4: ESPEC, 5: NAO},
    requisitos=[
        Requisito("compra", "HackRF One (US$ 150) ou TI IWR6843 EVM (US$ 200–300)"),
        Requisito("binario", "hackrf_transfer", "pacote hackrf"),
    ],
    doc="docs/01 §2, docs/12 D1",
    verificado=False,
    nota="O único caminho que reabre IMAGEAMENTO COERENTE: com IQ e uma antena de "
         "referência, a holografia de Wi-Fi (Holl & Reinhard) volta a ser possível. "
         "É o gatilho declarado para revisitar D1.",
))


# ------------------------------------------------------------------------ API

class ModoIndisponivel(RuntimeError):
    """Erguida quando o modo pedido existe mas o que ele exige não está aqui."""


def resolver(nome):
    if nome not in MODOS:
        disponiveis = ", ".join(MODOS)
        raise SystemExit(f"modo '{nome}' não existe. Disponíveis: {disponiveis}\n"
                         f"Veja: python3 src/modos.py --listar")
    return MODOS[nome]


def exigir(nome, permitir_nao_verificado=True):
    """Resolve o modo e falha com diagnóstico útil se ele não puder rodar aqui."""
    m = resolver(nome)
    estado, linhas = m.disponivel()
    if estado == "falta":
        faltando = [f"    - {r.tipo}:{r.alvo or '(root)'}  ->  {det}"
                    + (f"\n      dica: {r.dica}" if r.dica else "")
                    for r, o, det in linhas if o is False]
        raise ModoIndisponivel(
            f"modo '{nome}' ({m.titulo}) não pode rodar aqui.\n"
            f"  falta:\n" + "\n".join(faltando) +
            f"\n  documentação: {m.doc}\n"
            f"  alternativa gratuita e sempre disponível: --modo sim")
    if estado == "comprar":
        itens = [f"    - {det}" for r, _, det in linhas if r.tipo == "compra"]
        raise ModoIndisponivel(
            f"modo '{nome}' ({m.titulo}) exige hardware que o projeto não tem.\n"
            f"  comprar:\n" + "\n".join(itens) +
            f"\n  custo estimado: US$ {m.custo_usd:.0f}\n"
            f"  documentação: {m.doc}\n"
            f"  para exercitar o backend sem o hardware: --modo replay --arquivo <gravação>")
    if not m.verificado and permitir_nao_verificado:
        print(f"[aviso] modo '{nome}': código escrito, NUNCA verificado contra "
              f"hardware real. Trate a saída como suspeita até conferir. "
              f"Ver {m.doc}.", file=sys.stderr)
    return m


def camada_maxima(m):
    """A camada mais alta que o modo alcança em estado ok ou parcial."""
    alcancadas = [n for n in sorted(CAMADAS) if m.camada(n) in (OK, PARCIAL)]
    return max(alcancadas) if alcancadas else 0


# ------------------------------------------------------------------------ CLI

def _fmt_dr(dr):
    if dr == math.inf:
        return "sem resolução"
    if dr < 0.1:
        return f"{dr*100:.1f} cm"
    return f"{dr:.2f} m"


def listar(so_gratis=False):
    print(f"{'modo':13} {'custo':>7}  {'fase':4} {'ΔR alcance':>13}  camadas 1..5   estado")
    print("-" * 78)
    for m in MODOS.values():
        if so_gratis and not m.gratis:
            continue
        estado, _ = m.disponivel()
        estado = {"pronto": "disponível", "falta": "falta req.",
                  "comprar": "precisa comprar", "incerto": "não verificável"}[estado]
        if not m.verificado:
            estado += " *"
        cams = " ".join(f"{SIMBOLO[m.camada(n)]:>5}" for n in sorted(CAMADAS))
        custo = "grátis" if m.gratis else f"US$ {m.custo_usd:.0f}"
        fase = "sim" if m.tem_fase is True else ("~" if m.tem_fase == PARCIAL else "não")
        print(f"{m.nome:13} {custo:>7}  {fase:4} {_fmt_dr(m.delta_r):>13}  {cams}   {estado}")
    print("-" * 78)
    print("camadas: 1 presença · 2 localização/geometria · 3 vitais · 4 pose · 5 identidade")
    print("legenda: ok funciona · ~ parcial · espec código sem hardware testado · - fora")
    print("  * = modo cujo backend nunca foi verificado contra hardware real")
    print("\nΔR = c/(2·B): resolução AO LONGO do raio. 'sem resolução' significa B->0,")
    print("como no RSSI de beacon — aí toda a resolução vem do cruzamento de raios")
    print("de posições diferentes, ou seja de caminhar mais (docs/14 §14.4).")


def escada():
    print("Escada de camadas — qual modo destrava cada uma (docs/14 §14.2)\n")
    for n, nome in CAMADAS.items():
        print(f"  Camada {n} — {nome}")
        for est in (OK, PARCIAL, ESPEC):
            ms = [m.nome for m in MODOS.values() if m.camada(n) == est]
            if ms:
                etq = {OK: "funciona", PARCIAL: "parcial ", ESPEC: "só código"}[est]
                print(f"      {etq}: {', '.join(ms)}")
        if not any(m.camada(n) != NAO for m in MODOS.values()):
            print("      fora de alcance em todos os modos")
        print()
    print("Camadas 3 a 5 são sobre PESSOAS e este projeto não as persegue por decisão,")
    print("não só por limitação de hardware — ver docs/15 §9.")


def detectar():
    print("O que está disponível NESTA máquina agora:\n")
    grupos = {"pronto": [], "falta": [], "comprar": [], "incerto": []}
    for m in MODOS.values():
        estado, linhas = m.disponivel()
        grupos[estado].append((m, linhas))
    prontos, faltando, comprar, incerto = (grupos["pronto"], grupos["falta"],
                                           grupos["comprar"], grupos["incerto"])

    print("PRONTOS PARA USAR")
    for m, _ in prontos:
        print(f"  {m.nome:13} {m.titulo}")
    if faltando:
        print("\nFALTA ALGO GRATUITO (instalável ou privilégio)")
        for m, linhas in faltando:
            print(f"  {m.nome:13} {m.titulo}")
            for r, o, det in linhas:
                if o is False:
                    print(f"       falta {r.tipo}:{r.alvo or '(root)'} — {det}")
                    if r.dica:
                        print(f"       dica: {r.dica}")
    if incerto:
        print("\nDEPENDE DE ALGO QUE SOFTWARE NÃO DETECTA (teste manualmente)")
        for m, linhas in incerto:
            print(f"  {m.nome:13} {m.titulo}")
            for r, o, det in linhas:
                if r.tipo == "externo":
                    print(f"       verificar: {det}")
                    if r.dica:
                        print(f"       dica: {r.dica}")
    if comprar:
        print("\nEXIGE COMPRA (fora do custo zero)")
        for m, linhas in comprar:
            print(f"  {m.nome:13} US$ {m.custo_usd:>3.0f}  {m.titulo}")
    teto = max((camada_maxima(m) for m, _ in prontos), default=0)
    print(f"\nCamada máxima verificável hoje, sem gastar nada: {teto}"
          f"  ({CAMADAS.get(teto, '-')})")
    print("Camadas 3–5 exigem fase ou banda larga, e nenhum modo gratuito as entrega")
    print("(docs/14 §14.2). Não é falta de esforço, é ordem de magnitude.")


def explicar(nome):
    m = resolver(nome)
    estado, linhas = m.disponivel()
    print("=" * 74)
    print(f"MODO {m.nome} — {m.titulo}")
    print("=" * 74)
    print(f"  custo            : {'grátis' if m.gratis else f'US$ {m.custo_usd:.0f}'}")
    print(f"  backend          : fontes.py:{m.fonte}")
    print(f"  largura de banda : "
          f"{'n/a (potência agregada)' if not m.banda_hz else f'{m.banda_hz/1e6:.0f} MHz'}")
    print(f"  ΔR = c/(2B)      : {_fmt_dr(m.delta_r)}")
    print(f"  entrega fase?    : {'SIM' if m.tem_fase is True else 'parcial' if m.tem_fase == PARCIAL else 'não'}"
          f"   {'-> imageamento coerente possível' if m.tem_fase is True else ''}")
    print(f"  documentação     : {m.doc}")
    print(f"  backend testado  : {'sim' if m.verificado else 'NÃO — nunca rodou com hardware real'}")
    print("\n  camadas:")
    for n, cn in CAMADAS.items():
        print(f"    {n} {cn:24} {SIMBOLO[m.camada(n)]}")
    print("\n  requisitos:")
    if not m.requisitos:
        print("    (nenhum)")
    for r, o, det in linhas:
        marca = "ok  " if o is True else "FALTA" if o is False else "?   "
        print(f"    [{marca}] {r.tipo}: {r.alvo or '(root)'}")
        print(f"            {det}")
        if r.dica and o is not True:
            print(f"            dica: {r.dica}")
    if m.nota:
        print("\n  nota:")
        for linha in _quebrar(m.nota, 68):
            print(f"    {linha}")
    print(f"\n  veredito: " + {
        "pronto": "pode rodar agora",
        "falta": "falta requisito marcado FALTA acima",
        "comprar": f"depende de compra (US$ {m.custo_usd:.0f})",
        "incerto": "software não consegue verificar — teste manualmente",
    }[estado])


def _quebrar(texto, largura):
    palavras, linha, saida = texto.split(), "", []
    for p in palavras:
        if len(linha) + len(p) + 1 > largura:
            saida.append(linha)
            linha = p
        else:
            linha = f"{linha} {p}".strip()
    if linha:
        saida.append(linha)
    return saida


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--listar", action="store_true", help="tabela de todos os modos")
    p.add_argument("--gratis", action="store_true", help="com --listar, só os de custo zero")
    p.add_argument("--detectar", action="store_true", help="o que roda nesta máquina agora")
    p.add_argument("--camadas", action="store_true", help="a escada de camadas por modo")
    p.add_argument("--explicar", metavar="MODO", help="detalhe de um modo")
    a = p.parse_args()

    if a.explicar:
        explicar(a.explicar)
    elif a.detectar:
        detectar()
    elif a.camadas:
        escada()
    else:
        listar(so_gratis=a.gratis)


if __name__ == "__main__":
    main()
