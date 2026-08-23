#!/usr/bin/env python3
"""
survey.py — coleta de RSSI georreferenciado (fase 1).

Em cada ponto da grade marcada no chão, roda-se este script informando a posição.
Ele varre as redes visíveis N vezes e grava uma linha JSON por amostra.

Cada linha vira, mais tarde, um "raio" da tomografia: AP -> ponto de medição.

Privacidade: por padrão o BSSID é substituído por um hash truncado, estável entre
execuções (mesmo AP -> mesmo id) mas não reversível. SSIDs não são gravados.
Use --keep-bssid apenas se precisar identificar seus próprios APs.
"""

import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

SALT = "rf-sense/v1"


def anon(bssid: str) -> str:
    return hashlib.sha256((SALT + bssid.upper()).encode()).hexdigest()[:12]


def nmcli_scan(force: bool = True):
    """Varre redes via nmcli. Retorna [(bssid, signal_0_100, freq_mhz, chan)]."""
    cmd = ["nmcli", "-t", "-e", "yes", "-f", "BSSID,SIGNAL,FREQ,CHAN", "dev", "wifi", "list"]
    if force:
        cmd.append("--rescan")
        cmd.append("yes")
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(f"nmcli falhou: {out.stderr.strip()}")

    redes = []
    for linha in out.stdout.splitlines():
        if not linha.strip():
            continue
        # nmcli escapa os ':' do BSSID como '\:' quando -t está ativo
        campos = re.split(r"(?<!\\):", linha)
        campos = [c.replace("\\:", ":") for c in campos]
        if len(campos) < 4:
            continue
        bssid, sinal, freq, chan = campos[0], campos[1], campos[2], campos[3]
        try:
            sinal = int(sinal)
            freq = int(freq.split()[0])  # "2412 MHz" -> 2412
            chan = int(chan)
        except (ValueError, IndexError):
            continue
        if not re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", bssid):
            continue
        redes.append((bssid, sinal, freq, chan))
    return redes


def qualidade_para_dbm(q: int) -> float:
    """
    Converte a qualidade 0-100 do nmcli para dBm aproximado.

    O NetworkManager deriva essa qualidade do dBm com um mapeamento monotônico;
    a inversa linear usual é dBm = q/2 - 100, válida na faixa -100..-50 dBm.
    É uma APROXIMAÇÃO: o valor absoluto pode errar alguns dB, mas o que a
    tomografia usa é a DIFERENÇA entre pontos, que se preserva.
    """
    return q / 2.0 - 100.0


def coletar(x, y, z, amostras, intervalo, keep_bssid, label):
    linhas = []
    for i in range(amostras):
        t = time.time()
        try:
            redes = nmcli_scan()
        except Exception as e:
            print(f"  ! varredura {i+1} falhou: {e}", file=sys.stderr)
            continue
        for bssid, sinal, freq, chan in redes:
            linhas.append({
                "ts": round(t, 3),
                "x": x, "y": y, "z": z,
                "ap": bssid if keep_bssid else anon(bssid),
                "rssi_dbm": qualidade_para_dbm(sinal),
                "quality": sinal,
                "freq_mhz": freq,
                "chan": chan,
                "label": label,
            })
        print(f"  varredura {i+1}/{amostras}: {len(redes)} APs", flush=True)
        if i < amostras - 1:
            time.sleep(intervalo)
    return linhas


def resumo(caminho):
    por_ponto = defaultdict(lambda: defaultdict(list))
    with open(caminho) as f:
        for linha in f:
            if not linha.strip():
                continue
            r = json.loads(linha)
            por_ponto[(r["x"], r["y"])][r["ap"]].append(r["rssi_dbm"])

    aps_todos = set()
    for aps in por_ponto.values():
        aps_todos |= set(aps)

    print(f"\nPontos de medição : {len(por_ponto)}")
    print(f"APs distintos     : {len(aps_todos)}")

    cobertura = []
    for ap in aps_todos:
        n = sum(1 for aps in por_ponto.values() if ap in aps)
        cobertura.append((n / len(por_ponto), ap))
    cobertura.sort(reverse=True)

    bons = [c for c, _ in cobertura if c >= 0.8]
    print(f"APs vistos em >=80% dos pontos: {len(bons)}")

    print("\nTop APs por cobertura:")
    for cob, ap in cobertura[:12]:
        vals = [v for aps in por_ponto.values() if ap in aps for v in aps[ap]]
        print(f"  {ap}  cobertura {cob*100:5.1f}%  mediana {statistics.median(vals):6.1f} dBm"
              f"  amplitude {max(vals)-min(vals):4.1f} dB")

    print("\n--- Critério de sucesso da fase 1 ---")
    ok_aps = len(bons) >= 8
    ok_pts = len(por_ponto) >= 20
    print(f"  [{'OK' if ok_aps else '--'}] >= 8 APs em >=80% dos pontos  (tem {len(bons)})")
    print(f"  [{'OK' if ok_pts else '--'}] >= 20 pontos de grade         (tem {len(por_ponto)})")
    if ok_aps and ok_pts:
        print("\n  Pronto para a fase 2: python3 src/reconstruct.py <arquivo>")
    else:
        print("\n  Colete mais antes de reconstruir — o problema inverso fica instável.")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--x", type=float, help="posição X em metros, na sua planta")
    p.add_argument("--y", type=float, help="posição Y em metros, na sua planta")
    p.add_argument("--z", type=float, default=1.0, help="altura em metros (padrão 1.0)")
    p.add_argument("--samples", type=int, default=15, help="varreduras neste ponto (padrão 15)")
    p.add_argument("--interval", type=float, default=1.0, help="segundos entre varreduras")
    p.add_argument("--label", default="", help="rótulo livre, ex: 'cozinha-porta'")
    p.add_argument("--out", default="data/raw/survey.jsonl", help="arquivo JSONL de saída")
    p.add_argument("--keep-bssid", action="store_true",
                   help="grava o BSSID real em vez do hash (evite: é dado pessoal)")
    p.add_argument("--summary", metavar="ARQUIVO", help="apenas resume um arquivo já coletado")
    a = p.parse_args()

    if a.summary:
        resumo(a.summary)
        return

    if a.x is None or a.y is None:
        p.error("informe --x e --y (ou use --summary)")

    print(f"Coletando em ({a.x}, {a.y}, {a.z}) — {a.samples} varreduras")
    print("Mantenha o dispositivo na MESMA orientação de sempre e fique parado.\n")

    linhas = coletar(a.x, a.y, a.z, a.samples, a.interval, a.keep_bssid, a.label)
    if not linhas:
        print("Nenhuma amostra coletada.", file=sys.stderr)
        sys.exit(1)

    destino = Path(a.out)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "a") as f:
        for r in linhas:
            f.write(json.dumps(r) + "\n")

    aps = {r["ap"] for r in linhas}
    print(f"\n{len(linhas)} amostras de {len(aps)} APs -> {destino}")


if __name__ == "__main__":
    main()
