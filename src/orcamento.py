#!/usr/bin/env python3
"""
orcamento.py — orçamento de resolução: quantos pontos vale a pena medir (docs/15 §4).

O projeto afirma resolução de 0,5 a 2 m e usa célula de 0,5 m por padrão. Os dois
números são plausíveis e nenhum estava derivado. Com RSSI de beacon a largura de
banda é nula, então a resolução em alcance é INEXISTENTE (docs/14 §14.4) e a
resolução efetiva é fixada por três coisas, todas sob controle de quem mede:

  1. o espaçamento dos pontos de coleta  -> a abertura de medição
  2. a diversidade angular obtida        -> se a abertura é real ou degenerada
  3. a força da regularização            -> quanto do mapa é dado e quanto é suavidade

Este script varre a primeira e mede o efeito nas outras duas, usando o simulador:
para cada espaçamento, gera o survey, reconstrói, avalia contra a planta conhecida
e imprime a curva. O resultado é uma escolha de --step e --grid JUSTIFICADA, feita
antes de gastar o fim de semana medindo — em vez de herdada de um padrão.

Limitação assumida, a mesma de D10: o simulador usa o mesmo modelo direto que o
reconstrutor inverte. A curva é um TETO, não uma previsão. Espere menos em campo.
"""

import argparse
import json
import math
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compare                                                  # noqa: E402
import reconstruct                                              # noqa: E402
import simulate                                                 # noqa: E402
from groundtruth import carregar as carregar_gt, rasterizar      # noqa: E402


def lista_float(s):
    return [float(v) for v in s.replace(";", ",").split(",") if v.strip()]


def gerar_medidas(step, amostras, ruido, seed, limites=(0.5, 7.5, 0.5, 5.5)):
    """
    Survey sintético direto em memória, no formato que reconstruir() espera.
    Sem passar por arquivo: a varredura roda dezenas de vezes.
    """
    rng = random.Random(seed)
    x0, x1, y0, y1 = limites
    pontos = []
    y = y0
    while y <= y1 + 1e-9:
        x = x0
        while x <= x1 + 1e-9:
            pontos.append((x, y))
            x += step
        y += step

    # Os quatro cantos entram SEMPRE, independente do step. Sem isso a extensão
    # medida muda com o espaçamento (step 1,5 para em x=6,5; step 1,0 chega a
    # 7,5), a moldura da grade muda com ela, e máscaras de formas diferentes não
    # se intersectam — a régua comum da passada 2 sairia vazia. Andar até os
    # cantos também é o que se faria em campo, então o custo é honesto: no pior
    # caso quatro pontos a mais.
    for canto in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        if canto not in pontos:
            pontos.append(canto)

    medidas = []
    for (px, py) in pontos:
        for ap in simulate.APS_EXEMPLO:
            vals = [simulate.rssi_sintetico(ap, (px, py), simulate.PLANTA_EXEMPLO,
                                            ruido, rng) for _ in range(amostras)]
            medidas.append({"ponto": np.array([px, py], dtype=float),
                            "ap": ap[0], "freq": 2412,
                            "rssi": float(np.median(vals)),
                            "n": len(vals), "std": float(np.std(vals))})
    return medidas, len(pontos)


def uma_rodada(step, grid, amostras, ruido, seed, gt, n_ref, lam, mu,
               min_raios, min_div):
    medidas, n_pontos = gerar_medidas(step, amostras, ruido, seed)
    if n_pontos < 6:
        return None
    try:
        r = reconstruct.reconstruir(medidas, grid=grid, n_referencia=n_ref,
                                    lam=lam, mu=mu, verbose=False,
                                    min_raios=min_raios, min_diversidade=min_div)
    except ValueError:
        return None

    origem = (float(r["origem"][0]), float(r["origem"][1]))
    nx, ny = r["nx"], r["ny"]
    mapa = r["mapa"].reshape(ny, nx)
    real = np.array(rasterizar(gt, origem, grid, nx, ny), dtype=bool)
    if real.sum() == 0:
        return None
    dist = compare.campo_de_distancia(gt, origem, grid, nx, ny)

    return {"step": step, "grid": grid, "n_pontos": n_pontos,
            "n_raios": int(r["meta"]["n_raios"]),
            "frac_coberta": float(r["mascara"].mean()),
            "div_mediana": float(np.median(r["diversidade"])),
            "residuo": r["residuo"], "subdeterminado": r["subdeterminado"],
            # guardados para a segunda passada: a máscara comum
            "_mapa": mapa, "_real": real, "_dist": dist, "_mascara": r["mascara"],
            "_forma": (ny, nx)}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--steps", type=lista_float, default=[0.5, 0.75, 1.0, 1.5, 2.0],
                   help="espaçamentos de coleta a varrer, em metros")
    p.add_argument("--grids", type=lista_float, default=[0.5],
                   help="tamanhos de célula a varrer, em metros")
    p.add_argument("--samples", type=int, default=12, help="amostras por ponto")
    p.add_argument("--noise", type=float, default=2.0, help="ruído em dB")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-referencia", type=float, default=2.6)
    p.add_argument("--lam", type=float, default=0.05)
    p.add_argument("--mu", type=float, default=0.5)
    p.add_argument("--min-raios", type=int, default=5)
    p.add_argument("--min-diversidade", type=float, default=0.25)
    p.add_argument("--min-cobertura-aprov", type=float, default=0.7,
                   help="fração mínima da área coberta para a configuração ser "
                        "aprovada. Sem isto, medir menos 'vence' por encolher a "
                        "máscara para a parte fácil da casa")
    p.add_argument("--ground-truth", default="data/ground_truth.example.json")
    p.add_argument("--tipos", default="divisoria",
                   help="tipos de parede a avaliar (D15: externas não são recuperáveis)")
    p.add_argument("--out", default=None, help="salvar a curva em JSON")
    a = p.parse_args()

    gt = carregar_gt(a.ground_truth)
    if a.tipos:
        tipos = {t.strip() for t in a.tipos.split(",")}
        gt = dict(gt, paredes=[w for w in gt["paredes"] if w.get("tipo") in tipos])
        if not gt["paredes"]:
            sys.exit(f"nenhuma parede do tipo {sorted(tipos)} no ground truth")

    print("=" * 88)
    print("ORÇAMENTO DE RESOLUÇÃO  (docs/15 §4)")
    print("=" * 88)
    print(f"Planta      : {a.ground_truth}  [{len(gt['paredes'])} paredes"
          + (f", tipos {sorted(tipos)}" if a.tipos else "") + "]")
    print(f"Ruído       : {a.noise} dB · {a.samples} amostras/ponto · seed {a.seed}")
    print(f"Resolução em alcance do RSSI: INEXISTENTE (B -> 0). Toda a resolução")
    print(f"abaixo vem do cruzamento de raios, ou seja de caminhar (docs/14 §14.4).")
    print()

    # ---------------------------------------------------------------- passada 1
    # Roda todas as configurações e GUARDA os mapas. Nada é julgado ainda: a
    # comparação exige uma régua que só existe depois de conhecer todas.
    brutos = []
    for grid in a.grids:
        for step in a.steps:
            r = uma_rodada(step, grid, a.samples, a.noise, a.seed, gt,
                           a.n_referencia, a.lam, a.mu, a.min_raios, a.min_diversidade)
            if r is None:
                print(f"  step {step:.2f} grid {grid:.2f}: pontos insuficientes "
                      f"ou sistema inviável")
                continue
            brutos.append(r)

    if not brutos:
        sys.exit("nada reconstruído")

    # ---------------------------------------------------------------- passada 2
    # A ARMADILHA que esta seção existe para evitar: avaliar cada configuração
    # sob a PRÓPRIA máscara de cobertura faz o resultado MELHORAR quando se mede
    # menos. Com poucos pontos a máscara encolhe para o miolo fácil da casa, as
    # bordas difíceis saem da conta, e a métrica sobe. Máscaras de tamanhos
    # diferentes não são comparáveis entre si — é o mesmo grau de liberdade
    # escondido que D14 eliminou no limiar, reaparecendo no espaço.
    #
    # Então há três colunas, e cada uma responde a uma pergunta diferente:
    #   F1@propria — funciona onde HÁ dado?          (não compara configurações)
    #   F1@comum   — qual configuração é melhor?     (régua idêntica para todas)
    #   cob%       — quanto da casa você cobriu?     (o que a máscara esconde)
    # Aprovar exige as três, porque cada uma sozinha é enganável.
    comuns = {}
    for grid in {r["grid"] for r in brutos}:
        do_grid = [r for r in brutos if r["grid"] == grid]
        formas = {r["_forma"] for r in do_grid}
        if len(formas) == 1:
            m = np.ones(formas.pop(), dtype=bool)
            for r in do_grid:
                m &= r["_mascara"]
            comuns[grid] = m
        else:
            comuns[grid] = None      # grades de formas diferentes: sem régua comum

    cab = (f"{'step':>5} {'grid':>5} {'pontos':>7} {'raios':>6} {'cob%':>6} "
           f"{'div':>5} {'F1@prop':>8} {'F1@comum':>9} {'xacaso':>7} "
           f"{'d_pond':>7} {'d/acaso':>8}  aprov")
    print(cab)
    print("-" * len(cab))

    linhas = []
    for r in brutos:
        mapa, real, dist = r["_mapa"], r["_real"], r["_dist"]
        propria = compare.avaliar(mapa, real, dist, mascara=r["_mascara"])
        comum_m = comuns.get(r["grid"])
        comum = (compare.avaliar(mapa, real, dist, mascara=comum_m)
                 if comum_m is not None and comum_m.any() else None)
        if propria is None:
            continue
        base = comum or propria
        aprovado = (base["razao_dist"] < 0.6 and base["ganho_f1"] > 2.0
                    and r["frac_coberta"] >= a.min_cobertura_aprov)
        linhas.append({k: v for k, v in r.items() if not k.startswith("_")}
                      | {"f1_propria": propria["f1"],
                         "f1_comum": None if comum is None else comum["f1"],
                         "ganho_f1": base["ganho_f1"], "d_pond": base["d_pond"],
                         "razao_dist": base["razao_dist"],
                         "regua": "comum" if comum else "propria",
                         "aprovado": bool(aprovado)})
        f1c = "     n/a" if comum is None else f"{comum['f1']:9.3f}"
        print(f"{r['step']:5.2f} {r['grid']:5.2f} {r['n_pontos']:7d} {r['n_raios']:6d} "
              f"{r['frac_coberta']*100:6.1f} {r['div_mediana']:5.2f} "
              f"{propria['f1']:8.3f} {f1c} {base['ganho_f1']:7.1f} "
              f"{base['d_pond']:7.2f} {base['razao_dist']:8.2f}  "
              f"{'SIM' if aprovado else '-'}"
              + ("  [subdet.]" if r["subdeterminado"] else ""))

    for grid, m in sorted(comuns.items()):
        if m is not None:
            print(f"\n  régua comum (grade {grid:.2f} m): {int(m.sum())} células cobertas "
                  f"por TODAS as configurações, de {m.size}")

    if not linhas:
        sys.exit("\nnada avaliado")

    print("\n-- Leitura " + "-" * 76)
    print("  F1@prop  sob a própria máscara — NÃO compare configurações por esta coluna:")
    print("           medir menos encolhe a máscara para o miolo fácil e infla o número.")
    print("  F1@comum sob a régua comum a todas — é por esta que se compara.")
    print(f"  aprovar exige, além do critério da Fase 2, cobertura >= "
          f"{a.min_cobertura_aprov*100:.0f}%.")

    aprovados = [l for l in linhas if l["aprovado"]]
    if aprovados:
        barato = max(aprovados, key=lambda l: l["step"])
        melhor = max(aprovados, key=lambda l: (l["f1_comum"] or l["f1_propria"]))
        print(f"\n  MENOR ESFORÇO QUE PASSA o critério da Fase 2:")
        print(f"    step {barato['step']:.2f} m  ->  {barato['n_pontos']} pontos de coleta, "
              f"grade de {barato['grid']:.2f} m")
        f1b = barato["f1_comum"] or barato["f1_propria"]
        print(f"    F1@comum {f1b:.3f} ({barato['ganho_f1']:.1f}x o acaso), "
              f"d_pond {barato['d_pond']:.2f} m ({barato['razao_dist']:.2f}x o acaso), "
              f"cobertura {barato['frac_coberta']*100:.0f}%")
        print(f"    ~{barato['n_pontos'] * 1.5:.0f} min de campo a 1,5 min por ponto")
        f1m = melhor["f1_comum"] or melhor["f1_propria"]
        if melhor["step"] != barato["step"]:
            print(f"\n  MELHOR RESULTADO (não o mais barato):")
            print(f"    step {melhor['step']:.2f} m -> {melhor['n_pontos']} pontos, "
                  f"F1@comum {f1m:.3f}, cobertura {melhor['frac_coberta']*100:.0f}%")
            ganho = (f1m - f1b) / max(f1b, 1e-9) * 100
            custo = (melhor["n_pontos"] - barato["n_pontos"]) * 1.5
            print(f"    custa +{custo:.0f} min de campo por +{ganho:.0f}% de F1 — "
                  f"a decisão é sua, mas agora é informada")
    else:
        print("\n  NENHUMA configuração passou o critério. Antes de mexer em lam/mu,")
        print("  reduza --noise: se nem no simulador passa, o problema é o orçamento")
        print("  de erro, não a regularização.")

    piores_div = [l for l in linhas if l["div_mediana"] < a.min_diversidade]
    if piores_div:
        print(f"\n  {len(piores_div)} configuração(ões) com diversidade angular mediana")
        print(f"  abaixo de {a.min_diversidade}: ali os raios são quase paralelos e mais")
        print("  amostras do mesmo lugar não ajudam. O que falta é ÂNGULO, não quantidade.")

    print("\n  Lembrete de D10: o simulador usa o mesmo modelo direto que o reconstrutor")
    print("  inverte. Isto é um TETO da matemática, não uma previsão da física.")

    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(linhas, indent=2))
        print(f"\n  curva salva em {a.out}")


if __name__ == "__main__":
    main()
