#!/usr/bin/env python3
"""
cobertura.py — em quais células o mapa tem direito de existir (docs/15 §3).

O mapa de atenuação pinta todas as células com a mesma tinta, e quem olha supõe
confiança uniforme. Ela não é uniforme. Com RSSI de beacon a largura de banda é
nula, então NÃO existe resolução ao longo do raio (docs/14 §14.4): toda a
informação vem de raios cruzando a célula em ângulos diferentes.

Logo, duas células muito diferentes podem ter o mesmo valor:

  - atravessada por 40 raios em ângulos variados  -> resultado
  - atravessada por 2 raios quase paralelos       -> chute com cara de resultado

Este módulo mede a diferença, com duas grandezas tiradas da mesma matriz de
projeção que a tomografia já usa — sem física nova e sem coleta nova:

  CONTAGEM     quantos raios cruzam a célula.
  DIVERSIDADE  quão espalhados são os ângulos desses raios, em [0, 1].
               0 = todos paralelos (a célula é indistinguível das vizinhas ao
               longo daquela direção); 1 = ângulos uniformemente distribuídos.

               Um raio é uma RETA, não um vetor: as direções θ e θ+180° são a
               mesma informação. Por isso a dispersão é medida no ângulo DOBRADO
               (2θ), que é o jeito correto de medir espalhamento de orientações.

O uso mais importante disso não é olhar o mapa — é restringir a AVALIAÇÃO às
células cobertas. Sem essa máscara, as métricas de docs/13 misturam falha de
reconstrução com ausência de medição, e não há como saber qual das duas se está
medindo. É o argumento de D15 aplicado à cobertura em vez de ao tipo de parede.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

MIN_RAIOS = 5           # abaixo disso a célula é chute
MIN_DIVERSIDADE = 0.25  # abaixo disso os raios são praticamente paralelos


def calcular(raios, nx, ny):
    """
    raios: iterável de (pesos, direcao), onde
        pesos   = {indice_da_celula: comprimento_dentro_dela}
        direcao = (dx, dy) do raio, não precisa ser unitária

    Devolve (contagem, diversidade, comprimento), todos (ny, nx).
    """
    n_cel = nx * ny
    contagem = np.zeros(n_cel, dtype=np.int32)
    comprimento = np.zeros(n_cel)
    soma_cos = np.zeros(n_cel)
    soma_sin = np.zeros(n_cel)

    for pesos, direcao in raios:
        dx, dy = direcao
        norma = math.hypot(dx, dy)
        if norma < 1e-9:
            continue
        # ângulo dobrado: trata θ e θ+180° como a mesma orientação
        theta2 = 2.0 * math.atan2(dy, dx)
        c, s = math.cos(theta2), math.sin(theta2)
        for idx, w in pesos.items():
            contagem[idx] += 1
            comprimento[idx] += w
            soma_cos[idx] += c
            soma_sin[idx] += s

    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.hypot(soma_cos, soma_sin) / np.maximum(contagem, 1)
    diversidade = np.where(contagem > 0, 1.0 - r, 0.0)
    return (contagem.reshape(ny, nx),
            diversidade.reshape(ny, nx),
            comprimento.reshape(ny, nx))


def mascara(contagem, diversidade, min_raios=MIN_RAIOS, min_div=MIN_DIVERSIDADE):
    """True onde a célula é sustentada por dados, não por regularização."""
    return (contagem >= min_raios) & (diversidade >= min_div)


RAMPA = " .:-=+*#%@"


def render_ascii(campo, origem, passo, vmax=None, rotulo=""):
    ny, nx = campo.shape
    vmax = float(vmax if vmax is not None else campo.max())
    if vmax <= 0:
        return f"({rotulo or 'campo'} vazio)"
    linhas = []
    for iy in range(ny - 1, -1, -1):
        y = origem[1] + (iy + 0.5) * passo
        cel = "".join(RAMPA[min(int(v / vmax * (len(RAMPA) - 1) + 0.5), len(RAMPA) - 1)]
                      for v in campo[iy])
        linhas.append(f"{y:5.1f} |{cel}|")
    linhas.append("      +" + "-" * nx + "+")
    linhas.append(f"      x de {origem[0]:.1f} a {origem[0] + nx * passo:.1f} m"
                  f"   (máx {vmax:.2f}{' ' + rotulo if rotulo else ''})")
    return "\n".join(linhas)


def resumo(contagem, diversidade, origem, passo, min_raios=MIN_RAIOS,
           min_div=MIN_DIVERSIDADE, mostrar_mapas=True):
    """Imprime o diagnóstico e devolve a máscara + as estatísticas."""
    m = mascara(contagem, diversidade, min_raios, min_div)
    total = contagem.size
    frac_cob = float(m.mean())
    frac_raios = float((contagem >= min_raios).mean())
    frac_div = float((diversidade >= min_div).mean())

    print("=" * 66)
    print("COBERTURA DE RAIOS  (docs/15 §3)")
    print("=" * 66)
    print(f"Células            : {total}")
    print(f"Raios por célula   : mediana {np.median(contagem):.0f}  "
          f"máx {contagem.max()}  vazias {int((contagem == 0).sum())}")
    print(f"Diversidade angular: mediana {np.median(diversidade):.2f}  "
          f"máx {diversidade.max():.2f}")
    print(f"  com >= {min_raios} raios          : {frac_raios*100:5.1f}%")
    print(f"  com diversidade >= {min_div:.2f} : {frac_div*100:5.1f}%")
    print(f"  COBERTAS (as duas)      : {frac_cob*100:5.1f}%")

    if mostrar_mapas:
        print("\n-- Raios por célula " + "-" * 45)
        print(render_ascii(contagem.astype(float), origem, passo, rotulo="raios"))
        print("\n-- Diversidade angular " + "-" * 42)
        print(render_ascii(diversidade, origem, passo, vmax=1.0, rotulo="(0-1)"))

    print("\n-- Leitura " + "-" * 54)
    if frac_cob >= 0.8:
        print("  Cobertura suficiente. O mapa é sustentado por dados na maior parte")
        print("  da área, e as métricas de docs/13 podem ser lidas como estão.")
    elif frac_cob >= 0.4:
        print(f"  Só {frac_cob*100:.0f}% das células têm dado que as sustente. Avalie com")
        print("  máscara:  python3 src/compare.py <dir> <gt> --cobertura")
        print("  E colete mais pontos: sem banda, resolução vem de caminhar (docs/14 §14.4).")
    else:
        print(f"  Cobertura baixa ({frac_cob*100:.0f}%). O que está fora da máscara é")
        print("  regularização, não medição — por mais convincente que pareça.")
        if frac_raios > frac_div + 0.2:
            print("  O gargalo é ANGULAR, não quantidade: os raios são quase paralelos.")
            print("  Não colete mais do mesmo lugar; colete de direções diferentes.")
        elif frac_div > frac_raios + 0.2:
            print("  O gargalo é QUANTIDADE: os ângulos variam, faltam raios. Mais")
            print("  pontos de coleta, ou --grid maior.")
    return m, {"frac_coberta": frac_cob, "frac_min_raios": frac_raios,
               "frac_min_div": frac_div, "min_raios": min_raios,
               "min_diversidade": min_div}


def salvar(destino, contagem, diversidade, comprimento, salvar_pgm):
    """Grava as camadas de cobertura no mesmo referencial do mapa (D16)."""
    d = Path(destino)
    d.mkdir(parents=True, exist_ok=True)
    ny, nx = contagem.shape
    np.savetxt(d / "cobertura.csv", contagem, delimiter=",", fmt="%d")
    np.savetxt(d / "diversidade.csv", diversidade, delimiter=",", fmt="%.4f")
    salvar_pgm(contagem.astype(float).ravel(), nx, ny, d / "cobertura.pgm")
    salvar_pgm(diversidade.ravel(), nx, ny, d / "diversidade.pgm")
    return ["cobertura.csv", "diversidade.csv", "cobertura.pgm", "diversidade.pgm"]


# --------------------------------------------------------------------- CLI

def main():
    """Recalcula a cobertura de um mapa já reconstruído, sem refazer a tomografia."""
    p = argparse.ArgumentParser(description=main.__doc__)
    p.add_argument("survey", nargs="+", help="arquivo(s) JSONL do survey")
    p.add_argument("--mapa-dir", default="data/processed",
                   help="diretório com mapa_meta.json e aps.json")
    p.add_argument("--min-raios", type=int, default=MIN_RAIOS)
    p.add_argument("--min-diversidade", type=float, default=MIN_DIVERSIDADE)
    a = p.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import reconstruct

    d = Path(a.mapa_dir)
    meta = json.loads((d / "mapa_meta.json").read_text())
    aps = json.loads((d / "aps.json").read_text())
    origem = (meta["origem_x"], meta["origem_y"])
    passo, nx, ny = meta["grid"], meta["nx"], meta["ny"]

    medidas = reconstruct.carregar(a.survey)
    raios = []
    for m in medidas:
        info = aps.get(m["ap"])
        if info is None:
            continue
        pos = np.array([info["x"], info["y"]])
        if float(np.hypot(*(m["ponto"] - pos))) < 0.5:
            continue
        pesos = reconstruct.traçar_raio(pos, m["ponto"], np.array(origem), passo, nx, ny)
        if pesos:
            raios.append((pesos, tuple(m["ponto"] - pos)))

    print(f"{len(raios)} raios reconstruídos a partir de {len(medidas)} medidas\n")
    cont, div, comp = calcular(raios, nx, ny)
    resumo(cont, div, origem, passo, a.min_raios, a.min_diversidade)
    salvar(d, cont, div, comp, reconstruct.salvar_pgm)
    print(f"\nSalvo em {d}/: cobertura.csv, diversidade.csv, cobertura.pgm, diversidade.pgm")


if __name__ == "__main__":
    main()
