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

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cobertura as _cob      # noqa: E402
import modos as _modos        # noqa: E402

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


def ajustar_a_ref(pontos, rssis, pos, n_percurso):
    """
    Dada a posição do AP como CONHECIDA, o a_ref ótimo tem forma fechada: é a
    média do resíduo. Usado quando --aps-fixos traz posições medidas (por RTT ou
    pela triangulação de probe.py), em vez de estimadas.
    """
    d = np.hypot(pontos[:, 0] - pos[0], pontos[:, 1] - pos[1])
    a_ref = float(np.mean(rssis + 10.0 * n_percurso * np.log10(np.maximum(d, 0.3))))
    rmse = float(np.sqrt(np.mean((perda_modelo(d, a_ref, n_percurso) - rssis) ** 2)))
    return a_ref, rmse


def carregar_aps_fixos(caminho):
    """{canal: (x, y)} a partir de aps_medidos.json ou aps.json."""
    if not caminho:
        return {}
    dados = json.loads(Path(caminho).read_text())
    return {k: np.array([float(v["x"]), float(v["y"])]) for k, v in dados.items()}


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

# Lado maior desejado, em pixels, do mapa.pgm quando --pgm-escala é automático.
LADO_PGM_PADRAO = 600


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


def salvar_pgm(mapa, nx, ny, caminho, escala=None):
    """Grava o mapa como PGM, uma célula da grade por bloco de escala x escala pixels.

    A grade tem poucas dezenas de células de lado; gravada 1 pixel por célula, a
    imagem sai com ~16x12 px e nenhum visualizador a mostra de forma legível. A
    ampliação é nearest-neighbor: não inventa resolução, só torna visível a que já
    existe — a resolução física continua sendo o --grid.

    escala=None escolhe o fator que deixa o lado maior perto de LADO_PGM_PADRAO.
    Devolve a escala usada.
    """
    if escala is None:
        escala = max(1, round(LADO_PGM_PADRAO / max(nx, ny)))
    escala = max(1, int(escala))
    vmax = float(mapa.max()) or 1.0
    g = (mapa.reshape(ny, nx) / vmax * 255).astype(np.uint8)
    g = np.flipud(g)   # PGM desenha de cima para baixo
    if escala > 1:
        g = np.repeat(np.repeat(g, escala, axis=0), escala, axis=1)
    with open(caminho, "wb") as f:
        f.write(f"P5\n{g.shape[1]} {g.shape[0]}\n255\n".encode())
        f.write(g.tobytes())
    return escala


# --------------------------------------------------------------- pipeline reutilizável

def reconstruir(medidas, grid=0.5, min_cobertura=0.6, n_percurso=2.6,
                n_referencia=N_REFERENCIA_PADRAO, lam=0.05, mu=0.5,
                aps_fixos=None, verbose=True, min_raios=_cob.MIN_RAIOS,
                min_diversidade=_cob.MIN_DIVERSIDADE):
    """
    O pipeline inteiro, como função: localiza APs, monta o sistema, resolve e
    mede a cobertura. Devolve um dict.

    Existe como função separada do main porque orcamento.py precisa rodá-la
    centenas de vezes variando parâmetros, e camadas.py precisa dos mesmos
    subprodutos (M, raios, cobertura) sem reimprimir nada.
    """
    fala = print if verbose else (lambda *a, **k: None)
    aps_fixos = aps_fixos or {}

    pontos = np.unique(np.array([m["ponto"] for m in medidas]), axis=0)
    if len(pontos) < 6:
        raise ValueError(f"só {len(pontos)} pontos de medição; mínimo prático 20")

    x0, y0 = pontos.min(axis=0)
    x1, y1 = pontos.max(axis=0)
    fala(f"Pontos de medição : {len(pontos)}")
    fala(f"Área coberta      : {x1-x0:.1f} x {y1-y0:.1f} m")

    # --- etapa 1: posição dos APs ------------------------------------------
    por_ap = defaultdict(list)
    for m in medidas:
        por_ap[m["ap"]].append(m)

    aps = {}
    if aps_fixos:
        fala(f"\n{len(aps_fixos)} AP(s) com posição FIXA — não serão estimados")
    fala(f"\nLocalizando APs (expoente n={n_percurso})...")
    for ap, ms in sorted(por_ap.items()):
        cob = len(ms) / len(pontos)
        if cob < min_cobertura or len(ms) < 4:
            continue
        pts = np.array([m["ponto"] for m in ms])
        rssis = np.array([m["rssi"] for m in ms])
        if ap in aps_fixos:
            pos = aps_fixos[ap]
            a_ref, rmse = ajustar_a_ref(pts, rssis, pos, n_percurso)
            origem_pos = "fixo"
        else:
            pos, a_ref, rmse = localizar_ap(pts, rssis, (x0, x1, y0, y1), n_percurso)
            origem_pos = "estimado"
        aps[ap] = {"pos": pos, "a_ref": a_ref, "rmse": rmse, "cobertura": cob,
                   "origem": origem_pos}
        dentro = "dentro" if x0 <= pos[0] <= x1 and y0 <= pos[1] <= y1 else "fora"
        fala(f"  {ap}  pos=({pos[0]:6.1f},{pos[1]:6.1f}) {dentro:6s} "
             f"a_ref={a_ref:6.1f} dBm  rmse={rmse:4.1f} dB  cob={cob*100:4.0f}%  "
             f"[{origem_pos}]")

    if len(aps) < 3:
        raise ValueError(f"só {len(aps)} APs utilizáveis; a tomografia precisa de 3+ "
                         f"(idealmente 8+). Baixe min_cobertura ou colete mais.")

    # --- etapa 2: montar o sistema -----------------------------------------
    passo = grid
    margem = passo
    origem = np.array([x0 - margem, y0 - margem])
    nx = max(int(math.ceil((x1 - x0 + 2 * margem) / passo)), 2)
    ny = max(int(math.ceil((y1 - y0 + 2 * margem) / passo)), 2)
    n_cel = nx * ny
    fala(f"\nGrade: {nx} x {ny} = {n_cel} células de {passo} m")

    linhas_M, b, raios = [], [], []
    descartados = 0
    for m in medidas:
        info = aps.get(m["ap"])
        if info is None:
            continue
        delta = m["ponto"] - info["pos"]
        d = float(np.hypot(*delta))
        if d < 0.5:
            continue
        esperado = perda_modelo(d, info["a_ref"], n_referencia)
        excesso = max(esperado - m["rssi"], 0.0)
        pesos = traçar_raio(info["pos"], m["ponto"], origem, passo, nx, ny)
        if not pesos:
            descartados += 1
            continue
        linha = np.zeros(n_cel)
        for idx, w in pesos.items():
            linha[idx] = w
        linhas_M.append(linha)
        b.append(excesso)
        raios.append((pesos, tuple(delta)))

    if not linhas_M:
        raise ValueError("nenhum raio válido — confira o referencial das posições")

    M = np.array(linhas_M)
    b = np.array(b)
    subdeterminado = len(linhas_M) < n_cel // 4
    fala(f"Raios válidos: {len(b)}  (descartados: {descartados})")
    if subdeterminado:
        fala(f"Aviso: {len(linhas_M)} raios para {n_cel} células — muito "
             f"subdeterminado. Aumente grid ou colete mais pontos.")
    fala(f"Excesso de atenuação: mediana {np.median(b):.1f} dB, máx {b.max():.1f} dB")

    # --- etapa 3: resolver --------------------------------------------------
    fala(f"\nResolvendo (lam={lam}, mu={mu})...")
    mapa = resolver(M, b, nx, ny, lam=lam, mu=mu)
    residuo = float(np.linalg.norm(M @ mapa - b) / max(np.linalg.norm(b), 1e-9))
    fala(f"Resíduo relativo: {residuo*100:.1f}%")

    # --- etapa 4: cobertura -------------------------------------------------
    contagem, diversidade, comprimento = _cob.calcular(raios, nx, ny)
    masc = _cob.mascara(contagem, diversidade, min_raios, min_diversidade)

    return {
        "mapa": mapa, "M": M, "b": b, "raios": raios, "aps": aps,
        "origem": origem, "nx": nx, "ny": ny, "passo": passo,
        "residuo": residuo, "subdeterminado": subdeterminado,
        "contagem": contagem, "diversidade": diversidade,
        "comprimento": comprimento, "mascara": masc,
        "meta": {
            "origem_x": float(origem[0]), "origem_y": float(origem[1]),
            "grid": float(passo), "nx": int(nx), "ny": int(ny),
            "unidade_valores": "dB/m",
            "n_percurso": float(n_percurso), "n_referencia": float(n_referencia),
            "lam": float(lam), "mu": float(mu),
            "n_raios": int(len(b)), "n_aps": len(aps),
            "n_aps_fixos": sum(1 for v in aps.values() if v["origem"] == "fixo"),
            "residuo_relativo": float(residuo),
            "frac_coberta": float(masc.mean()),
            "min_raios": int(min_raios), "min_diversidade": float(min_diversidade),
        },
    }


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
    p.add_argument("--aps-fixos", default=None,
                   help="JSON {canal: {x, y}} com posições MEDIDAS de APs — de "
                        "src/probe.py triangular, ou de Wi-Fi RTT. Remove a maior "
                        "fonte de erro sistemático do mapa (docs/15 §2, §6)")
    p.add_argument("--min-raios", type=int, default=_cob.MIN_RAIOS,
                   help="raios mínimos para a célula contar como coberta (docs/15 §3)")
    p.add_argument("--min-diversidade", type=float, default=_cob.MIN_DIVERSIDADE,
                   help="diversidade angular mínima, 0-1")
    p.add_argument("--sem-cobertura", action="store_true",
                   help="não imprimir os mapas de cobertura (ainda são salvos)")
    p.add_argument("--modo", default=None,
                   help="apenas rotula a procedência no meta; a reconstrução em si "
                        "não depende do modo. Ver python3 src/modos.py --listar")
    p.add_argument("--out", default="data/processed", help="diretório de saída")
    p.add_argument("--pgm-escala", type=int, default=0,
                   help="pixels por célula da grade no mapa.pgm "
                        "(0 = automático, ~{} px no lado maior)".format(LADO_PGM_PADRAO))
    a = p.parse_args()

    medidas = carregar(a.survey)
    if not medidas:
        print("Nenhuma medida encontrada.", file=sys.stderr)
        sys.exit(1)

    try:
        r = reconstruir(medidas, grid=a.grid, min_cobertura=a.min_cobertura,
                        n_percurso=a.n_percurso, n_referencia=a.n_referencia,
                        lam=a.lam, mu=a.mu,
                        aps_fixos=carregar_aps_fixos(a.aps_fixos),
                        min_raios=a.min_raios, min_diversidade=a.min_diversidade)
    except ValueError as e:
        sys.exit(f"\n{e}")

    mapa, nx, ny, origem, passo = r["mapa"], r["nx"], r["ny"], r["origem"], r["passo"]

    print("\n" + "=" * 60)
    print("MAPA DE ATENUAÇÃO  (escuro/espaço = livre, denso = parede)")
    print("=" * 60)
    print(render_ascii(mapa, nx, ny, origem, passo))

    print()
    _cob.resumo(r["contagem"], r["diversidade"], origem, passo,
                a.min_raios, a.min_diversidade, mostrar_mapas=not a.sem_cobertura)

    destino = Path(a.out)
    destino.mkdir(parents=True, exist_ok=True)
    escala_pgm = salvar_pgm(mapa, nx, ny, destino / "mapa.pgm", a.pgm_escala or None)
    np.savetxt(destino / "mapa.csv", mapa.reshape(ny, nx), delimiter=",", fmt="%.4f")
    extras = _cob.salvar(destino, r["contagem"], r["diversidade"], r["comprimento"],
                         salvar_pgm)

    meta = dict(r["meta"], pgm_escala=int(escala_pgm))
    if a.modo:
        modo = _modos.resolver(a.modo)
        meta["modo"] = modo.nome
        meta["modo_verificado"] = modo.verificado
        meta["delta_r_m"] = (None if modo.delta_r == math.inf else round(modo.delta_r, 4))
    if a.aps_fixos:
        meta["aps_fixos_de"] = a.aps_fixos
    with open(destino / "mapa_meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    with open(destino / "aps.json", "w") as f:
        json.dump({k: {"x": float(v["pos"][0]), "y": float(v["pos"][1]),
                       "a_ref": float(v["a_ref"]), "rmse": float(v["rmse"]),
                       "origem": v["origem"]}
                   for k, v in r["aps"].items()}, f, indent=2)

    print(f"\nSalvo em {destino}/ : mapa.pgm, mapa.csv, mapa_meta.json, aps.json, "
          + ", ".join(extras))
    print(f"mapa.pgm: {nx*escala_pgm} x {ny*escala_pgm} px "
          f"({escala_pgm} px por célula de {passo} m)")
    print("\nAvalie com número, e só nas células cobertas:")
    print(f"  python3 src/compare.py {destino} data/ground_truth.json "
          f"--tipos divisoria --cobertura")
    print("Espere manchas na posição das paredes, não bordas nítidas — a resolução")
    print("do Wi-Fi não permite mais que isso (docs/14 §14.4).")


if __name__ == "__main__":
    main()
