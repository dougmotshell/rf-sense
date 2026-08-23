#!/usr/bin/env python3
"""
reconstruct.py — tomografia RF por atenuação (fase 2).

Ideia, emprestada da tomografia de raios-X:

  Cada par (AP, ponto de medição) é um RAIO atravessando a casa. O sinal recebido
  é menor do que seria em espaço livre por causa do que há no caminho — paredes,
  principalmente. Esse "excesso de atenuação" é a integral de linha de uma
  densidade desconhecida ao longo do raio:

      excesso_dB(raio_i)  =  soma_j  M[i,j] * densidade[j]

  onde M[i,j] é o comprimento do raio i dentro da célula j da grade. Com raios
  suficientes cruzando em ângulos diferentes, o sistema é invertível.

  Paredes atenuam muito; ar quase nada. Logo o mapa de densidade e' aproximadamente
  a planta baixa.

Duas etapas:
  1. Localizar os APs (posições desconhecidas) por ajuste log-distance.
  2. Resolver o problema inverso com regularização de Tikhonov + suavidade,
     impondo densidade >= 0 (não existe parede que amplifique sinal).

Sem dependências além de numpy.
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

# Expoente de perda de percurso usado como REFERÊNCIA ao calcular o excesso de
# atenuação: tudo que atenua além dele é atribuído à densidade do mapa.
#
# 2.0 = espaço livre. Escolha-o menor que --n-percurso (usado para LOCALIZAR os APs)
# e o mapa carrega um viés que cresce com log(d) — ver docs/07, seção "viés do
# expoente". Iguale os dois com --n-referencia para eliminar o viés em troca de
# perder o offset absoluto. Controlado por --n-referencia.
N_REFERENCIA_PADRAO = 2.0


# ----------------------------------------------------------------------------- dados

def carregar(caminhos):
    """Agrega as amostras: para cada (ponto, AP), a mediana do RSSI."""
    bruto = defaultdict(list)
    for caminho in caminhos:
        with open(caminho) as f:
            for linha in f:
                if not linha.strip():
                    continue
                r = json.loads(linha)
                bruto[((r["x"], r["y"]), r["ap"], r.get("freq_mhz", 2412))].append(r["rssi_dbm"])

    medidas = []
    for (ponto, ap, freq), vals in bruto.items():
        medidas.append({
            "ponto": np.array(ponto, dtype=float),
            "ap": ap,
            "freq": freq,
            "rssi": float(np.median(vals)),
            "n": len(vals),
            "std": float(np.std(vals)),
        })
    return medidas


# ------------------------------------------------------------------- localizar os APs

def perda_modelo(dist, a_ref, n):
    """RSSI previsto pelo modelo log-distance. a_ref = RSSI a 1 metro."""
    return a_ref - 10.0 * n * np.log10(np.maximum(dist, 0.3))


def localizar_ap(pontos, rssis, limites, n_percurso, passo_fino=0.25):
    """
    Estima (x, y) do AP e seu a_ref por busca em grade grosseiro-para-fino.

    Sem scipy: busca direta é lenta mas robusta, e a grade é pequena.
    APs de vizinhos caem fora dos limites da casa — isso é esperado e útil,
    porque os raios deles atravessam a casa inteira.
    """
    x0, x1, y0, y1 = limites
    # margem generosa: APs podem estar fora da área medida
    margem = max(x1 - x0, y1 - y0)
    bx0, bx1 = x0 - margem, x1 + margem
    by0, by1 = y0 - margem, y1 + margem

    melhor = None
    passo = max((bx1 - bx0) / 24.0, 0.5)

    while passo >= passo_fino:
        xs = np.arange(bx0, bx1 + passo, passo)
        ys = np.arange(by0, by1 + passo, passo)
        for cx in xs:
            for cy in ys:
                d = np.hypot(pontos[:, 0] - cx, pontos[:, 1] - cy)
                # a_ref ótimo em forma fechada: média do resíduo
                a_ref = np.mean(rssis + 10.0 * n_percurso * np.log10(np.maximum(d, 0.3)))
                erro = float(np.mean((perda_modelo(d, a_ref, n_percurso) - rssis) ** 2))
                if melhor is None or erro < melhor[0]:
                    melhor = (erro, cx, cy, a_ref)
        # refina em torno do melhor
        _, cx, cy, _ = melhor
        bx0, bx1 = cx - 2 * passo, cx + 2 * passo
        by0, by1 = cy - 2 * passo, cy + 2 * passo
        passo /= 2.5

    erro, cx, cy, a_ref = melhor
    return np.array([cx, cy]), a_ref, math.sqrt(erro)


# ------------------------------------------------------------------------- tomografia

def traçar_raio(p0, p1, origem, passo_grade, nx, ny, amostras_por_metro=8):
    """
    Comprimento do raio p0->p1 dentro de cada célula da grade.
    Amostragem uniforme: mais simples que Siddon e suficiente nesta resolução.
    Retorna dict {índice_da_célula: comprimento}.
    """
    delta = p1 - p0
    comprimento = float(np.hypot(*delta))
    if comprimento < 1e-6:
        return {}
    n = max(int(comprimento * amostras_por_metro), 2)
    ds = comprimento / n

    pesos = defaultdict(float)
    for k in range(n):
        t = (k + 0.5) / n
        pos = p0 + t * delta
        ix = int((pos[0] - origem[0]) / passo_grade)
        iy = int((pos[1] - origem[1]) / passo_grade)
        if 0 <= ix < nx and 0 <= iy < ny:
            pesos[iy * nx + ix] += ds
    return pesos


def resolver(M, b, nx, ny, lam=0.05, mu=0.5, iters=400, lr=None):
    """
    Minimiza ||Mx - b||^2 + lam*||x||^2 + mu*||Dx||^2  sujeito a  x >= 0.

    Gradiente projetado. D é o laplaciano discreto (penaliza mapas ruidosos,
    favorece estruturas contínuas — que é o que paredes são).
    """
    n_cel = nx * ny
    x = np.zeros(n_cel)

    MtM = M.T @ M
    Mtb = M.T @ b

    def laplaciano(v):
        g = v.reshape(ny, nx)
        out = 4.0 * g.copy()
        out[:, :-1] -= g[:, 1:]
        out[:, 1:] -= g[:, :-1]
        out[:-1, :] -= g[1:, :]
        out[1:, :] -= g[:-1, :]
        return out.ravel()

    if lr is None:
        # passo estável ~ 1 / maior autovalor aproximado
        escala = float(np.linalg.norm(MtM, 2)) + lam + mu * 8.0
        lr = 1.0 / max(escala, 1e-9)

    for _ in range(iters):
        grad = 2.0 * (MtM @ x - Mtb) + 2.0 * lam * x + 2.0 * mu * laplaciano(x)
        x = np.maximum(x - lr * grad, 0.0)   # projeção: densidade não é negativa
    return x


# ------------------------------------------------------------------------------ saída

RAMPA = " .:-=+*#%@"


def render_ascii(mapa, nx, ny, origem, passo):
    vmax = float(mapa.max())
    if vmax <= 0:
        return "(mapa vazio — nenhuma atenuação detectada)"
    g = mapa.reshape(ny, nx) / vmax
    linhas = []
    for iy in range(ny - 1, -1, -1):   # y crescente para cima
        y = origem[1] + (iy + 0.5) * passo
        celulas = "".join(RAMPA[min(int(v * (len(RAMPA) - 1) + 0.5), len(RAMPA) - 1)]
                          for v in g[iy])
        linhas.append(f"{y:5.1f} |{celulas}|")
    eixo = "      +" + "-" * nx + "+"
    linhas.append(eixo)
    linhas.append(f"      x de {origem[0]:.1f} a {origem[0] + nx * passo:.1f} m"
                  f"   (célula {passo:.2f} m, máx {vmax:.1f} dB/m)")
    return "\n".join(linhas)


def salvar_pgm(mapa, nx, ny, caminho):
    vmax = float(mapa.max()) or 1.0
    g = (mapa.reshape(ny, nx) / vmax * 255).astype(np.uint8)
    g = np.flipud(g)   # PGM desenha de cima para baixo
    with open(caminho, "wb") as f:
        f.write(f"P5\n{nx} {ny}\n255\n".encode())
        f.write(g.tobytes())


# -------------------------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("survey", nargs="+", help="arquivo(s) JSONL do survey.py")
    p.add_argument("--grid", type=float, default=0.5, help="tamanho da célula em metros")
    p.add_argument("--min-cobertura", type=float, default=0.6,
                   help="fração mínima de pontos em que o AP precisa aparecer")
    p.add_argument("--n-percurso", type=float, default=2.6,
                   help="expoente log-distance para LOCALIZAR os APs (2.0 livre, 3-4 indoor)")
    p.add_argument("--n-referencia", type=float, default=N_REFERENCIA_PADRAO,
                   help="expoente de REFERÊNCIA do excesso de atenuação (padrão 2.0 = espaço "
                        "livre). Iguale a --n-percurso para remover o viés em log(d), em troca "
                        "de medir só o desvio em relação à parede média. Ver docs/07.")
    p.add_argument("--lam", type=float, default=0.05, help="regularização Tikhonov")
    p.add_argument("--mu", type=float, default=0.5, help="peso da suavidade")
    p.add_argument("--out", default="data/processed", help="diretório de saída")
    a = p.parse_args()

    medidas = carregar(a.survey)
    if not medidas:
        print("Nenhuma medida encontrada.", file=sys.stderr)
        sys.exit(1)

    pontos = np.unique(np.array([m["ponto"] for m in medidas]), axis=0)
    if len(pontos) < 6:
        print(f"Só {len(pontos)} pontos de medição. Colete mais — mínimo prático 20.",
              file=sys.stderr)
        sys.exit(1)

    x0, y0 = pontos.min(axis=0)
    x1, y1 = pontos.max(axis=0)
    print(f"Pontos de medição : {len(pontos)}")
    print(f"Área coberta      : {x1-x0:.1f} x {y1-y0:.1f} m")

    # --- etapa 1: localizar APs -------------------------------------------------
    por_ap = defaultdict(list)
    for m in medidas:
        por_ap[m["ap"]].append(m)

    aps = {}
    print(f"\nLocalizando APs (expoente n={a.n_percurso})...")
    for ap, ms in sorted(por_ap.items()):
        cobertura = len(ms) / len(pontos)
        if cobertura < a.min_cobertura or len(ms) < 4:
            continue
        pts = np.array([m["ponto"] for m in ms])
        rssis = np.array([m["rssi"] for m in ms])
        pos, a_ref, rmse = localizar_ap(pts, rssis, (x0, x1, y0, y1), a.n_percurso)
        aps[ap] = {"pos": pos, "a_ref": a_ref, "rmse": rmse, "cobertura": cobertura}
        dentro = "dentro" if x0 <= pos[0] <= x1 and y0 <= pos[1] <= y1 else "fora"
        print(f"  {ap}  pos=({pos[0]:6.1f},{pos[1]:6.1f}) {dentro:6s} "
              f"a_ref={a_ref:6.1f} dBm  rmse={rmse:4.1f} dB  cob={cobertura*100:4.0f}%")

    if len(aps) < 3:
        print(f"\nSó {len(aps)} APs utilizáveis. A tomografia precisa de pelo menos 3 "
              f"(idealmente 8+). Baixe --min-cobertura ou colete mais.", file=sys.stderr)
        sys.exit(1)

    # --- etapa 2: montar o sistema ----------------------------------------------
    passo = a.grid
    margem = passo
    origem = np.array([x0 - margem, y0 - margem])
    nx = max(int(math.ceil((x1 - x0 + 2 * margem) / passo)), 2)
    ny = max(int(math.ceil((y1 - y0 + 2 * margem) / passo)), 2)
    n_cel = nx * ny
    print(f"\nGrade: {nx} x {ny} = {n_cel} células de {passo} m")

    linhas_M, b = [], []
    descartados = 0
    for m in medidas:
        info = aps.get(m["ap"])
        if info is None:
            continue
        d = float(np.hypot(*(m["ponto"] - info["pos"])))
        if d < 0.5:
            continue
        esperado = perda_modelo(d, info["a_ref"], a.n_referencia)
        excesso = esperado - m["rssi"]        # dB a mais de perda que o espaço livre
        if excesso < 0:
            excesso = 0.0                     # sinal melhor que o modelo: sem obstáculo
        pesos = traçar_raio(info["pos"], m["ponto"], origem, passo, nx, ny)
        if not pesos:
            descartados += 1
            continue
        linha = np.zeros(n_cel)
        for idx, w in pesos.items():
            linha[idx] = w
        linhas_M.append(linha)
        b.append(excesso)

    if len(linhas_M) < n_cel // 4:
        print(f"\nAviso: {len(linhas_M)} raios para {n_cel} células — sistema muito "
              f"subdeterminado. Aumente --grid ou colete mais pontos.", file=sys.stderr)

    M = np.array(linhas_M)
    b = np.array(b)
    print(f"Raios válidos: {len(b)}  (descartados: {descartados})")
    print(f"Excesso de atenuação: mediana {np.median(b):.1f} dB, máx {b.max():.1f} dB")

    # --- etapa 3: resolver -------------------------------------------------------
    print(f"\nResolvendo (lam={a.lam}, mu={a.mu})...")
    mapa = resolver(M, b, nx, ny, lam=a.lam, mu=a.mu)

    residuo = float(np.linalg.norm(M @ mapa - b) / max(np.linalg.norm(b), 1e-9))
    print(f"Resíduo relativo: {residuo*100:.1f}%")

    # --- saída -------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("MAPA DE ATENUAÇÃO  (escuro/espaço = livre, denso = parede)")
    print("=" * 60)
    print(render_ascii(mapa, nx, ny, origem, passo))

    destino = Path(a.out)
    destino.mkdir(parents=True, exist_ok=True)
    salvar_pgm(mapa, nx, ny, destino / "mapa.pgm")
    np.savetxt(destino / "mapa.csv", mapa.reshape(ny, nx), delimiter=",", fmt="%.4f")

    # Georreferência: sem isto o mapa.csv é uma matriz sem posição no mundo,
    # e compare.py não teria como sobrepô-lo ao ground truth.
    with open(destino / "mapa_meta.json", "w") as f:
        json.dump({
            "origem_x": float(origem[0]), "origem_y": float(origem[1]),
            "grid": float(passo), "nx": int(nx), "ny": int(ny),
            "unidade_valores": "dB/m",
            "n_percurso": float(a.n_percurso), "n_referencia": float(a.n_referencia),
            "lam": float(a.lam), "mu": float(a.mu),
            "n_raios": int(len(b)), "n_aps": len(aps),
            "residuo_relativo": float(residuo),
        }, f, indent=2)
    with open(destino / "aps.json", "w") as f:
        json.dump({k: {"x": float(v["pos"][0]), "y": float(v["pos"][1]),
                       "a_ref": float(v["a_ref"]), "rmse": float(v["rmse"])}
                   for k, v in aps.items()}, f, indent=2)

    print(f"\nSalvo em {destino}/ : mapa.pgm, mapa.csv, mapa_meta.json, aps.json")
    print("\nCompare com a planta da fase 0. Espere manchas na posição das paredes,")
    print("não bordas nítidas — a resolução do Wi-Fi não permite mais que isso.")


if __name__ == "__main__":
    main()
