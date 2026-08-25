#!/usr/bin/env python3
"""
poc.py — o MVP: um comando que roda os portões em ordem e dá veredito.

O projeto tem seis ferramentas e treze documentos. O que faltava era a pergunta
única: DÁ PARA SEGUIR, NESTE HARDWARE, HOJE? Este script responde com portões
ordenados, cada um com critério objetivo, e para no primeiro que reprova — porque
seguir em frente com um portão reprovado só move o erro para mais tarde, onde ele
fica mais caro de achar.

  P0  cadência        a cadeia de medição é rápida o suficiente para o quê?
  P1  quantização     qual o menor degrau de sinal que ela distingue?
  P2  visibilidade    há APs suficientes, e estáveis?
  P3  matemática      o pipeline reconstrói uma planta CONHECIDA?
  P4  campo           existe ground truth para comparar, e plano de coleta?

P0 a P2 medem o rádio de verdade e dependem do --modo. P3 roda sempre em modo
sim, porque validar a matemática exige conhecer a resposta — é o único jeito de
separar "o algoritmo está errado" de "a coleta está ruim" (D10).

Uso:
    python3 src/poc.py --modo free       # diagnostica o rádio real
    python3 src/poc.py --modo sim        # prova a matemática de ponta a ponta
    python3 src/poc.py --so-matematica   # pula o hardware
"""

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compare                                                   # noqa: E402
import fontes                                                    # noqa: E402
import modos                                                     # noqa: E402
import orcamento                                                 # noqa: E402
import reconstruct                                               # noqa: E402
from groundtruth import carregar as carregar_gt, rasterizar       # noqa: E402
from probe import EXIGENCIA_HZ                                   # noqa: E402

PASSOU, REPROVOU, PULOU, ALERTA = "PASSOU", "REPROVOU", "PULOU", "ALERTA"


class Portao:
    def __init__(self, cod, nome):
        self.cod, self.nome = cod, nome
        self.estado, self.resumo, self.detalhes = PULOU, "", []

    def fecha(self, estado, resumo):
        self.estado, self.resumo = estado, resumo
        return self

    def diz(self, linha):
        self.detalhes.append(linha)


# ------------------------------------------------------------------ P0 e P1

def amostrar_fonte(modo, dur, **kw):
    """Coleta bruta compartilhada por P0, P1 e P2 — uma passada, três portões."""
    if modo == "sim":
        kw.setdefault("x", 2.0)
        kw.setdefault("y", 2.0)
        kw.setdefault("duracao", dur)
    fonte = fontes.abrir(modo, **kw)
    valores = defaultdict(list)
    mudancas = defaultdict(int)
    ultimo = {}
    latencias = []
    consultas = 0
    t0 = time.time()
    try:
        while time.time() - t0 < dur:
            ti = time.time()
            regs = fonte.amostrar()
            latencias.append(time.time() - ti)
            consultas += 1
            for r in regs:
                c, v = r["canal"], r["valor"]
                valores[c].append(v)
                if c in ultimo and v != ultimo[c]:
                    mudancas[c] += 1
                ultimo[c] = v
            if not regs and getattr(fonte, "esgotada", False):
                break
    finally:
        fonte.fechar()
    return {"dur": time.time() - t0, "valores": dict(valores), "mudancas": dict(mudancas),
            "consultas": consultas, "latencias": latencias, "unidade": fonte.unidade,
            "verificado": fonte.VERIFICADO}


def p0_cadencia(dados, modo):
    p = Portao("P0", "cadência da cadeia de medição")
    dur = dados["dur"]
    if not dados["valores"]:
        return p.fecha(REPROVOU, "a fonte não devolveu nenhum canal")

    hz_consulta = dados["consultas"] / max(dur, 1e-9)
    taxas = [n / dur for n in dados["mudancas"].values()]
    hz_efetivo = max(taxas) if taxas else 0.0

    p.diz(f"consultas à fonte  : {hz_consulta:6.2f} Hz "
          f"(latência mediana {np.median(dados['latencias']):.3f} s)")
    p.diz(f"TAXA EFETIVA       : {hz_efetivo:6.3f} Hz  "
          f"(quantas vezes por segundo o número MUDA)")
    if hz_efetivo > 0 and hz_consulta > hz_efetivo * 3:
        p.diz(f"perguntando {hz_consulta/hz_efetivo:.0f}x mais rápido do que o dado muda —")
        p.diz("as leituras extras são o mesmo valor repetido, e não reduzem ruído")

    alcancado = [t for h, t in EXIGENCIA_HZ if hz_efetivo >= h]
    for limite, texto in EXIGENCIA_HZ:
        p.diz(f"  [{'ok ' if hz_efetivo >= limite else '-- '}] >= {limite:5.2f} Hz  {texto}")

    p.hz = hz_efetivo
    p.protocolo = ("dinamico" if hz_efetivo >= 1.0
                   else "estatico" if hz_efetivo >= 0.05 else "nenhum")
    if p.protocolo == "nenhum":
        return p.fecha(REPROVOU, f"{hz_efetivo:.3f} Hz — lento até para oclusor parado")
    if p.protocolo == "estatico":
        return p.fecha(ALERTA, f"{hz_efetivo:.3f} Hz — só protocolo ESTÁTICO; "
                               f"a sonda de docs/15 §2 exige 2 Hz e está fora")
    return p.fecha(PASSOU, f"{hz_efetivo:.3f} Hz — protocolo dinâmico viável")


def p1_quantizacao(dados):
    p = Portao("P1", "quantização e faixa dinâmica")
    degraus, faixas = [], []
    for c, vs in dados["valores"].items():
        d = sorted(set(vs))
        if len(d) < 2:
            continue
        degraus.append(min(b - a for a, b in zip(d, d[1:])))
        faixas.append(d[-1] - d[0])
    if not degraus:
        return p.fecha(REPROVOU, "nenhum canal variou: impossível medir o degrau")

    degrau = float(np.median(degraus))
    faixa = float(np.median(faixas))
    p.diz(f"menor degrau distinguível : {degrau:.2f} {dados['unidade']}")
    p.diz(f"faixa observada (mediana) : {faixa:.2f} {dados['unidade']} por canal")
    p.diz(f"canais que variaram       : {len(degraus)}/{len(dados['valores'])}")

    # O sinal que o projeto persegue: corpo humano 3-6 dB, parede interna ~6 dB
    for nome, amplitude in (("corpo humano", 3.0), ("parede interna", 6.0)):
        n = amplitude / degrau if degrau else float("inf")
        p.diz(f"  {nome} ({amplitude:.0f} dB) cabe em {n:.1f} degraus")
    p.degrau = degrau
    if degrau >= 3.0:
        return p.fecha(REPROVOU, f"degrau de {degrau:.1f} dB engole o sinal de 3 dB "
                                 f"do corpo humano")
    if degrau > 1.0:
        return p.fecha(ALERTA, f"degrau de {degrau:.1f} dB: o sinal do corpo cabe em "
                               f"~{3.0/degrau:.0f} degraus. Funciona, com pouca margem")
    return p.fecha(PASSOU, f"degrau de {degrau:.2f} dB, folga confortável")


def p2_visibilidade(dados, min_aps):
    p = Portao("P2", "visibilidade de APs")
    n = len(dados["valores"])
    estaveis = sum(1 for vs in dados["valores"].values()
                   if len(vs) >= 0.5 * max(len(v) for v in dados["valores"].values()))
    p.diz(f"canais vistos      : {n}")
    p.diz(f"vistos em >=50% das leituras : {estaveis}")
    if not dados["verificado"]:
        p.diz("backend NUNCA verificado contra hardware real — trate como suspeito")
    if n < 3:
        return p.fecha(REPROVOU, f"{n} canais: a tomografia precisa de 3+, idealmente 8+")
    if estaveis < min_aps:
        return p.fecha(ALERTA, f"{estaveis} canais estáveis, abaixo dos {min_aps} "
                               f"do critério da Fase 1")
    return p.fecha(PASSOU, f"{estaveis} canais estáveis")


# ---------------------------------------------------------------------- P3

def p3_matematica(gt_path, step, grid, ruido, seed):
    """Fecha o ciclo com a resposta conhecida: gera, reconstrói, avalia."""
    p = Portao("P3", "matemática de ponta a ponta (modo sim)")
    if not Path(gt_path).exists():
        return p.fecha(PULOU, f"{gt_path} não existe")

    gt = carregar_gt(gt_path)
    gt = dict(gt, paredes=[w for w in gt["paredes"] if w.get("tipo") == "divisoria"])
    if not gt["paredes"]:
        return p.fecha(PULOU, "nenhuma parede do tipo divisoria (D15)")

    medidas, n_pontos = orcamento.gerar_medidas(step, 12, ruido, seed)
    try:
        r = reconstruct.reconstruir(medidas, grid=grid, n_referencia=2.6, verbose=False)
    except ValueError as e:
        return p.fecha(REPROVOU, f"reconstrução falhou: {e}")

    origem = (float(r["origem"][0]), float(r["origem"][1]))
    nx, ny = r["nx"], r["ny"]
    mapa = r["mapa"].reshape(ny, nx)
    real = np.array(rasterizar(gt, origem, grid, nx, ny), dtype=bool)
    dist = compare.campo_de_distancia(gt, origem, grid, nx, ny)
    m = compare.avaliar(mapa, real, dist, mascara=r["mascara"])
    if m is None:
        return p.fecha(REPROVOU, "nenhuma célula avaliável sob a máscara de cobertura")

    p.diz(f"planta            : {n_pontos} pontos, step {step} m, grade {grid} m, "
          f"ruído {ruido} dB")
    p.diz(f"raios / cobertura : {r['meta']['n_raios']} raios, "
          f"{r['mascara'].mean()*100:.0f}% das células cobertas")
    p.diz(f"F1                : {m['f1']:.3f}  ({m['ganho_f1']:.1f}x o acaso)")
    p.diz(f"distância ponderada: {m['d_pond']:.2f} m  "
          f"({m['razao_dist']:.2f}x o acaso de {m['d_acaso']:.2f} m)")
    p.diz("teto da matemática, não previsão da física (D10)")

    # o mesmo critério da Fase 2, em docs/03
    if m["razao_dist"] < 0.6 and m["ganho_f1"] > 2.0:
        return p.fecha(PASSOU, f"F1 {m['ganho_f1']:.1f}x o acaso, "
                               f"d {m['razao_dist']:.2f}x o acaso")
    return p.fecha(REPROVOU, f"não atinge o critério da Fase 2 nem no simulador "
                             f"(F1 {m['ganho_f1']:.1f}x, d {m['razao_dist']:.2f}x)")


# ---------------------------------------------------------------------- P4

def p4_campo(gt_path):
    p = Portao("P4", "prontidão de campo")
    if not Path(gt_path).exists():
        p.diz(f"{gt_path} não existe — sem referência, 'o mapa ficou bom' é opinião")
        p.diz("é a Fase 0, e ela vem ANTES de qualquer RF (D2):")
        p.diz("  cp data/ground_truth.example.json data/ground_truth.json")
        p.diz("  # edite com as medidas da SUA casa")
        p.diz("  python3 src/groundtruth.py data/ground_truth.json --render")
        return p.fecha(REPROVOU, "sem ground truth da casa real")
    gt = carregar_gt(gt_path)
    divisorias = [w for w in gt["paredes"] if w.get("tipo") == "divisoria"]
    p.diz(f"{len(gt['paredes'])} paredes, {len(divisorias)} divisórias, "
          f"{len(gt.get('portas', []))} portas")
    if not divisorias:
        return p.fecha(REPROVOU, "nenhuma parede interna: só externas, e elas não "
                                 "são recuperáveis por construção (D15)")
    return p.fecha(PASSOU, f"{len(divisorias)} divisórias para avaliar")


# --------------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modo", default="free", help="modo de aquisição (python3 src/modos.py --listar)")
    p.add_argument("--dur", type=float, default=45.0, help="segundos de medição do rádio")
    p.add_argument("--so-matematica", action="store_true", help="pula P0-P2")
    p.add_argument("--min-aps", type=int, default=8, help="critério da Fase 1")
    p.add_argument("--step", type=float, default=1.0, help="[P3] espaçamento simulado")
    p.add_argument("--grid", type=float, default=0.5, help="[P3] célula")
    p.add_argument("--ruido", type=float, default=2.0, help="[P3] ruído em dB")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--ground-truth", default="data/ground_truth.json")
    p.add_argument("--fonte-dev", default=None)
    p.add_argument("--arquivo", default=None)
    p.add_argument("--sem-rescan", action="store_true", help="[free] ler o cache")
    p.add_argument("--out", default=None, help="salvar o veredito em JSON")
    a = p.parse_args()

    m = modos.resolver(a.modo)
    print("=" * 74)
    print("rf-sense — POC: dá para seguir, neste hardware, hoje?")
    print("=" * 74)
    print(f"modo   : {m.nome} — {m.titulo}")
    print(f"custo  : {'grátis' if m.gratis else f'US$ {m.custo_usd:.0f}'} · "
          f"ΔR em alcance: "
          f"{'inexistente (B->0)' if m.delta_r == math.inf else f'{m.delta_r:.2f} m'}")
    print(f"camada máxima declarada pelo modo: {modos.camada_maxima(m)}")
    print()

    portoes = []
    if not a.so_matematica:
        try:
            modos.exigir(a.modo)
            print(f"medindo o rádio por {a.dur:.0f} s...", flush=True)
            dados = amostrar_fonte(a.modo, a.dur, fonte_dev=a.fonte_dev,
                                   arquivo=a.arquivo, rescan=not a.sem_rescan)
            portoes += [p0_cadencia(dados, a.modo), p1_quantizacao(dados),
                        p2_visibilidade(dados, a.min_aps)]
        except (modos.ModoIndisponivel, RuntimeError) as e:
            g = Portao("P0", "cadência da cadeia de medição")
            g.diz(str(e))
            portoes.append(g.fecha(REPROVOU, "o modo não pode rodar aqui"))
    else:
        for cod, nome in (("P0", "cadência"), ("P1", "quantização"),
                          ("P2", "visibilidade")):
            portoes.append(Portao(cod, nome).fecha(PULOU, "--so-matematica"))

    portoes.append(p3_matematica(
        a.ground_truth if Path(a.ground_truth).exists()
        else "data/ground_truth.example.json", a.step, a.grid, a.ruido, a.seed))
    portoes.append(p4_campo(a.ground_truth))

    for g in portoes:
        print(f"\n[{g.estado:8}] {g.cod} — {g.nome}")
        print(f"           {g.resumo}")
        for d in g.detalhes:
            print(f"           {d}")

    print("\n" + "=" * 74)
    reprovados = [g for g in portoes if g.estado == REPROVOU]
    alertas = [g for g in portoes if g.estado == ALERTA]
    p0 = next((g for g in portoes if g.cod == "P0"), None)

    if reprovados:
        print(f"VEREDITO: BLOQUEADO em {reprovados[0].cod} — {reprovados[0].resumo}")
        print("\nO próximo passo é destravar esse portão, e só ele. Seguir com um")
        print("portão reprovado move o erro para depois, onde custa mais para achar.")
    else:
        print("VEREDITO: LIBERADO" + (f" com {len(alertas)} alerta(s)" if alertas else ""))
        proto = getattr(p0, "protocolo", None)
        print("\nPróximos passos, na ordem revista de docs/15 §10:")
        if proto == "estatico":
            print("  1. teste de movimento, protocolo ESTÁTICO (a cadência não")
            print("     permite cronometrar uma travessia):")
            print(f"       python3 src/probe.py gravar --modo {a.modo} --label vazio "
                  f"--dur 180 --out data/raw/ab-vazio.jsonl")
            print(f"       python3 src/probe.py gravar --modo {a.modo} --label bloq "
                  f"--dur 180 --out data/raw/ab-bloq.jsonl")
            print("       python3 src/probe.py movimento --ab data/raw/ab-vazio.jsonl "
                  "data/raw/ab-bloq.jsonl")
        elif proto == "dinamico":
            print("  1. teste de movimento e sonda (protocolo dinâmico liberado):")
            print(f"       python3 src/probe.py gravar --modo {a.modo} --rx X,Y "
                  f"--caminho x0,y0,x1,y1 --dur 30 --marcar")
        print("  2. orçamento de resolução, para escolher --step com justificativa:")
        print("       python3 src/orcamento.py")
        print("  3. survey e reconstrução:")
        print("       python3 src/survey.py --x .. --y .. --out data/raw/survey.jsonl")
        print("       python3 src/reconstruct.py data/raw/survey.jsonl "
              f"--modo {a.modo}")
        print("       python3 src/camadas.py --survey data/raw/survey.jsonl")

    if alertas:
        print("\nAlertas que valem ler antes de coletar:")
        for g in alertas:
            print(f"  {g.cod}: {g.resumo}")

    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(
            {"modo": a.modo, "ts": time.time(),
             "portoes": [{"cod": g.cod, "nome": g.nome, "estado": g.estado,
                          "resumo": g.resumo, "detalhes": g.detalhes} for g in portoes],
             "veredito": "BLOQUEADO" if reprovados else "LIBERADO"}, indent=2))
        print(f"\nveredito salvo em {a.out}")

    sys.exit(1 if reprovados else 0)


if __name__ == "__main__":
    main()
