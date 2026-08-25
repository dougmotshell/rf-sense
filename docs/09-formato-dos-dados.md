# 09 — Formato dos dados

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

PGM binário (P5), 8 bits. Densidade normalizada para 0–255 pelo máximo do mapa —
portanto **as intensidades não são comparáveis entre execuções diferentes**. Para comparar
mapas quantitativamente, use o CSV.

Cada célula da grade vira um bloco de `pgm_escala × pgm_escala` pixels, logo a imagem tem
`nx·pgm_escala × ny·pgm_escala`. A ampliação é nearest-neighbor e **não acrescenta
resolução**: a resolução física continua sendo `--grid`. Sem ela a imagem sairia com dezenas
de pixels de lado e nenhum visualizador a mostraria de forma legível. O fator é automático
(lado maior ≈ 600 px) e pode ser fixado com `--pgm-escala N`; `--pgm-escala 1` reproduz o
formato antigo, um pixel por célula.

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
  "n_raios": 383, "n_aps": 8, "pgm_escala": 38, "residuo_relativo": 0.493
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

## `data/raw/probe.jsonl` — série temporal do `probe.py`

Superconjunto do formato de survey, com uma linha de metadados na frente.

```json
{"evento":"meta","ts":1.77e9,"modo":"free","fonte":"nmcli","verificado":true,
 "rx_x":2.0,"rx_y":2.0,"z":1.0,"caminho":[1,1,1,5],"dur":180.0,"label":"vazio",
 "unidade":"dBm"}
{"ts":1.77e9,"fonte":"nmcli","canal":"a1b2c3d4e5f6","valor":-58.5,"unidade":"dBm",
 "quality":83,"freq_mhz":2412,"chan":1,"x":2.0,"y":2.0,"z":1.0,"label":"vazio"}
{"evento":"marca","ts":1.77e9}
```

| campo | obrigatório | significado |
|---|---|---|
| `canal` | ✅ | id da origem do sinal: AP hasheado, subportadora, alvo do radar |
| `valor` | ✅ | o número, na unidade declarada |
| `unidade` | ✅ | `dBm`, `m` ou `adim` — depende do modo |
| `fonte` | ✅ | backend que produziu (`nmcli`, `sim`, `esp32csi`, `mmwave`, ...) |

**Por que `canal`/`valor` e não `ap`/`rssi_dbm`:** um modo pago não devolve RSSI de AP.
`pago-mmwave` devolve distância a um alvo; `pago-csi` devolve amplitude e fase por
subportadora. Os nomes genéricos permitem que `probe.py` e o modo `replay` funcionem
sobre qualquer fonte. O `replay` aceita os dois formatos: se achar `ap`/`rssi_dbm`,
preenche `canal`/`valor` sozinho, então survey antigo continua legível.

Campos extras por tipo de fonte: `csi_amp[]`, `csi_fase[]`, `tem_fase` (CSI);
`alvo_x`, `alvo_y`, `vel_mps` (mmWave); `bins[]`, `noise`, `tsf` (spectral);
`oclusor_x`, `oclusor_y`, `bloqueio_db` (sim — a resposta certa, para conferir).

## `data/processed/aps_medidos.json` — APs por triangulação

```json
{
  "meu-roteador": {"x": 1.02, "y": 4.94, "metodo": "oclusao",
                   "n_raios": 2, "dispersao_m": 0.0}
}
```

Consumido por `reconstruct.py --aps-fixos`. Diferente de `aps.json`, que traz posições
**estimadas** por ajuste log-distance, aqui são posições **medidas** — a `dispersao_m`
é a discordância mediana entre os pares de raios usados, e serve de barra de erro.

O `aps.json` gerado passou a trazer também `origem`, com valor `"fixo"` ou
`"estimado"`, para que a camada 2 do `camadas.py` distinga as duas.

## `data/processed/cobertura.csv` e `diversidade.csv`

Mesma forma e mesmo referencial do `mapa.csv` ([D16](12-decisoes.md)).

| arquivo | unidade | significado |
|---|---|---|
| `cobertura.csv` | inteiro | raios que cruzam a célula |
| `diversidade.csv` | 0–1 | dispersão dos ângulos desses raios, no ângulo dobrado |

Célula é considerada **coberta** quando `cobertura >= min_raios` **e**
`diversidade >= min_diversidade`. Os dois limiares vão gravados em `mapa_meta.json`,
para que `compare.py --cobertura` reproduza exatamente a máscara usada.

`mapa_meta.json` ganhou também `frac_coberta`, `n_aps_fixos`, e — quando `--modo` é
passado — `modo`, `modo_verificado` e `delta_r_m`. O `modo_verificado: false` viaja com
o dado de propósito: um mapa feito com backend não testado precisa carregar esse aviso.

## `data/processed/poc.json` — veredito dos portões

```json
{"modo":"free","ts":1.77e9,"veredito":"BLOQUEADO",
 "portoes":[{"cod":"P0","nome":"cadência da cadeia de medição","estado":"ALERTA",
             "resumo":"0.133 Hz — só protocolo ESTÁTICO","detalhes":["..."]}]}
```

Estados: `PASSOU`, `ALERTA`, `REPROVOU`, `PULOU`. Guardar isto com data permite ver se
a cadeia de medição mudou entre coletas — atualização de kernel, troca de AP, outro
laptop.

## Convenções gerais

- **Distâncias em metros**, **potências em dBm**, **atenuações em dB**, **densidades em dB/m**.
- **Um único referencial** `(x, y)` compartilhado por survey, ground truth, APs e mapa.
  Se você mudar a origem no meio da coleta, o dataset inteiro é perdido — marque o `(0,0)`
  fisicamente no chão.
- **Todo `data/` está no `.gitignore`.** Medições contêm identificadores de rede de terceiros
  e não devem ser versionadas nem publicadas (`docs/05`).
