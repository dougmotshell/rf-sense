#!/usr/bin/env python3
"""
camadas.py — entrega o resultado em camadas com procedência declarada (docs/15 §7).

A saída atual do projeto é um mapa ASCII e um PGM. Serve para depurar e não
permite responder à única pergunta que um leitor faz: ISTO ESTÁ CERTO? Para isso
é preciso ver o mapa CONTRA a referência, e ver onde havia dado.

O padrão vem do `gods-eye-view` (docs/14 §14.7): o valor não está numa camada,
está em sobrepor camadas cada uma com a fonte declarada. Aqui são seis, todas
derivadas de arquivos que já existem, todas no mesmo referencial de
mapa_meta.json (D16), e nenhuma dependência nova (D11):

  0  planta do ground truth        data/ground_truth.json
  1  mapa de atenuação             mapa.csv
  2  posições dos APs              aps.json          (fixo vs. estimado)
  3  cobertura de raios            cobertura.csv, diversidade.csv
  4  pontos de coleta visitados    survey JSONL
  5  diferença mapa - referência   camadas 1 e 0

Cada execução escreve também camadas/MANIFESTO.md, que diz de onde cada pixel
veio. Uma camada sem procedência é uma afirmação sem fonte.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from groundtruth import carregar as carregar_gt, rasterizar   # noqa: E402
from reconstruct import salvar_pgm                            # noqa: E402


def celula(origem, passo, nx, ny, x, y):
    ix = int((x - origem[0]) / passo)
    iy = int((y - origem[1]) / passo)
    return (ix, iy) if (0 <= ix < nx and 0 <= iy < ny) else (None, None)


def montar(mapa_dir, gt_path=None, surveys=(), tipos=None):
    d = Path(mapa_dir)
    meta = json.loads((d / "mapa_meta.json").read_text())
    origem = (meta["origem_x"], meta["origem_y"])
    passo, nx, ny = meta["grid"], meta["nx"], meta["ny"]

    mapa = np.loadtxt(d / "mapa.csv", delimiter=",")
    if mapa.ndim == 1:
        mapa = mapa.reshape(1, -1)

    camadas = []
    vazio = lambda: np.zeros((ny, nx))              # noqa: E731

    # --- 0 ground truth
    gt_ras = None
    if gt_path and Path(gt_path).exists():
        gt = carregar_gt(gt_path)
        if tipos:
            gt = dict(gt, paredes=[w for w in gt["paredes"] if w.get("tipo") in tipos])
        gt_ras = np.array(rasterizar(gt, origem, passo, nx, ny), dtype=float)
        camadas.append(("0-referencia", gt_ras, Path(gt_path).name,
                        "paredes medidas com trena, rasterizadas na grade do mapa"
                        + (f" [tipos {sorted(tipos)}]" if tipos else "")))

    # --- 1 atenuação
    camadas.append(("1-atenuacao", mapa, "mapa.csv",
                    f"tomografia por atenuação, {meta.get('n_raios','?')} raios, "
                    f"n_ref={meta.get('n_referencia')}, lam={meta.get('lam')}, "
                    f"mu={meta.get('mu')}, resíduo "
                    f"{meta.get('residuo_relativo', 0)*100:.0f}%"))

    # --- 2 APs
    aps_f = d / "aps.json"
    if aps_f.exists():
        aps = json.loads(aps_f.read_text())
        camada = vazio()
        fixos = 0
        for canal, info in aps.items():
            ix, iy = celula(origem, passo, nx, ny, info["x"], info["y"])
            if ix is None:
                continue                      # AP de vizinho, fora da grade
            fixo = info.get("origem") == "fixo"
            fixos += fixo
            camada[iy, ix] = 1.0 if fixo else 0.5
        dentro = int((camada > 0).sum())
        camadas.append(("2-aps", camada, "aps.json",
                        f"{len(aps)} APs ({fixos} com posição medida, "
                        f"{len(aps)-fixos} estimada); {dentro} caem dentro da grade — "
                        f"os de fora são vizinhos, e os raios deles atravessam a casa. "
                        f"Tom claro = medido, escuro = estimado"))

    # --- 3 cobertura
    for nome, arq, desc in (
        ("3a-cobertura", "cobertura.csv",
         "raios que cruzam cada célula; onde é escuro, o mapa é regularização"),
        ("3b-diversidade", "diversidade.csv",
         "dispersão dos ângulos desses raios (0-1); baixo = raios paralelos"),
    ):
        f = d / arq
        if f.exists():
            v = np.loadtxt(f, delimiter=",")
            camadas.append((nome, v.reshape(ny, nx) if v.ndim == 1 else v, arq, desc))

    # --- 4 pontos de coleta
    if surveys:
        camada = vazio()
        pontos = set()
        for s in surveys:
            with open(s) as fh:
                for linha in fh:
                    if not linha.strip():
                        continue
                    r = json.loads(linha)
                    if "x" not in r or "y" not in r:
                        continue
                    pontos.add((r["x"], r["y"]))
        for (px, py) in pontos:
            ix, iy = celula(origem, passo, nx, ny, px, py)
            if ix is not None:
                camada[iy, ix] += 1.0
        camadas.append(("4-pontos", camada, ", ".join(Path(s).name for s in surveys),
                        f"{len(pontos)} posições onde houve medição — a abertura de "
                        f"medição, que é de onde vem TODA a resolução (docs/14 §14.4)"))

    # --- 5 diferença
    if gt_ras is not None:
        vmax = mapa.max() or 1.0
        dif = np.abs(mapa / vmax - gt_ras)
        camadas.append(("5-diferenca", dif, "mapa.csv - ground truth",
                        "|mapa normalizado - referência|; claro = discordância"))

    return camadas, meta, origem, passo, nx, ny, mapa, gt_ras


RAMPA = " .:-=+*#%@"


def sobrepor(mapa, gt_ras, pontos, aps, ny, nx, origem, passo):
    """Uma vista só, ASCII: massa do mapa + parede real + coleta + AP."""
    vmax = mapa.max() or 1.0
    linhas = []
    for iy in range(ny - 1, -1, -1):
        y = origem[1] + (iy + 0.5) * passo
        s = ""
        for ix in range(nx):
            if aps is not None and aps[iy, ix] > 0:
                s += "A"
            elif pontos is not None and pontos[iy, ix] > 0:
                s += "+"
            elif gt_ras is not None and gt_ras[iy, ix] > 0:
                s += "W"
            else:
                v = mapa[iy, ix] / vmax
                s += RAMPA[min(int(v * (len(RAMPA) - 1) + 0.5), len(RAMPA) - 1)]
        linhas.append(f"{y:5.1f} |{s}|")
    linhas.append("      +" + "-" * nx + "+")
    linhas.append("      'W' parede real   '+' ponto de coleta   'A' AP   sombra = atenuação")
    return "\n".join(linhas)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mapa-dir", default="data/processed")
    p.add_argument("--ground-truth", default="data/ground_truth.json")
    p.add_argument("--survey", nargs="*", default=[], help="JSONL usados na reconstrução")
    p.add_argument("--tipos", default=None, help="filtrar paredes por tipo, ex.: divisoria")
    p.add_argument("--out", default=None, help="diretório das camadas (padrão: <mapa-dir>/camadas)")
    p.add_argument("--pgm-escala", type=int, default=0)
    a = p.parse_args()

    tipos = {t.strip() for t in a.tipos.split(",")} if a.tipos else None
    gt = a.ground_truth if Path(a.ground_truth).exists() else None
    if gt is None:
        print(f"[aviso] {a.ground_truth} não existe — sem camadas 0 e 5. "
              f"A pergunta 'está certo?' fica sem resposta (docs/03 Fase 0).",
              file=sys.stderr)

    camadas, meta, origem, passo, nx, ny, mapa, gt_ras = montar(
        a.mapa_dir, gt, a.survey, tipos)

    destino = Path(a.out) if a.out else Path(a.mapa_dir) / "camadas"
    destino.mkdir(parents=True, exist_ok=True)

    escalas = {}
    for nome, campo, fonte, desc in camadas:
        escalas[nome] = salvar_pgm(np.asarray(campo, dtype=float).ravel(), nx, ny,
                                   destino / f"{nome}.pgm", a.pgm_escala or None)
        np.savetxt(destino / f"{nome}.csv", np.asarray(campo, dtype=float),
                   delimiter=",", fmt="%.4f")

    por_nome = {n: c for n, c, _, _ in camadas}
    print("=" * 74)
    print("CAMADAS SOBREPOSTAS  (docs/15 §7)")
    print("=" * 74)
    print(sobrepor(mapa, gt_ras, por_nome.get("4-pontos"), por_nome.get("2-aps"),
                   ny, nx, origem, passo))

    linhas_man = [
        "# Manifesto das camadas",
        "",
        "Gerado por `src/camadas.py`. Todas no mesmo referencial de `mapa_meta.json`",
        f"— origem ({origem[0]:.2f}, {origem[1]:.2f}), célula {passo} m, grade {nx}x{ny} —",
        "então sobrepõem-se pixel a pixel em qualquer visualizador.",
        "",
        f"Modo da coleta: `{meta.get('modo', 'não declarado')}`"
        + ("" if meta.get("modo_verificado", True)
           else "  **backend nunca verificado contra hardware real**"),
        "",
        "| camada | arquivo | procedência | o que é |",
        "|---|---|---|---|",
    ]
    for nome, _, fonte, desc in camadas:
        linhas_man.append(f"| {nome} | `{nome}.pgm` · `{nome}.csv` | `{fonte}` | {desc} |")
    linhas_man += [
        "",
        "## Como ler",
        "",
        "Abra `1-atenuacao.pgm` e `0-referencia.pgm` no mesmo visualizador e alterne.",
        "Onde `3a-cobertura.pgm` está escuro, o que aparece na camada 1 é",
        "regularização, não medição — por mais convincente que pareça. `5-diferenca.pgm`",
        "já mostra a discordância direta, e `4-pontos.pgm` mostra a abertura de medição",
        "que produziu tudo isso.",
        "",
        "Sem largura de banda a resolução não vem do algoritmo, vem da camada 4:",
        "cada ponto novo é resolução nova (docs/14 §14.4).",
    ]
    (destino / "MANIFESTO.md").write_text("\n".join(linhas_man) + "\n")

    print(f"\n{len(camadas)} camadas -> {destino}/")
    for nome, _, fonte, _ in camadas:
        print(f"  {nome:16} <- {fonte}")
    print(f"  MANIFESTO.md     <- procedência de cada camada")


if __name__ == "__main__":
    main()
