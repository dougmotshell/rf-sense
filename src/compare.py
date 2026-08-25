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


def carregar_cobertura(diretorio, meta, min_raios=None, min_div=None):
    """
    Máscara das células sustentadas por dados (docs/15 §3).

    Avaliar fora dela mistura duas coisas diferentes — falha de reconstrução e
    ausência de medição — e nenhuma métrica consegue separar as duas depois.
    É D15 aplicado à cobertura em vez de ao tipo de parede.
    """
    d = Path(diretorio)
    cont_f, div_f = d / "cobertura.csv", d / "diversidade.csv"
    if not cont_f.exists() or not div_f.exists():
        sys.exit(f"não encontrei cobertura.csv/diversidade.csv em {d} — "
                 f"regenere o mapa com a versão atual do reconstruct.py")
    cont = np.loadtxt(cont_f, delimiter=",")
    div = np.loadtxt(div_f, delimiter=",")
    if cont.ndim == 1:
        cont, div = cont.reshape(1, -1), div.reshape(1, -1)
    mr = min_raios if min_raios is not None else meta.get("min_raios", 5)
    md = min_div if min_div is not None else meta.get("min_diversidade", 0.25)
    return (cont >= mr) & (div >= md), mr, md


def avaliar(mapa, real, dist, limiar=None, mascara=None):
    """
    Métricas do mapa contra o ground truth rasterizado. Devolve dict.

    Separada do main porque orcamento.py precisa dela centenas de vezes, sem
    imprimir nada. `mascara` restringe TUDO — predição, referência e baseline —
    às células cobertas, para que o acaso siga sendo comparável.
    """
    if mascara is None:
        mascara = np.ones_like(real, dtype=bool)
    n_aval = int(mascara.sum())
    if n_aval == 0:
        return None
    real_m = real & mascara
    n_real = int(real_m.sum())
    if n_real == 0:
        return None

    vals = mapa[mascara]
    if limiar is None:
        frac = n_real / n_aval
        limiar = float(np.quantile(vals, 1.0 - frac))
        modo = f"percentil casado (top {frac*100:.0f}% das células avaliadas)"
    else:
        modo = f"limiar fixo {limiar:.2f} dB/m"
    pred = (mapa >= limiar) & mascara
    n_pred = int(pred.sum())

    tp = int((pred & real_m).sum())
    fp = int((pred & ~real_m).sum())
    fn = int((~pred & real_m).sum())
    precisao = tp / n_pred if n_pred else 0.0
    recall = tp / n_real if n_real else 0.0
    f1 = 2 * precisao * recall / (precisao + recall) if (precisao + recall) else 0.0
    iou = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0

    base_prec = n_real / n_aval
    base_rec = n_pred / n_aval
    base_f1 = (2 * base_prec * base_rec / (base_prec + base_rec)) if n_pred else 0.0

    peso = np.where(mascara, mapa, 0.0).ravel()
    d_pred = dist[pred] if n_pred else np.array([0.0])
    d_pond = float((dist.ravel() * peso).sum() / peso.sum()) if peso.sum() > 0 else float("nan")
    d_acaso = float(dist[mascara].mean())

    return {"limiar": limiar, "modo": modo, "n_aval": n_aval, "n_real": n_real,
            "n_pred": n_pred, "precisao": precisao, "recall": recall, "f1": f1,
            "iou": iou, "base_prec": base_prec, "base_f1": base_f1,
            "ganho_f1": (f1 / base_f1) if base_f1 else float("nan"),
            "d_mediana": float(np.median(d_pred)), "d_pond": d_pond,
            "d_acaso": d_acaso, "pred": pred, "real": real_m,
            "razao_dist": (d_pond / d_acaso) if d_acaso else float("nan")}


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
    p.add_argument("--cobertura", action="store_true",
                   help="avaliar SÓ as células sustentadas por dados (docs/15 §3). "
                        "Sem isto, a métrica mistura falha de reconstrução com "
                        "ausência de medição e não há como separar as duas.")
    p.add_argument("--min-raios", type=int, default=None,
                   help="com --cobertura, sobrescreve o mínimo de raios por célula")
    p.add_argument("--min-diversidade", type=float, default=None,
                   help="com --cobertura, sobrescreve a diversidade angular mínima")
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
    if int(real.sum()) == 0:
        sys.exit("o ground truth não intersecta a área do mapa — confira o referencial (0,0)")

    masc, mr, md = (None, None, None)
    if a.cobertura:
        masc, mr, md = carregar_cobertura(a.mapa_dir, meta, a.min_raios, a.min_diversidade)

    dist = campo_de_distancia(gt, origem, grid, nx, ny)
    tol = a.tolerancia if a.tolerancia is not None else grid

    r = avaliar(mapa, real, dist, limiar=a.limiar, mascara=masc)
    if r is None:
        sys.exit("nenhuma célula avaliável: a máscara de cobertura não intersecta o "
                 "ground truth. Colete mais pontos, ou baixe --min-raios/--min-diversidade.")

    pred, real_m = r["pred"], r["real"]
    d_pred = dist[pred] if r["n_pred"] else np.array([0.0])
    dentro = float((d_pred <= tol).mean()) * 100 if r["n_pred"] else 0.0

    print("=" * 66)
    print("AVALIAÇÃO DO MAPA CONTRA O GROUND TRUTH")
    print("=" * 66)
    print(f"Grade          : {nx} x {ny} células de {grid} m")
    print(f"Reconstrução   : n_ref={meta.get('n_referencia')}  lam={meta.get('lam')}  "
          f"mu={meta.get('mu')}  raios={meta.get('n_raios')}  "
          f"resíduo={meta.get('residuo_relativo', 0)*100:.0f}%")
    print(f"Binarização    : {r['modo']}  ->  limiar {r['limiar']:.3f} dB/m")
    if masc is not None:
        print(f"Máscara        : cobertura ligada — {r['n_aval']}/{real.size} células "
              f"({r['n_aval']/real.size*100:.0f}%) com >= {mr} raios e "
              f"diversidade >= {md:.2f}")
    else:
        print(f"Máscara        : NENHUMA — avaliando as {real.size} células, inclusive "
              f"as sem dado. Use --cobertura.")
    print(f"Células parede : {r['n_real']} reais / {r['n_pred']} previstas"
          + (f"   [somente tipos {sorted(filtro)}]" if filtro else ""))

    print("\n-- Sobreposição (dura com mapas borrados) " + "-" * 24)
    print(f"  Precisão : {r['precisao']*100:5.1f}%   (acaso: {r['base_prec']*100:.1f}%)")
    print(f"  Recall   : {r['recall']*100:5.1f}%")
    if r["base_f1"]:
        print(f"  F1       : {r['f1']:5.3f}     (acaso: {r['base_f1']:.3f}"
              f" -> {r['ganho_f1']:.1f}x melhor)")
    else:
        print(f"  F1       : {r['f1']:5.3f}")
    print(f"  IoU      : {r['iou']:5.3f}")

    print("\n-- Proximidade (a métrica honesta aqui) " + "-" * 26)
    print(f"  Distância mediana das células previstas à parede real : {r['d_mediana']:.2f} m")
    print(f"  Distância média, ponderada pela densidade do mapa     : {r['d_pond']:.2f} m")
    print(f"  Mesma medida para uma célula ao acaso                 : {r['d_acaso']:.2f} m")
    print(f"  Previsões a menos de {tol:.2f} m de uma parede real      : {dentro:.0f}%")

    print("\n" + "=" * 66)
    print(render_lado_a_lado(pred, real_m, ny, nx, origem, grid))

    print("\n-- Leitura " + "-" * 55)
    d_pond, d_aleatorio, iou = r["d_pond"], r["d_acaso"], r["iou"]
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
    if masc is None:
        print("\n  Rode de novo com --cobertura: parte do que está sendo cobrado do")
        print("  mapa é área onde nenhum raio passou, e isso não é erro dele.")
    print()


if __name__ == "__main__":
    main()
