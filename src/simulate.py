#!/usr/bin/env python3
"""
simulate.py — gera um survey sintético a partir de uma planta conhecida.

Serve para validar o pipeline SEM sair da cadeira: você sabe a resposta certa,
então dá para saber se o reconstruct.py está funcionando antes de gastar um fim
de semana medindo a casa de verdade.

Modelo: perda de espaço livre + atenuação por parede atravessada + ruído.
"""

import argparse
import json
import math
import random
from pathlib import Path

# Planta de exemplo: um apartamento de 8 x 6 m com três paredes internas.
# Cada parede é um segmento (x0, y0, x1, y1, atenuação_dB).
PLANTA_EXEMPLO = [
    # contorno externo
    (0.0, 0.0, 8.0, 0.0, 12.0),
    (8.0, 0.0, 8.0, 6.0, 12.0),
    (8.0, 6.0, 0.0, 6.0, 12.0),
    (0.0, 6.0, 0.0, 0.0, 12.0),
    # divisórias internas
    (3.5, 0.0, 3.5, 4.2, 6.0),   # parede vertical com vão de porta em cima
    (3.5, 6.0, 3.5, 5.2, 6.0),
    (3.5, 3.0, 8.0, 3.0, 6.0),   # parede horizontal do quarto
]

# APs: alguns dentro, alguns "do vizinho" (fora do apartamento).
APS_EXEMPLO = [
    ("meu-roteador",  1.0,  5.0, -30.0),
    ("vizinho-norte", 4.0,  9.5, -34.0),
    ("vizinho-sul",   5.0, -3.0, -32.0),
    ("vizinho-leste", 12.0, 2.0, -33.0),
    ("vizinho-oeste", -4.0, 3.0, -31.0),
    ("corredor",      -2.0, 6.5, -35.0),
    ("andar-cima",    2.0,  1.0, -38.0),
    ("andar-baixo",   6.5,  5.0, -37.0),
]


def intersecta(p0, p1, seg):
    """Os segmentos p0-p1 e seg se cruzam?"""
    (x1, y1), (x2, y2) = p0, p1
    x3, y3, x4, y4 = seg[0], seg[1], seg[2], seg[3]
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return False
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / den
    return 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0


def rssi_sintetico(ap, ponto, planta, ruido, rng):
    dx, dy = ponto[0] - ap[1], ponto[1] - ap[2]
    d = max(math.hypot(dx, dy), 0.5)
    rssi = ap[3] - 20.0 * math.log10(d)                     # espaço livre
    for seg in planta:
        if intersecta((ap[1], ap[2]), ponto, seg):
            rssi -= seg[4]                                  # atravessou parede
    return rssi + rng.gauss(0, ruido)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="data/raw/sim.jsonl")
    p.add_argument("--step", type=float, default=1.0, help="espaçamento da grade em metros")
    p.add_argument("--samples", type=int, default=12, help="amostras por ponto")
    p.add_argument("--noise", type=float, default=2.0, help="desvio padrão do ruído em dB")
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()

    rng = random.Random(a.seed)
    destino = Path(a.out)
    destino.parent.mkdir(parents=True, exist_ok=True)

    # pontos de medição: grade interna ao apartamento, com margem das paredes
    pontos = []
    y = 0.5
    while y <= 5.5:
        x = 0.5
        while x <= 7.5:
            pontos.append((x, y))
            x += a.step
        y += a.step

    n = 0
    with open(destino, "w") as f:
        for (px, py) in pontos:
            for _ in range(a.samples):
                for ap in APS_EXEMPLO:
                    f.write(json.dumps({
                        "ts": 0.0, "x": px, "y": py, "z": 1.0,
                        "ap": ap[0],
                        "rssi_dbm": round(rssi_sintetico(ap, (px, py), PLANTA_EXEMPLO,
                                                         a.noise, rng), 2),
                        "freq_mhz": 2412, "chan": 1, "label": "sim",
                    }) + "\n")
                    n += 1

    print(f"{len(pontos)} pontos x {a.samples} amostras x {len(APS_EXEMPLO)} APs "
          f"= {n} linhas -> {destino}")
    print("\nPlanta usada (o que a reconstrução deveria recuperar):")
    print("  contorno 8 x 6 m")
    print("  parede vertical   em x=3.5 (com vão de porta entre y=4.2 e y=5.2)")
    print("  parede horizontal em y=3.0, de x=3.5 a x=8.0")
    print(f"\nAgora: python3 src/reconstruct.py {destino}")


if __name__ == "__main__":
    main()
