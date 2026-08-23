#!/usr/bin/env python3
"""
groundtruth.py — a planta de referência da fase 0.

Sem uma planta medida de verdade não existe avaliação, só impressão: um mapa
reconstruído errado que parece plausível é o pior resultado possível do projeto.

Faz três coisas:
  --validate  confere o arquivo e aponta problemas
  --render    desenha a planta em ASCII, para conferir o que você digitou
  --plan      gera o plano de coleta: onde colar a fita crepe e que comandos rodar

Formato do arquivo em docs/09-formato-dos-dados.md.
"""

import argparse
import json
import math
import sys
from pathlib import Path

# Atenuações típicas, em dB, para preencher a planta. Ordens de grandeza — meça
# se quiser precisão; a tomografia é pouco sensível ao valor exato.
TIPICOS = {
    "drywall": 4.0, "alvenaria": 9.0, "concreto": 15.0,
    "laje": 20.0, "vidro": 3.0, "porta": 3.5, "externa": 12.0,
}

OBRIGATORIOS = ("x0", "y0", "x1", "y1")


# ------------------------------------------------------------------------- validação

def carregar(caminho):
    with open(caminho) as f:
        gt = json.load(f)
    if "paredes" not in gt:
        raise ValueError("arquivo sem a chave 'paredes'")
    return gt


def validar(gt):
    """Retorna (erros, avisos). Erros impedem o uso; avisos são suspeitas."""
    erros, avisos = [], []

    paredes = gt.get("paredes", [])
    if not paredes:
        erros.append("nenhuma parede definida")

    for i, p in enumerate(paredes):
        faltando = [c for c in OBRIGATORIOS if c not in p]
        if faltando:
            erros.append(f"parede[{i}]: faltam os campos {faltando}")
            continue
        comp = math.hypot(p["x1"] - p["x0"], p["y1"] - p["y0"])
        if comp < 0.05:
            erros.append(f"parede[{i}]: comprimento {comp:.3f} m — segmento degenerado")
        if "atenuacao_db" not in p:
            avisos.append(f"parede[{i}]: sem 'atenuacao_db' — assumindo {TIPICOS['alvenaria']} dB")
        else:
            a = p["atenuacao_db"]
            if not 0 < a < 60:
                avisos.append(f"parede[{i}]: atenuação {a} dB fora da faixa plausível (0–60)")

    for i, d in enumerate(gt.get("portas", [])):
        if any(c not in d for c in OBRIGATORIOS):
            erros.append(f"porta[{i}]: faltam campos de coordenada")

    if gt.get("unidade", "metros") != "metros":
        erros.append("apenas 'metros' é suportado no campo 'unidade'")

    # a planta precisa fechar um recinto, ou o plano de coleta não sabe onde é dentro
    xs = [c for p in paredes for c in (p.get("x0", 0), p.get("x1", 0))]
    ys = [c for p in paredes for c in (p.get("y0", 0), p.get("y1", 0))]
    if xs and ys:
        larg, alt = max(xs) - min(xs), max(ys) - min(ys)
        if larg < 1 or alt < 1:
            avisos.append(f"planta muito pequena ({larg:.1f} x {alt:.1f} m) — confira as unidades")
        if larg > 60 or alt > 60:
            avisos.append(f"planta muito grande ({larg:.1f} x {alt:.1f} m) — confira as unidades")

    return erros, avisos


# --------------------------------------------------------------------------- geometria

def limites(gt):
    xs = [c for p in gt["paredes"] for c in (p["x0"], p["x1"])]
    ys = [c for p in gt["paredes"] for c in (p["y0"], p["y1"])]
    return min(xs), min(ys), max(xs), max(ys)


def dist_ponto_segmento(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    den = dx * dx + dy * dy
    if den < 1e-12:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / den))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def dist_a_parede(gt, px, py):
    return min(dist_ponto_segmento(px, py, p["x0"], p["y0"], p["x1"], p["y1"])
               for p in gt["paredes"])


def rasterizar(gt, origem, grid, nx, ny, espessura=None):
    """
    Máscara booleana: célula True se alguma parede passa por ela.
    'espessura' é a distância máxima do centro da célula à parede; por padrão
    meia diagonal da célula, de forma que a parede ocupe as células que cruza.
    """
    if espessura is None:
        espessura = grid * 0.7071
    mascara = [[False] * nx for _ in range(ny)]
    for iy in range(ny):
        cy = origem[1] + (iy + 0.5) * grid
        for ix in range(nx):
            cx = origem[0] + (ix + 0.5) * grid
            if dist_a_parede(gt, cx, cy) <= espessura:
                mascara[iy][ix] = True
    return mascara


def em_porta(gt, px, py, tol=0.4):
    for d in gt.get("portas", []):
        if dist_ponto_segmento(px, py, d["x0"], d["y0"], d["x1"], d["y1"]) <= tol:
            return True
    return False


# ------------------------------------------------------------------------------ render

def render(gt, grid=0.5):
    x0, y0, x1, y1 = limites(gt)
    margem = grid
    origem = (x0 - margem, y0 - margem)
    nx = max(int(math.ceil((x1 - x0 + 2 * margem) / grid)), 2)
    ny = max(int(math.ceil((y1 - y0 + 2 * margem) / grid)), 2)
    mascara = rasterizar(gt, origem, grid, nx, ny)

    linhas = []
    for iy in range(ny - 1, -1, -1):
        y = origem[1] + (iy + 0.5) * grid
        cels = ""
        for ix in range(nx):
            x = origem[0] + (ix + 0.5) * grid
            if em_porta(gt, x, y, tol=grid * 0.7):
                cels += "+"            # vão de porta: ausência intencional de parede
            elif mascara[iy][ix]:
                cels += "#"
            else:
                cels += " "
        linhas.append(f"{y:5.1f} |{cels}|")
    linhas.append("      +" + "-" * nx + "+")
    linhas.append(f"      x de {origem[0]:.1f} a {origem[0] + nx * grid:.1f} m"
                  f"   (célula {grid} m)   '#' parede  '+' porta")
    return "\n".join(linhas)


# ------------------------------------------------------------------------------- plano

def plano_de_coleta(gt, step, margem_parede, survey_out):
    x0, y0, x1, y1 = limites(gt)
    pontos = []
    y = y0
    while y <= y1 + 1e-9:
        x = x0
        while x <= x1 + 1e-9:
            # pontos colados na parede sofrem reflexão forte e viés de corpo
            if dist_a_parede(gt, x, y) >= margem_parede:
                pontos.append((round(x, 2), round(y, 2)))
            x += step
        y += step

    print(f"PLANO DE COLETA — fase 1")
    print("=" * 64)
    print(f"Planta        : {x1-x0:.1f} x {y1-y0:.1f} m")
    print(f"Espaçamento   : {step} m")
    print(f"Margem parede : {margem_parede} m (pontos mais próximos foram descartados)")
    print(f"Pontos        : {len(pontos)}")

    if len(pontos) < 20:
        print(f"\n  AVISO: {len(pontos)} pontos. O critério da fase 1 pede >= 20.")
        print(f"  Use --step {max(step/2, 0.25):.2f} para adensar a grade.")

    tempo = len(pontos) * (15 * 1.0 + 20) / 60.0   # 15 varreduras + deslocamento
    print(f"Tempo estimado: ~{tempo:.0f} min\n")

    print("ANTES DE COMEÇAR")
    print("-" * 64)
    print("  1. Marque a origem (0,0) no chão com fita. Todo o dataset depende dela.")
    print("  2. Escolha uma direção 'norte' e aponte o laptop para ela em TODOS os pontos.")
    print("     O corpo atenua 3-6 dB: girar injeta viés que vira parede falsa no mapa.")
    print("  3. Casa vazia. Ninguém circulando, você parado durante a varredura.")
    print("  4. Não mude nada no meio: roteador ligado, mesma banda, tampa aberta.\n")

    print("COMANDOS (um por ponto)")
    print("-" * 64)
    for px, py in pontos:
        print(f"python3 src/survey.py --x {px} --y {py} --samples 15 --out {survey_out}")

    print("\nAO TERMINAR")
    print("-" * 64)
    print(f"  python3 src/survey.py --summary {survey_out}")
    print(f"  python3 src/reconstruct.py {survey_out} --grid 0.5")
    print(f"  python3 src/reconstruct.py {survey_out} --grid 0.5 --n-referencia 2.6")
    print(f"  python3 src/compare.py data/processed <ground_truth.json>")
    return pontos


# -------------------------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("arquivo", help="ground_truth.json")
    p.add_argument("--validate", action="store_true", help="apenas validar")
    p.add_argument("--render", action="store_true", help="desenhar a planta em ASCII")
    p.add_argument("--plan", action="store_true", help="gerar o plano de coleta")
    p.add_argument("--grid", type=float, default=0.5, help="célula do render (m)")
    p.add_argument("--step", type=float, default=1.0, help="espaçamento da grade de coleta (m)")
    p.add_argument("--margem-parede", type=float, default=0.4,
                   help="distância mínima entre ponto de coleta e parede (m)")
    p.add_argument("--survey-out", default="data/raw/survey.jsonl",
                   help="arquivo de survey citado nos comandos gerados")
    a = p.parse_args()

    if not Path(a.arquivo).exists():
        print(f"Arquivo não encontrado: {a.arquivo}", file=sys.stderr)
        print("Comece copiando data/ground_truth.example.json", file=sys.stderr)
        sys.exit(1)

    try:
        gt = carregar(a.arquivo)
    except Exception as e:
        print(f"Não foi possível ler: {e}", file=sys.stderr)
        sys.exit(1)

    erros, avisos = validar(gt)
    for e in erros:
        print(f"  ERRO  {e}", file=sys.stderr)
    for w in avisos:
        print(f"  aviso {w}")
    if erros:
        sys.exit(1)

    x0, y0, x1, y1 = limites(gt)
    print(f"OK: {len(gt['paredes'])} paredes, {len(gt.get('portas', []))} portas, "
          f"área {x1-x0:.1f} x {y1-y0:.1f} m")

    # sem flag de ação, mostra tudo
    nenhuma = not (a.validate or a.render or a.plan)
    if a.render or nenhuma:
        print()
        print(render(gt, a.grid))
    if a.plan or nenhuma:
        print()
        plano_de_coleta(gt, a.step, a.margem_parede, a.survey_out)


if __name__ == "__main__":
    main()
