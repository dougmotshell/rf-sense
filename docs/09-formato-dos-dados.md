# 09 — Formato dos dados

<sub><b>intelie</b> · Classificação ISO 27001: <b>PÚBLICO</b></sub>

---

## `data/raw/*.jsonl` — survey (entrada)

JSON Lines: **um objeto por linha**, uma linha por (varredura × AP visível). Formato de append,
para acumular vários pontos no mesmo arquivo. Produzido por `survey.py` e `simulate.py`.

```json
{"ts": 1787521234.939, "x": 0.0, "y": 0.0, "z": 1.0, "ap": "970b2be0217d",
 "rssi_dbm": -50.0, "quality": 100, "freq_mhz": 2412, "chan": 1, "label": ""}
```

| Campo | Tipo | Unidade | Descrição |
|---|---|---|---|
| `ts` | float | s | epoch Unix da varredura |
| `x`, `y` | float | m | posição do receptor na sua planta |
| `z` | float | m | altura do receptor (reservado para 2,5D) |
| `ap` | string | — | identificador do AP: SHA-256 truncado do BSSID, ou o BSSID real com `--keep-bssid` |
| `rssi_dbm` | float | dBm | potência recebida — **é o dado que a tomografia consome** |
| `quality` | int | 0–100 | valor cru do `nmcli`, preservado para auditoria |
| `freq_mhz` | int | MHz | frequência do canal |
| `chan` | int | — | número do canal |
| `label` | string | — | rótulo livre do operador |

### Notas importantes

- **`rssi_dbm` é derivado, não medido.** O `nmcli` entrega qualidade 0–100, não dBm. A conversão
  aplicada é `dBm = quality/2 − 100`, a inversa linear usual na faixa −100 a −50 dBm. O valor
  absoluto pode errar alguns dB; a **diferença entre pontos**, que é o que a tomografia usa,
  se preserva. `quality` fica gravado para permitir recalibrar depois.
- **Um AP multibanda aparece como dois `ap` distintos** (BSSIDs diferentes em 2,4 e 5 GHz).
  Isso é correto — são caminhos de propagação diferentes.
- **O hash tem salt fixo** (`"rf-sense/v1"` em `survey.py`), então o mesmo AP recebe o mesmo id
  entre execuções e máquinas. Mudar o salt invalida datasets antigos.
- **SSID nunca é gravado.** Ver `docs/05`.

### Consumo direto

```python
import json
with open("data/raw/survey.jsonl") as f:
    amostras = [json.loads(l) for l in f if l.strip()]
```

`reconstruct.py` agrega por `((x,y), ap, freq_mhz)` e usa a **mediana** do `rssi_dbm` — mediana,
não média, porque o RSSI tem outliers assimétricos.

---

## `data/processed/mapa.csv` — o mapa

Matriz de densidade de atenuação, `ny` linhas × `nx` colunas, separador vírgula, 4 casas.
**Unidade: dB/m.** Valores sempre `≥ 0`.

Origem geográfica e escala **não estão no CSV** — são impressas pelo `reconstruct.py`:

```
origem = (x_min − grid,  y_min − grid)        # canto inferior esquerdo
célula[iy][ix] cobre  x ∈ [origem_x + ix·grid, origem_x + (ix+1)·grid]
                      y ∈ [origem_y + iy·grid, origem_y + (iy+1)·grid]
```

⚠️ **Linha 0 do CSV é `y` mínimo** (o eixo Y cresce para baixo no arquivo). O mapa ASCII e o PGM
invertem para exibição, de forma que `y` cresça para cima como numa planta.

```python
import numpy as np
mapa = np.loadtxt("data/processed/mapa.csv", delimiter=",")   # shape (ny, nx)
```

---

## `data/processed/mapa.pgm` — imagem

PGM binário (P5), 8 bits, `nx × ny`. Densidade normalizada para 0–255 pelo máximo do mapa —
portanto **as intensidades não são comparáveis entre execuções diferentes**. Para comparar
mapas quantitativamente, use o CSV.

Já vem invertido verticalmente para leitura natural. Abre em GIMP, ImageMagick, `feh`, etc.

---

## `data/processed/mapa_meta.json` — georreferência do mapa

Sem este arquivo, `mapa.csv` é uma matriz sem posição no mundo. É o que permite ao
`compare.py` sobrepor o mapa ao ground truth.

```json
{
  "origem_x": 0.0, "origem_y": 0.0, "grid": 0.5, "nx": 16, "ny": 12,
  "unidade_valores": "dB/m",
  "n_percurso": 2.6, "n_referencia": 2.6, "lam": 0.05, "mu": 0.5,
  "n_raios": 383, "n_aps": 8, "residuo_relativo": 0.493
}
```

Além da georreferência, registra **os parâmetros que geraram aquele mapa** — sem isso, comparar
duas execuções vira adivinhação.

---

## `data/processed/aps.json` — APs estimados

```json
{
  "970b2be0217d": {"x": 1.03, "y": 4.92, "a_ref": -30.7, "rmse": 3.9}
}
```

| Campo | Unidade | Descrição |
|---|---|---|
| `x`, `y` | m | posição estimada, mesmo referencial do survey |
| `a_ref` | dBm | potência de referência a 1 m ajustada |
| `rmse` | dB | erro do ajuste log-distance — **>6 dB indica posição não confiável** |

Posições fora da área medida são **esperadas e desejáveis**: são APs de vizinhos, cujos raios
atravessam a casa inteira e dão os melhores ângulos de projeção.

---

## `data/ground_truth.json` — planta de referência (fase 0)

Consumido por `src/groundtruth.py` (validação, desenho, plano de coleta) e por
`src/compare.py` (avaliação). Exemplo pronto e testável em
`data/ground_truth.example.json` — é a mesma planta do simulador.
Mesma convenção de `PLANTA_EXEMPLO` em `simulate.py`: paredes como segmentos com atenuação.

```json
{
  "unidade": "metros",
  "origem": "canto inferior esquerdo da planta, coincide com (0,0) do survey",
  "paredes": [
    {"x0": 0.0, "y0": 0.0, "x1": 8.0, "y1": 0.0, "atenuacao_db": 12.0, "tipo": "externa"},
    {"x0": 3.5, "y0": 0.0, "x1": 3.5, "y1": 4.2, "atenuacao_db": 6.0, "tipo": "divisoria"}
  ],
  "portas": [
    {"x0": 3.5, "y0": 4.2, "x1": 3.5, "y1": 5.2}
  ]
}
```

Valores típicos de atenuação para preencher: drywall 3–5 dB, alvenaria 6–12 dB, laje 15–25 dB,
vidro 2–4 dB, porta de madeira 3–4 dB. São ordens de grandeza — meça se quiser precisão.

---

## Convenções gerais

- **Distâncias em metros**, **potências em dBm**, **atenuações em dB**, **densidades em dB/m**.
- **Um único referencial** `(x, y)` compartilhado por survey, ground truth, APs e mapa.
  Se você mudar a origem no meio da coleta, o dataset inteiro é perdido — marque o `(0,0)`
  fisicamente no chão.
- **Todo `data/` está no `.gitignore`.** Medições contêm identificadores de rede de terceiros
  e não devem ser versionadas nem publicadas (`docs/05`).
