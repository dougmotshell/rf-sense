#!/usr/bin/env python3
"""
probe.py — camada 1 (movimento) e camada 2 (pessoa como sonda).

Implementa docs/15 §1 e §2, que existem para atacar as duas fraquezas do projeto
que nenhum ajuste de algoritmo resolve:

  §1 TESTE DE MOVIMENTO — o risco número um não é a matemática, é a CADEIA DE
     MEDIÇÃO. Se o RSSI que chega até aqui vem suavizado, cacheado ou atualizado
     a cada 30 s, a tomografia inteira se apoia em lixo. Um corpo humano atenua
     3–6 dB: se essa queda não aparece, nada mais vai.

  §2 PESSOA COMO SONDA — a posição dos APs é estimada por ajuste log-distance e
     nunca verificada (D5). Uma pessoa caminhando é um atenuador de posição
     CONHECIDA: quando ela cruza a reta AP->receptor, o sinal cai. Onde a queda
     acontece mede o erro da posição estimada — e, de dois receptores diferentes,
     TRIANGULA a posição real do AP, que pode então ser fixada na reconstrução.

Subcomandos:
    gravar      série temporal contínua de um ponto fixo
    movimento   §1 — quais canais reagiram ao movimento, e com que margem
    sonda       §2 — onde a queda ocorreu vs. onde deveria ocorrer
    triangular  §2 — cruza duas ou mais gravações e escreve aps_medidos.json

Funciona em qualquer modo de modos.py. Com --modo sim o oclusor é sintético e o
ciclo inteiro é verificável sem sair da cadeira.
"""

import argparse
import json
import math
import select
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fontes            # noqa: E402
import modos             # noqa: E402

LIMIAR_QUEDA_DB = 3.0     # corpo humano atenua 3–6 dB (docs/03 Fase 1)


# ------------------------------------------------------------------- utilidades

def par(s, n=2):
    """'1.5,2' -> (1.5, 2.0). Aceita n valores."""
    vals = [float(v) for v in s.replace(";", ",").split(",") if v.strip()]
    if len(vals) != n:
        raise argparse.ArgumentTypeError(f"esperava {n} números separados por vírgula: '{s}'")
    return tuple(vals)


def mediana_movel(v, janela):
    """Mediana móvel, para achar a queda sem ser enganado por um outlier."""
    if janela <= 1 or len(v) < janela:
        return np.asarray(v, dtype=float)
    v = np.asarray(v, dtype=float)
    metade = janela // 2
    est = np.pad(v, (metade, metade), mode="edge")
    return np.array([np.median(est[i:i + janela]) for i in range(len(v))])


def carregar_serie(caminho):
    """{canal: (ts[], valor[])} + metadados da gravação."""
    por_canal = defaultdict(lambda: ([], []))
    meta, marcas = {}, []
    with open(caminho) as f:
        for linha in f:
            if not linha.strip():
                continue
            r = json.loads(linha)
            if r.get("evento") == "meta":
                meta = r
                continue
            if r.get("evento") == "marca":
                marcas.append(r["ts"])
                continue
            ts, val = por_canal[r["canal"]]
            ts.append(r["ts"])
            val.append(r["valor"])
    series = {c: (np.array(t), np.array(v)) for c, (t, v) in por_canal.items()}
    return series, meta, marcas


def cruzamento(a, b, c, d):
    """Interseção dos segmentos a-b e c-d. Devolve (ponto, f_ab) ou None."""
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = a, b, c, d
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / den
    if not (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0):
        return None
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1)), t


def cruzamento_retas(p1, d1, p2, d2):
    """Interseção de duas retas infinitas (ponto, direção). Devolve ponto ou None."""
    den = d1[0] * (-d2[1]) - d1[1] * (-d2[0])
    if abs(den) < 1e-12:
        return None
    bx, by = p2[0] - p1[0], p2[1] - p1[1]
    t = (bx * (-d2[1]) - by * (-d2[0])) / den
    return (p1[0] + t * d1[0], p1[1] + t * d1[1]), t


# ------------------------------------------------------------------- gravação

def gravar(a):
    kw = dict(fonte_dev=a.fonte_dev, arquivo=a.arquivo, keep_bssid=a.keep_bssid,
              rescan=not getattr(a, "sem_rescan", False))
    if a.modo == "sim":
        kw.update(x=a.rx[0], y=a.rx[1], duracao=a.dur,
                  oclusor=a.caminho, atenuacao_db=a.atenuacao, ruido=a.ruido)
    try:
        fonte = fontes.abrir(a.modo, **kw)
    except (modos.ModoIndisponivel, RuntimeError) as e:
        sys.exit(f"\n{e}\n")

    destino = Path(a.out)
    destino.parent.mkdir(parents=True, exist_ok=True)

    print(f"modo {a.modo} · fonte {fonte.id} · receptor em {a.rx}")
    if a.caminho:
        print(f"caminho do oclusor: ({a.caminho[0]},{a.caminho[1]}) -> "
              f"({a.caminho[2]},{a.caminho[3]})")
    print(f"gravando {a.dur:.0f} s em {destino}")
    if a.marcar:
        print("APERTE ENTER no instante em que a pessoa cruzar a reta AP-receptor.")
    print("Mantenha o dispositivo na MESMA orientação e parado.\n")

    linhas = [{"evento": "meta", "ts": round(time.time(), 3), "modo": a.modo,
               "fonte": fonte.id, "verificado": fonte.VERIFICADO,
               "rx_x": a.rx[0], "rx_y": a.rx[1], "z": a.z,
               "caminho": list(a.caminho) if a.caminho else None,
               "dur": a.dur, "label": a.label,
               "unidade": fonte.unidade}]

    t_ini = time.time()
    n = 0
    marcas = []
    ultimo_print = 0.0
    try:
        while time.time() - t_ini < a.dur:
            regs = fonte.amostrar()
            if not regs and getattr(fonte, "esgotada", False):
                print("(arquivo de replay esgotado)")
                break
            for r in regs:
                r.update(x=a.rx[0], y=a.rx[1], z=a.z, label=a.label)
                linhas.append(r)
                n += 1
            decorrido = time.time() - t_ini
            if decorrido - ultimo_print >= 0.25:
                ultimo_print = decorrido
                print(f"\r  {decorrido:5.1f}s / {a.dur:.0f}s · {n} registros · "
                      f"{len(regs)} canais", end="", flush=True)
            if a.marcar and sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.readline()
                marcas.append(round(time.time(), 3))
                print(f"\n  marca {len(marcas)} em t={decorrido:.1f}s", flush=True)
            if a.hz > 0:
                time.sleep(max(0.0, 1.0 / a.hz))
    except KeyboardInterrupt:
        print("\n  interrompido")

    print()
    with open(destino, "w") as f:
        for r in linhas:
            f.write(json.dumps(r) + "\n")
        for ts in marcas:
            f.write(json.dumps({"evento": "marca", "ts": ts}) + "\n")
    fonte.fechar()

    canais = {r["canal"] for r in linhas if "canal" in r}
    print(f"\n{n} registros de {len(canais)} canais -> {destino}")
    print(f"\nAgora:  python3 src/probe.py movimento {destino}")
    if a.caminho:
        print(f"     e:  python3 src/probe.py sonda {destino}")


# --------------------------------------------------- portão 0: cadência da cadeia

# O que cada camada exige de TAXA EFETIVA de amostragem. Não é opinião: sai de
# Nyquist com folga sobre o fenômeno que se quer medir.
EXIGENCIA_HZ = [
    (0.05, "camada 1 com oclusor ESTÁTICO (pessoa parada na reta por ~1 min)"),
    (1.0,  "camada 1 com pessoa ANDANDO (a travessia dura 1-3 s)"),
    (2.0,  "camada 2 pessoa como sonda / triangulação (docs/15 §2)"),
    (5.0,  "camada 3 respiração (0,2-0,5 Hz de fenômeno)"),
    (10.0, "camada 3 batimento (1-2 Hz de fenômeno)"),
]


def medir_cadencia(a):
    """
    Mede a taxa EFETIVA da cadeia de medição, que não é a taxa com que se
    pergunta a ela.

    A distinção decide o que é possível: dá para consultar o nmcli a 1,6 Hz e
    receber 1,6 vez por segundo o MESMO valor em cache. O que importa é quantas
    vezes por segundo o número MUDA. Se a cadeia atualiza a cada 8 s, nenhuma
    esperteza de algoritmo recupera uma pessoa que atravessou em 2 s.

    Este é o portão 0 do POC, e ele roda antes de qualquer coleta.
    """
    kw = dict(fonte_dev=a.fonte_dev, arquivo=a.arquivo, keep_bssid=a.keep_bssid,
              rescan=not a.sem_rescan)
    if a.modo == "sim":
        kw.update(x=0.0, y=0.0, duracao=a.dur)
    try:
        fonte = fontes.abrir(a.modo, **kw)
    except (modos.ModoIndisponivel, RuntimeError) as e:
        sys.exit(f"\n{e}\n")

    print("=" * 72)
    print("PORTÃO 0 — CADÊNCIA DA CADEIA DE MEDIÇÃO")
    print("=" * 72)
    print(f"modo {a.modo} · fonte {fonte.id}"
          + ("" if fonte.VERIFICADO else "  [backend NÃO verificado]"))
    if a.modo == "free":
        print(f"rescan forçado: {'não' if a.sem_rescan else 'SIM'}"
              f"  (survey.py força; sem forçar, lê o cache)")
    print(f"medindo {a.dur:.0f} s...\n")

    ultimo, mudancas, latencias = {}, defaultdict(int), []
    consultas = 0
    t0 = time.time()
    try:
        while time.time() - t0 < a.dur:
            ti = time.time()
            regs = fonte.amostrar()
            latencias.append(time.time() - ti)
            consultas += 1
            for r in regs:
                c, v = r["canal"], r["valor"]
                if c in ultimo and v != ultimo[c]:
                    mudancas[c] += 1
                ultimo[c] = v
            if not regs and getattr(fonte, "esgotada", False):
                break
    except KeyboardInterrupt:
        print("  interrompido")
    dur = time.time() - t0
    fonte.fechar()

    if not ultimo:
        sys.exit("nenhum canal observado — a fonte não devolveu nada")

    hz_consulta = consultas / max(dur, 1e-9)
    taxas = sorted((n / dur for n in mudancas.values()), reverse=True)
    hz_efetivo = taxas[0] if taxas else 0.0
    hz_mediano = float(np.median(list(mudancas.values()) or [0])) / max(dur, 1e-9)

    print(f"canais observados       : {len(ultimo)}")
    print(f"consultas à fonte       : {consultas} em {dur:.1f} s "
          f"= {hz_consulta:.2f} Hz")
    print(f"latência por consulta   : mediana {np.median(latencias):.3f} s  "
          f"máx {max(latencias):.3f} s")
    print(f"canais que nunca mudaram: {len(ultimo) - len(mudancas)}/{len(ultimo)}")
    print(f"TAXA EFETIVA (melhor canal) : {hz_efetivo:.3f} Hz")
    print(f"TAXA EFETIVA (mediana)      : {hz_mediano:.3f} Hz")

    if hz_consulta > hz_efetivo * 3 and hz_efetivo > 0:
        print(f"\n  Consultando {hz_consulta/hz_efetivo:.0f}x mais rápido do que o dado")
        print("  muda. As amostras extras são o MESMO valor repetido — elas inflam a")
        print("  contagem de 'amostras por ponto' sem reduzir o ruído. A mediana de 15")
        print("  leituras de 3 valores distintos é a mediana de 3 valores.")

    print("\n-- O que esta cadência permite " + "-" * 40)
    for limite, texto in EXIGENCIA_HZ:
        ok = hz_efetivo >= limite
        print(f"  [{'ok ' if ok else 'NÃO'}] >= {limite:5.2f} Hz  {texto}")

    alcancado = [t for h, t in EXIGENCIA_HZ if hz_efetivo >= h]
    print()
    if not alcancado:
        print("  A cadeia é lenta até para oclusor estático. Antes de coletar, veja")
        print("  se há um caminho mais rápido:  python3 src/modos.py --detectar")
    elif len(alcancado) == 1:
        print("  Só o protocolo ESTÁTICO é viável neste modo: a pessoa fica PARADA")
        print("  na reta AP-receptor por ~1 min, e se compara com um trecho vazio.")
        print(f"    python3 src/probe.py gravar --modo {a.modo} --label vazio "
              f"--dur 120 --out data/raw/ab-vazio.jsonl")
        print(f"    python3 src/probe.py gravar --modo {a.modo} --label bloqueado "
              f"--dur 120 --out data/raw/ab-bloq.jsonl")
        print("    python3 src/probe.py movimento --ab data/raw/ab-vazio.jsonl "
              "data/raw/ab-bloq.jsonl")
        print("  A sonda de docs/15 §2 NÃO é viável aqui: ela precisa cronometrar")
        print("  a queda contra uma caminhada, e isso exige >= 2 Hz.")
    else:
        print("  Cadência suficiente para o protocolo dinâmico (pessoa andando).")
    return hz_efetivo


# ------------------------------------------------------ §1 teste de movimento

def analisar_ab(caminho_vazio, caminho_bloq, limiar):
    """
    Protocolo ESTÁTICO, para cadeias lentas: duas gravações longas, uma com a
    reta AP-receptor livre e outra com uma pessoa parada em cima dela. Compara
    medianas em vez de cronometrar uma queda — que é o que sobra quando a
    cadeia atualiza mais devagar do que uma pessoa atravessa.
    """
    sa, ma, _ = carregar_serie(caminho_vazio)
    sb, mb, _ = carregar_serie(caminho_bloq)

    print("=" * 72)
    print("CAMADA 1 — TESTE DE MOVIMENTO, PROTOCOLO A/B ESTÁTICO  (docs/15 §1)")
    print("=" * 72)
    print(f"A (livre)     : {caminho_vazio}  [{ma.get('label') or 'sem rótulo'}]")
    print(f"B (bloqueado) : {caminho_bloq}  [{mb.get('label') or 'sem rótulo'}]")
    if ma.get("rx_x") != mb.get("rx_x") or ma.get("rx_y") != mb.get("rx_y"):
        print("\n  ATENÇÃO: o receptor não estava na mesma posição nas duas gravações.")
        print("  A diferença medida abaixo inclui a mudança de geometria, e não só o corpo.")

    comuns = sorted(set(sa) & set(sb))
    if not comuns:
        sys.exit("nenhum canal em comum entre as duas gravações")

    print(f"\n{'canal':16} {'A dist':>7} {'B dist':>7} {'med A':>8} {'med B':>8} "
          f"{'queda':>7} {'signif':>7}  reagiu")
    print("-" * 76)
    reagiram, avaliaveis = 0, 0
    for c in comuns:
        va, vb = sa[c][1], sb[c][1]
        na, nb = len(set(va)), len(set(vb))     # valores DISTINTOS, não leituras
        med_a, med_b = float(np.median(va)), float(np.median(vb))
        queda = med_a - med_b
        # dispersão combinada dos valores distintos: a régua de significância
        disp = math.sqrt((np.std(list(set(va))) ** 2 + np.std(list(set(vb))) ** 2) / 2) or 1e-9
        signif = queda / disp
        confiavel = na >= 3 and nb >= 3
        avaliaveis += confiavel
        ok = confiavel and queda >= limiar and signif >= 1.5
        reagiram += ok
        marca = "SIM" if ok else ("-" if confiavel else "poucos")
        print(f"{c[:16]:16} {na:7d} {nb:7d} {med_a:8.1f} {med_b:8.1f} "
              f"{queda:7.2f} {signif:7.1f}  {marca}")

    print("\n-- Critério " + "-" * 60)
    print(f"  >= 3 valores DISTINTOS em cada lado, queda >= {limiar:.1f} dB, "
          f"significância >= 1,5")
    print(f"  canais avaliáveis: {avaliaveis}/{len(comuns)} · reagiram: {reagiram}")
    if avaliaveis == 0:
        print("\n  INCONCLUSIVO: nenhum canal teve 3 valores distintos. As gravações")
        print("  foram curtas demais para a cadência desta cadeia. Meça a cadência e")
        print("  multiplique: python3 src/probe.py cadencia --modo <modo>")
    elif reagiram >= 1:
        print("\n  APROVADO. A cadeia enxerga um corpo humano, no protocolo estático.")
        print("  Camada 1 funciona. A Fase 1 pode prosseguir.")
    else:
        print("\n  REPROVADO. Antes de culpar a física, verifique:")
        print("    1. a pessoa estava mesmo entre o receptor e ESTE AP?")
        print("    2. mesma orientação do dispositivo nas duas gravações?")
        print("    3. controle automático de potência no AP")
        print("  Compare com o teto: python3 src/probe.py cadencia --modo sim")


def analisar_movimento(a):
    if a.ab:
        return analisar_ab(a.ab[0], a.ab[1], a.limiar)
    series, meta, _ = carregar_serie(a.arquivo)
    if not series:
        sys.exit("nenhum registro na série")

    print("=" * 72)
    print("CAMADA 1 — TESTE DE MOVIMENTO  (docs/15 §1)")
    print("=" * 72)
    print(f"Gravação : modo {meta.get('modo','?')} · fonte {meta.get('fonte','?')}"
          f"{'' if meta.get('verificado', True) else '  [backend NÃO verificado]'}")
    print(f"Receptor : ({meta.get('rx_x')}, {meta.get('rx_y')})  "
          f"unidade {meta.get('unidade','dBm')}")

    dur = max(max(t) - min(t) for t, _ in series.values())
    taxa = np.mean([len(t) / max(dur, 1e-6) for t, _ in series.values()])
    print(f"Duração  : {dur:.1f} s · ~{taxa:.2f} amostras/s por canal")

    if taxa < 0.2:
        print("\n  ATENÇÃO: menos de uma amostra a cada 5 s. Nesta taxa o teste não")
        print("  detecta uma pessoa passando. Isso JÁ É um resultado: a cadeia de")
        print("  medição é lenta demais para camada 1 neste modo.")

    linhas = []
    for canal, (t, v) in sorted(series.items()):
        if len(v) < 5:
            continue
        suave = mediana_movel(v, a.janela)
        base = float(np.median(suave))
        i_min = int(np.argmin(suave))
        queda = base - float(suave[i_min])
        ruido = float(np.std(np.diff(v)) / math.sqrt(2)) or 1e-9
        linhas.append({"canal": canal, "base": base, "queda": queda,
                       "t_min": float(t[i_min]), "ruido": ruido,
                       "snr": queda / ruido, "n": len(v)})

    linhas.sort(key=lambda d: -d["queda"])
    print(f"\n{'canal':16} {'base':>8} {'queda':>8} {'ruído':>7} {'queda/ruído':>12}  reagiu")
    print("-" * 72)
    reagiram = 0
    for d in linhas:
        ok = d["queda"] >= a.limiar and d["snr"] >= 2.0
        reagiram += ok
        print(f"{d['canal'][:16]:16} {d['base']:8.1f} {d['queda']:8.2f} "
              f"{d['ruido']:7.2f} {d['snr']:12.1f}  {'SIM' if ok else '-'}")

    print("\n-- Critério de sucesso " + "-" * 48)
    print(f"  queda >= {a.limiar:.1f} dB com relação queda/ruído >= 2 em ao menos 1 canal")
    print(f"  canais que reagiram: {reagiram}/{len(linhas)}")
    if reagiram >= 1:
        print("\n  APROVADO. A cadeia de medição enxerga um corpo humano. Camada 1")
        print("  funciona neste modo, e a Fase 1 pode prosseguir.")
        if reagiram == len(linhas) and len(linhas) > 2:
            print("\n  Mas TODOS os canais caíram junto. Isso não é oclusão de um raio —")
            print("  é ganho automático do rádio, mudança de canal ou o corpo perto da")
            print("  antena. Refaça com a pessoa longe do receptor e perto do AP.")
    else:
        print("\n  REPROVADO — e o problema é a cadeia de medição, não a física.")
        print("  Investigue nesta ordem:")
        print("    1. intervalo real de atualização do scan (nmcli cacheia)")
        print("    2. suavização/histerese do driver")
        print("    3. controle automático de potência no AP")
        print("    4. a pessoa estava mesmo entre o receptor e ESTE AP?")
        print("  Compare com o teto teórico:  --modo sim  (docs/15 §1)")


# ------------------------------------------------------- §2 pessoa como sonda

def analisar_sonda(a):
    series, meta, marcas = carregar_serie(a.arquivo)
    caminho = a.caminho or (tuple(meta["caminho"]) if meta.get("caminho") else None)
    if not caminho:
        sys.exit("informe --caminho x0,y0,x1,y1 (a reta que a pessoa percorreu)")
    rx = a.rx or (meta.get("rx_x"), meta.get("rx_y"))
    if rx[0] is None:
        sys.exit("informe --rx x,y (posição do receptor durante a gravação)")

    A, B = (caminho[0], caminho[1]), (caminho[2], caminho[3])
    aps_est = json.loads(Path(a.aps).read_text()) if a.aps else {}

    print("=" * 72)
    print("CAMADA 2 — PESSOA COMO SONDA  (docs/15 §2)")
    print("=" * 72)
    print(f"Receptor : {rx}")
    print(f"Caminho  : {A} -> {B}   (percorrido em {meta.get('dur', '?')} s)")
    print(f"APs estimados fornecidos: {len(aps_est)}")
    if marcas:
        print(f"Marcas manuais: {len(marcas)} — servem de referência independente "
              f"do mínimo detectado")

    t_ini = min(min(t) for t, _ in series.values())
    t_fim = max(max(t) for t, _ in series.values())
    span = max(t_fim - t_ini, 1e-6)

    resultados = {}
    for canal, (t, v) in sorted(series.items()):
        if len(v) < 5:
            continue
        suave = mediana_movel(v, a.janela)
        i_min = int(np.argmin(suave))
        queda = float(np.median(suave) - suave[i_min])
        if queda < a.limiar:
            continue
        f = (t[i_min] - t_ini) / span
        p_emp = (A[0] + f * (B[0] - A[0]), A[1] + f * (B[1] - A[1]))
        d = (p_emp[0] - rx[0], p_emp[1] - rx[1])
        norma = math.hypot(*d) or 1e-9
        resultados[canal] = {
            "queda_db": round(queda, 2), "t_rel": round(f, 3),
            "cruzou_em": [round(p_emp[0], 3), round(p_emp[1], 3)],
            "direcao": [round(d[0] / norma, 5), round(d[1] / norma, 5)],
            "rx": [rx[0], rx[1]],
        }

    if not resultados:
        print(f"\nNenhum canal caiu {a.limiar:.1f} dB ou mais. Rode o teste de "
              f"movimento primeiro:\n  python3 src/probe.py movimento {a.arquivo}")
        return

    print(f"\n{'canal':16} {'queda':>7} {'t rel':>7} {'cruzou em':>16} "
          f"{'previsto':>16} {'erro':>7}")
    print("-" * 76)
    erros = []
    for canal, r in sorted(resultados.items(), key=lambda kv: -kv[1]["queda_db"]):
        prev_txt, erro_txt = "(sem AP est.)", ""
        info = aps_est.get(canal)
        if info:
            ap = (info["x"], info["y"])
            cr = cruzamento(A, B, rx, ap)
            if cr:
                p_prev, _ = cr
                erro = math.hypot(p_prev[0] - r["cruzou_em"][0],
                                  p_prev[1] - r["cruzou_em"][1])
                erros.append((canal, erro))
                prev_txt = f"({p_prev[0]:5.2f},{p_prev[1]:5.2f})"
                erro_txt = f"{erro:6.2f}m"
                r["previsto"] = [round(p_prev[0], 3), round(p_prev[1], 3)]
                r["erro_m"] = round(erro, 3)
            else:
                prev_txt = "não cruza"
        print(f"{canal[:16]:16} {r['queda_db']:7.2f} {r['t_rel']:7.2f} "
              f"({r['cruzou_em'][0]:5.2f},{r['cruzou_em'][1]:5.2f}) "
              f"{prev_txt:>16} {erro_txt:>7}")

    if marcas:
        print("\n-- Contra as marcas manuais " + "-" * 43)
        for canal, r in sorted(resultados.items(), key=lambda kv: -kv[1]["queda_db"])[:6]:
            t_min = t_ini + r["t_rel"] * span
            dt = min(abs(t_min - mk) for mk in marcas)
            print(f"  {canal[:16]:16} mínimo a {dt:5.2f} s da marca mais próxima"
                  f"   {'ok' if dt <= 1.0 else 'FORA de 1 s'}")
        print("  Critério de docs/15 §2: mínimo e marca dentro de 1 s um do outro.")

    print("\n-- Leitura " + "-" * 60)
    if erros:
        med = float(np.median([e for _, e in erros]))
        print(f"  erro mediano entre queda observada e prevista: {med:.2f} m")
        if med <= a.tolerancia:
            print(f"  Dentro de {a.tolerancia:.1f} m: as posições estimadas dos APs")
            print("  estão consistentes com a geometria observada. D5 verificado.")
        else:
            print(f"  Acima de {a.tolerancia:.1f} m: a posição estimada de pelo menos um AP")
            print("  está deslocada, e esse erro se espalha por todos os raios dele.")
            print("  Triangule a posição real e fixe-a na reconstrução:")
            print("    python3 src/probe.py triangular g1.jsonl g2.jsonl --out data/processed")
    else:
        print("  Sem APs estimados para comparar (passe --aps data/processed/aps.json).")
        print("  Ainda assim cada canal deu uma DIREÇÃO a partir do receptor — que é")
        print("  exatamente o insumo da triangulação:")
        print("    python3 src/probe.py triangular <esta> <outra de outro ponto>")

    if a.out:
        destino = Path(a.out)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(resultados, indent=2))
        print(f"\n  direções salvas em {destino}")


# ----------------------------------------------------- §2 triangulação de APs

def triangular(a):
    """Cada gravação dá, por canal, uma reta receptor -> ponto de oclusão.
    Duas retas de receptores diferentes se cruzam na posição real do AP."""
    raios = defaultdict(list)
    for arq in a.gravacoes:
        series, meta, _ = carregar_serie(arq)
        caminho = tuple(meta["caminho"]) if meta.get("caminho") else None
        rx = (meta.get("rx_x"), meta.get("rx_y"))
        if not caminho or rx[0] is None:
            print(f"  {arq}: sem caminho/receptor nos metadados — ignorada", file=sys.stderr)
            continue
        A, B = (caminho[0], caminho[1]), (caminho[2], caminho[3])
        t_ini = min(min(t) for t, _ in series.values())
        span = max(max(max(t) for t, _ in series.values()) - t_ini, 1e-6)
        for canal, (t, v) in series.items():
            if len(v) < 5:
                continue
            suave = mediana_movel(v, a.janela)
            i_min = int(np.argmin(suave))
            queda = float(np.median(suave) - suave[i_min])
            if queda < a.limiar:
                continue
            f = (t[i_min] - t_ini) / span
            p = (A[0] + f * (B[0] - A[0]), A[1] + f * (B[1] - A[1]))
            d = (p[0] - rx[0], p[1] - rx[1])
            n = math.hypot(*d) or 1e-9
            raios[canal].append({"rx": rx, "dir": (d[0] / n, d[1] / n),
                                 "queda": queda, "arquivo": arq})

    print("=" * 72)
    print("TRIANGULAÇÃO DE APs A PARTIR DE OCLUSÃO  (docs/15 §2)")
    print("=" * 72)
    medidos = {}
    for canal, rs in sorted(raios.items()):
        if len(rs) < 2:
            print(f"  {canal[:16]:16} só {len(rs)} raio — precisa de 2 receptores distintos")
            continue
        pontos = []
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                if math.dist(rs[i]["rx"], rs[j]["rx"]) < 0.5:
                    continue        # receptores quase no mesmo lugar: reta degenerada
                cr = cruzamento_retas(rs[i]["rx"], rs[i]["dir"],
                                      rs[j]["rx"], rs[j]["dir"])
                if cr and cr[1] > 0:            # à frente do receptor, não atrás
                    pontos.append(cr[0])
        if not pontos:
            print(f"  {canal[:16]:16} raios paralelos ou atrás do receptor")
            continue
        px = float(np.median([p[0] for p in pontos]))
        py = float(np.median([p[1] for p in pontos]))
        disp = float(np.median([math.hypot(p[0] - px, p[1] - py) for p in pontos]))
        medidos[canal] = {"x": round(px, 3), "y": round(py, 3),
                          "metodo": "oclusao", "n_raios": len(rs),
                          "dispersao_m": round(disp, 3)}
        print(f"  {canal[:16]:16} ({px:7.2f},{py:7.2f})  {len(rs)} raios  "
              f"dispersão {disp:5.2f} m")

    if not medidos:
        print("\nNada triangulado. É preciso ao menos duas gravações, de receptores")
        print("separados por >= 0,5 m, com o mesmo AP visível caindo nas duas.")
        return

    destino = Path(a.out) / "aps_medidos.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(medidos, indent=2))
    print(f"\n{len(medidos)} APs medidos -> {destino}")
    print("\nUse na reconstrução, em vez das posições estimadas:")
    print(f"  python3 src/reconstruct.py <survey> --aps-fixos {destino}")


# ------------------------------------------------------------------------ main

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gravar", help="série temporal de um ponto fixo")
    g.add_argument("--modo", default="sim", help="modo de modos.py (padrão: sim)")
    g.add_argument("--rx", type=lambda s: par(s, 2), default=(0.0, 0.0),
                   help="posição do receptor, 'x,y'")
    g.add_argument("--z", type=float, default=1.0)
    g.add_argument("--caminho", type=lambda s: par(s, 4), default=None,
                   help="reta percorrida pela pessoa, 'x0,y0,x1,y1'")
    g.add_argument("--dur", type=float, default=20.0, help="duração em segundos")
    g.add_argument("--hz", type=float, default=10.0,
                   help="taxa alvo de amostragem, Hz (0 = tão rápido quanto a fonte "
                        "permitir; com --modo sim isso gera milhares de amostras/s "
                        "e não representa nenhum rádio real)")
    g.add_argument("--atenuacao", type=float, default=5.0,
                   help="[sim] atenuação do corpo em dB")
    g.add_argument("--ruido", type=float, default=2.0, help="[sim] ruído em dB")
    g.add_argument("--marcar", action="store_true", help="anotar o cruzamento no ENTER")
    g.add_argument("--label", default="")
    g.add_argument("--fonte-dev", default=None, help="arquivo, /dev/ttyUSB0, udp:5566, -")
    g.add_argument("--arquivo", default=None, help="para --modo replay/free-rtt/free-bfi")
    g.add_argument("--keep-bssid", action="store_true")
    g.add_argument("--sem-rescan", action="store_true",
                   help="[free] lê o cache em vez de forçar varredura: rápido e "
                        "repetido. Mede a cadência antes de confiar nisso")
    g.add_argument("--out", default="data/raw/probe.jsonl")

    c = sub.add_parser("cadencia", help="portão 0 — taxa EFETIVA da cadeia de medição")
    c.add_argument("--modo", default="free")
    c.add_argument("--dur", type=float, default=45.0)
    c.add_argument("--sem-rescan", action="store_true",
                   help="[free] lê o cache do NetworkManager em vez de forçar varredura")
    c.add_argument("--fonte-dev", default=None)
    c.add_argument("--arquivo", default=None)
    c.add_argument("--keep-bssid", action="store_true")

    m = sub.add_parser("movimento", help="§1 — quais canais reagiram ao movimento")
    m.add_argument("arquivo", nargs="?", default=None)
    m.add_argument("--ab", nargs=2, metavar=("LIVRE", "BLOQUEADO"),
                   help="protocolo estático: duas gravações longas, para cadeias "
                        "lentas demais para cronometrar uma travessia")
    m.add_argument("--limiar", type=float, default=LIMIAR_QUEDA_DB)
    m.add_argument("--janela", type=int, default=5, help="janela da mediana móvel")

    s = sub.add_parser("sonda", help="§2 — onde a queda ocorreu vs. onde deveria")
    s.add_argument("arquivo")
    s.add_argument("--caminho", type=lambda x: par(x, 4), default=None)
    s.add_argument("--rx", type=lambda x: par(x, 2), default=None)
    s.add_argument("--aps", default=None, help="aps.json do reconstruct.py, para comparar")
    s.add_argument("--limiar", type=float, default=LIMIAR_QUEDA_DB)
    s.add_argument("--janela", type=int, default=5)
    s.add_argument("--tolerancia", type=float, default=1.0, help="erro aceitável em metros")
    s.add_argument("--out", default=None, help="salvar as direções em JSON")

    t = sub.add_parser("triangular", help="§2 — cruza gravações e mede a posição dos APs")
    t.add_argument("gravacoes", nargs="+")
    t.add_argument("--limiar", type=float, default=LIMIAR_QUEDA_DB)
    t.add_argument("--janela", type=int, default=5)
    t.add_argument("--out", default="data/processed")

    a = p.parse_args()
    if a.cmd == "movimento" and not a.arquivo and not a.ab:
        p.error("informe o arquivo, ou --ab LIVRE BLOQUEADO")
    {"cadencia": medir_cadencia, "gravar": gravar, "movimento": analisar_movimento,
     "sonda": analisar_sonda, "triangular": triangular}[a.cmd](a)


if __name__ == "__main__":
    main()
