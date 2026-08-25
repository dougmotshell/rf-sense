#!/usr/bin/env bash
# selftest.sh — autoteste de ponta a ponta, determinístico e sem hardware.
#
# O projeto não tem suíte de testes unitários e não vai ter: o que importa aqui não
# é se uma função devolve o valor certo, é se o PIPELINE recupera uma planta que ele
# não conhece. Então o teste é o próprio experimento de docs/10, com asserção
# numérica em cima — e roda em ~1 min, sem rádio e sem rede.
#
# Só o modo `sim` é exercitado, porque é o único em que a resposta é conhecida
# (D10). Os modos que dependem de hardware são cobertos por dump_bruto(), não aqui.
set -euo pipefail

cd "$(dirname "$0")/.."
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
falhas=0

passo() { printf '\n\033[36m==>\033[0m %s\n' "$1"; }
ok()    { printf '  \033[32mok\033[0m   %s\n' "$1"; }
falha() { printf '  \033[31mFALHA\033[0m %s\n' "$1"; falhas=$((falhas+1)); }

# ---------------------------------------------------------------- 1. registro
passo "modos.py — registro consistente"
python3 src/modos.py --listar >/dev/null && ok "listar"
python3 src/modos.py --detectar >/dev/null && ok "detectar"
python3 src/modos.py --camadas >/dev/null && ok "camadas"
for m in sim free replay free-root free-bfi free-rtt pago-csi pago-mmwave pago-sdr; do
  python3 src/modos.py --explicar "$m" >/dev/null || falha "explicar $m"
done
ok "explicar, todos os 9 modos"

python3 - <<'PY' || falhas=$((falhas+1))
import sys; sys.path.insert(0, "src")
import modos, fontes
faltando = [m.nome for m in modos.MODOS.values() if m.fonte not in fontes.BACKENDS]
assert not faltando, f"modos sem backend: {faltando}"
orfaos = set(fontes.BACKENDS) - {m.fonte for m in modos.MODOS.values()}
assert not orfaos, f"backends sem modo: {orfaos}"
print("  ok   todo modo tem backend, e vice-versa")
PY

# ---------------------------------------------------------- 2. fonte sintética
passo "fontes.py — fonte sim e oclusor"
python3 - <<'PY' || falhas=$((falhas+1))
import sys; sys.path.insert(0, "src")
import fontes
f = fontes.abrir("sim", x=6.0, y=1.0, oclusor=(1, 1, 1, 5), duracao=1.0, ruido=0.0)
regs = f.amostrar()
assert len(regs) == 8, f"esperava 8 canais, veio {len(regs)}"
assert all(r["unidade"] == "dBm" for r in regs)
# sem ruído e com oclusor no início do caminho, algum canal deve estar bloqueado
import time; time.sleep(1.1)
bloq = max(r["bloqueio_db"] for r in f.amostrar())
assert bloq > 0.5, f"oclusor não bloqueou nada (max {bloq})"
print(f"  ok   8 canais, oclusor atenua {bloq:.2f} dB no fim do caminho")
PY

# ------------------------------------------------------- 3. camada 1 e sonda
passo "probe.py — camada 1 e triangulação (resposta conhecida)"
python3 src/probe.py gravar --modo sim --rx 6,1 --caminho 1,1,1,5 --dur 3 --hz 30 \
  --out "$TMP/g1.jsonl" >/dev/null
python3 src/probe.py gravar --modo sim --rx 6,5 --caminho 2,1,2,5 --dur 3 --hz 30 \
  --out "$TMP/g2.jsonl" >/dev/null
python3 src/probe.py movimento "$TMP/g1.jsonl" | grep -q "APROVADO" \
  && ok "movimento aprovado" || falha "movimento reprovou no simulador"
python3 src/probe.py gravar --modo sim --rx 1,3 --caminho 4,0.5,4,5.5 --dur 3 --hz 30 \
  --out "$TMP/g3.jsonl" >/dev/null
python3 src/probe.py triangular "$TMP/g1.jsonl" "$TMP/g2.jsonl" "$TMP/g3.jsonl" --out "$TMP" >/dev/null

python3 - "$TMP/aps_medidos.json" <<'PY' || falhas=$((falhas+1))
import json, math, sys
sys.path.insert(0, "src")
import simulate
reais = {a[0]: (a[1], a[2]) for a in simulate.APS_EXEMPLO}
medidos = json.load(open(sys.argv[1]))
assert medidos, "triangulação não produziu nenhum AP"
for canal, v in medidos.items():
    erro = math.dist((v["x"], v["y"]), reais[canal])
    assert erro < 1.5, f"{canal}: erro de {erro:.2f} m contra a posição real"
    print(f"  ok   {canal} triangulado a {erro:.2f} m da posição real")
PY

# -------------------------------------------------- 4. pipeline de tomografia
passo "pipeline — simulate -> reconstruct -> cobertura -> compare"
python3 src/simulate.py --out "$TMP/sim.jsonl" >/dev/null
python3 src/reconstruct.py "$TMP/sim.jsonl" --grid 0.5 --n-referencia 2.6 \
  --modo sim --out "$TMP/proc" --sem-cobertura >/dev/null
for f in mapa.csv mapa.pgm mapa_meta.json aps.json cobertura.csv diversidade.csv; do
  [ -s "$TMP/proc/$f" ] || falha "não gerou $f"
done
ok "seis artefatos gerados"

python3 - "$TMP/proc" <<'PY' || falhas=$((falhas+1))
import json, sys
import numpy as np
sys.path.insert(0, "src")
import compare
from groundtruth import carregar, rasterizar

d = sys.argv[1]
mapa = np.loadtxt(f"{d}/mapa.csv", delimiter=",")
meta = json.load(open(f"{d}/mapa_meta.json"))
assert meta["modo"] == "sim" and meta["delta_r_m"] is None, "meta do modo não gravado"

gt = carregar("data/ground_truth.example.json")
gt = dict(gt, paredes=[w for w in gt["paredes"] if w["tipo"] == "divisoria"])
origem = (meta["origem_x"], meta["origem_y"])
ny, nx = mapa.shape
real = np.array(rasterizar(gt, origem, meta["grid"], nx, ny), dtype=bool)
dist = compare.campo_de_distancia(gt, origem, meta["grid"], nx, ny)

livre = compare.avaliar(mapa, real, dist)
masc, _, _ = compare.carregar_cobertura(d, meta)
sob = compare.avaliar(mapa, real, dist, mascara=masc)

# o baseline de docs/13, com folga para não virar teste frágil
assert livre["ganho_f1"] > 2.0, f"F1 {livre['ganho_f1']:.1f}x o acaso, esperado > 2"
assert livre["razao_dist"] < 0.6, f"d {livre['razao_dist']:.2f}x o acaso, esperado < 0.6"
assert 0.3 < masc.mean() < 1.0, f"máscara cobre {masc.mean():.0%}, suspeito"
assert sob["ganho_f1"] > 2.0, "com máscara, F1 abaixo de 2x o acaso"
print(f"  ok   sem máscara: F1 {livre['ganho_f1']:.1f}x, d {livre['razao_dist']:.2f}x")
print(f"  ok   com máscara ({masc.mean():.0%} das células): "
      f"F1 {sob['ganho_f1']:.1f}x, d {sob['razao_dist']:.2f}x")
PY

# --------------------------------------------------------------- 5. camadas
passo "camadas.py — sete camadas e manifesto"
python3 src/camadas.py --mapa-dir "$TMP/proc" \
  --ground-truth data/ground_truth.example.json --survey "$TMP/sim.jsonl" \
  --tipos divisoria --out "$TMP/camadas" >/dev/null
n=$(ls "$TMP/camadas"/*.pgm 2>/dev/null | wc -l)
[ "$n" -eq 7 ] && ok "7 camadas em PGM" || falha "esperava 7 PGM, achei $n"
grep -q "Manifesto das camadas" "$TMP/camadas/MANIFESTO.md" \
  && ok "manifesto com procedência" || falha "manifesto ausente"

# -------------------------------------------------------------- 6. orçamento
passo "orcamento.py — régua comum entre configurações"
python3 src/orcamento.py --steps 1.0,2.0 --out "$TMP/curva.json" >/dev/null
python3 - "$TMP/curva.json" <<'PY' || falhas=$((falhas+1))
import json, sys
curva = json.load(open(sys.argv[1]))
assert len(curva) == 2, f"esperava 2 configurações, veio {len(curva)}"
# a régua comum tem de existir: sem ela a comparação entre steps não é comparação
assert all(l["f1_comum"] is not None for l in curva), \
    "f1_comum ausente: as molduras de grade não coincidiram"
assert all(l["regua"] == "comum" for l in curva), "avaliou sob a máscara própria"
print(f"  ok   régua comum aplicada a {len(curva)} configurações")
PY

# -------------------------------------------------------------------- 7. POC
passo "poc.py — portões e código de saída"
python3 src/poc.py --so-matematica --ground-truth data/ground_truth.example.json \
  --out "$TMP/poc.json" >/dev/null && ok "veredito LIBERADO, saída 0" \
  || falha "poc reprovou com a planta de exemplo"
python3 - "$TMP/poc.json" <<'PY' || falhas=$((falhas+1))
import json, sys
v = json.load(open(sys.argv[1]))
assert v["veredito"] == "LIBERADO", v["veredito"]
cods = {p["cod"]: p["estado"] for p in v["portoes"]}
assert cods["P3"] == "PASSOU" and cods["P4"] == "PASSOU", cods
assert all(cods[c] == "PULOU" for c in ("P0", "P1", "P2")), cods
print("  ok   P0-P2 pulados, P3 e P4 passaram")
PY

# ------------------------------------------------------------------ veredito
printf '\n%s\n' "------------------------------------------------------------"
if [ "$falhas" -eq 0 ]; then
  printf '\033[32mAUTOTESTE OK\033[0m — o pipeline recupera a planta que não conhece.\n'
  exit 0
fi
printf '\033[31m%d FALHA(S)\033[0m\n' "$falhas"
exit 1
