#!/usr/bin/env python3
"""
compare.py — avalia o mapa reconstruído contra o ground truth (fases 0 + 2).

Fecha o ciclo do projeto: sem isto, "o mapa ficou bom" é opinião. Aqui vira número.

Duas famílias de métrica, porque uma só engana:

  SOBREPOSIÇÃO (IoU, precisão, recall, F1) — quantas células preditas como parede
  realmente são parede. Penaliza duramente um mapa borrado, MESMO que ele esteja
  centrado no lugar certo. Um erro de meia célula já zera a interseção.

  PROXIMIDADE (distância às paredes) — quão longe, em metros, as células preditas
  estão da parede real mais próxima. É a métrica honesta para este projeto: a
  tomografia RF produz manchas, e o que importa é se a mancha está no lugar certo.

Compare sempre contra o baseline aleatório que o script imprime. Um F1 de 0,35 não
diz nada sozinho; dizer que ele é 3x o acaso, sim.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from groundtruth import carregar, dist_a_parede, rasterizar


def carregar_mapa(diretorio):
    d = Path(diretorio)
    csv, meta = d / "mapa.csv", d / "mapa_meta.json"
    if not csv.exists():
        sys.exit(f"não encontrei {csv} — rode src/reconstruct.py antes")
    if not meta.exists():
        sys.exit(f"não encontrei {meta} — regenere o mapa com a versão atual do reconstruct.py")
    mapa = np.loadtxt(csv, delimiter=",")
    if mapa.ndim == 1:
        mapa = mapa.reshape(1, -1)
    with open(meta) as f:
        return mapa, json.load(f)


def campo_de_distancia(gt, origem, grid, nx, ny):
    """Distância de cada centro de célula à parede real mais próxima, em metros."""
    d = np.zeros((ny, nx))
    for iy in range(ny):
        cy = origem[1] + (iy + 0.5) * grid
        for ix in range(nx):
            cx = origem[0] + (ix + 0.5) * grid
            d[iy, ix] = dist_a_parede(gt, cx, cy)
    return d


def render_lado_a_lado(pred, real, ny, nx, origem, grid):
    """'#' acerto  'o' falso positivo  '.' parede não detectada  ' ' vazio correto."""
    linhas = []
    for iy in range(ny - 1, -1, -1):
        y = origem[1] + (iy + 0.5) * grid
        s = ""
        for ix in range(nx):
            p, r = pred[iy, ix], real[iy, ix]
            s += "#" if (p and r) else "o" if p else "." if r else " "
        linhas.append(f"{y:5.1f} |{s}|")
    linhas.append("      +" + "-" * nx + "+")
    linhas.append("      '#' parede detectada   'o' falso positivo   '.' parede perdida")
    return "\n".join(linhas)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mapa_dir", help="diretório com mapa.csv e mapa_meta.json")
    p.add_argument("ground_truth", help="ground_truth.json")
    p.add_argument("--limiar", type=float, default=None,
                   help="densidade mínima (dB/m) para considerar parede. Por padrão usa "
                        "percentil casado: prevê tantas células quantas o GT tem")
    p.add_argument("--tipos", default=None,
                   help="avaliar apenas paredes destes tipos, separados por vírgula "
                        "(ex.: 'divisoria'). Paredes externas raramente são recuperáveis: "
                        "todos os pontos ficam do lado de dentro e nenhum raio as discrimina "
                        "(ver docs/10). Filtrá-las dá a métrica honesta do que é detectável.")
    p.add_argument("--tolerancia", type=float, default=None,
                   help="raio (m) para contar um acerto como próximo (padrão: 1 célula)")
    a = p.parse_args()

    mapa, meta = carregar_mapa(a.mapa_dir)
    gt = carregar(a.ground_truth)

    filtro = None
    if a.tipos:
        filtro = {t.strip() for t in a.tipos.split(",")}
        antes = len(gt["paredes"])
        gt = dict(gt, paredes=[w for w in gt["paredes"] if w.get("tipo") in filtro])
        if not gt["paredes"]:
            sys.exit(f"nenhuma parede do tipo {sorted(filtro)} no ground truth")
        print(f"Filtro de tipos: {sorted(filtro)} — {len(gt['paredes'])}/{antes} paredes\n")

    ny, nx = mapa.shape
    grid = meta["grid"]
    origem = (meta["origem_x"], meta["origem_y"])
    tol = a.tolerancia if a.tolerancia is not None else grid

    real = np.array(rasterizar(gt, origem, grid, nx, ny), dtype=bool)
    n_real = int(real.sum())
    if n_real == 0:
        sys.exit("o ground truth não intersecta a área do mapa — confira o referencial (0,0)")

    # Binarização: por padrão, prever exatamente tantas células quantas o GT tem.
    # Isso remove o grau de liberdade do limiar e torna precisão e recall comparáveis.
    if a.limiar is not None:
        limiar = a.limiar
        modo = f"limiar fixo {limiar:.2f} dB/m"
    else:
        frac = n_real / real.size
        limiar = float(np.quantile(mapa, 1.0 - frac))
        modo = f"percentil casado (top {frac*100:.0f}% das células)"
    pred = mapa >= limiar
    n_pred = int(pred.sum())

    tp = int((pred & real).sum())
    fp = int((pred & ~real).sum())
    fn = int((~pred & real).sum())
    precisao = tp / n_pred if n_pred else 0.0
    recall = tp / n_real if n_real else 0.0
    f1 = 2 * precisao * recall / (precisao + recall) if (precisao + recall) else 0.0
    iou = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0

    # baseline: prever n_pred células ao acaso
    base_prec = n_real / real.size
    base_f1 = (2 * base_prec * (n_pred / real.size)
               / (base_prec + n_pred / real.size)) if n_pred else 0.0

    dist = campo_de_distancia(gt, origem, grid, nx, ny)
    d_pred = dist[pred] if n_pred else np.array([0.0])
    # onde o mapa concentra massa, ponderado pela densidade
    peso = mapa.ravel()
    d_pond = float((dist.ravel() * peso).sum() / peso.sum()) if peso.sum() > 0 else float("nan")
    d_aleatorio = float(dist.mean())

    print("=" * 66)
    print("AVALIAÇÃO DO MAPA CONTRA O GROUND TRUTH")
    print("=" * 66)
    print(f"Grade          : {nx} x {ny} células de {grid} m")
    print(f"Reconstrução   : n_ref={meta.get('n_referencia')}  lam={meta.get('lam')}  "
          f"mu={meta.get('mu')}  raios={meta.get('n_raios')}  "
          f"resíduo={meta.get('residuo_relativo', 0)*100:.0f}%")
    print(f"Binarização    : {modo}  ->  limiar {limiar:.3f} dB/m")
    print(f"Células parede : {n_real} reais / {n_pred} previstas"
          + (f"   [somente tipos {sorted(filtro)}]" if filtro else ""))

    print("\n-- Sobreposição (dura com mapas borrados) " + "-" * 24)
    print(f"  Precisão : {precisao*100:5.1f}%   (acaso: {base_prec*100:.1f}%)")
    print(f"  Recall   : {recall*100:5.1f}%")
    print(f"  F1       : {f1:5.3f}     (acaso: {base_f1:.3f}"
          f" -> {f1/base_f1:.1f}x melhor)" if base_f1 else f"  F1       : {f1:5.3f}")
    print(f"  IoU      : {iou:5.3f}")

    print("\n-- Proximidade (a métrica honesta aqui) " + "-" * 26)
    print(f"  Distância mediana das células previstas à parede real : {np.median(d_pred):.2f} m")
    print(f"  Distância média, ponderada pela densidade do mapa     : {d_pond:.2f} m")
    print(f"  Mesma medida para uma célula ao acaso                 : {d_aleatorio:.2f} m")
    dentro = float((d_pred <= tol).mean()) * 100 if n_pred else 0.0
    print(f"  Previsões a menos de {tol:.2f} m de uma parede real      : {dentro:.0f}%")

    print("\n" + "=" * 66)
    print(render_lado_a_lado(pred, real, ny, nx, origem, grid))

    print("\n-- Leitura " + "-" * 55)
    if d_pond < d_aleatorio * 0.6 and dentro > 50:
        print("  O mapa concentra massa perto das paredes reais. Funcionou.")
    elif d_pond < d_aleatorio * 0.85:
        print("  Sinal presente, mas fraco. Mais pontos de coleta é o caminho,")
        print("  não ajuste de parâmetro.")
    else:
        print("  O mapa não está melhor que o acaso. Antes de mexer em parâmetros,")
        print("  verifique: referencial (0,0) igual nos dois arquivos? APs com rmse")
        print("  alto? orientação do dispositivo constante durante a coleta?")
    if iou < 0.3 and dentro > 50:
        print("  IoU baixo com boa proximidade é o resultado ESPERADO: as manchas")
        print("  estão no lugar certo, mas espalhadas. Ver docs/07 §9.")
    print()


if __name__ == "__main__":
    main()
