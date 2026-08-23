# 03 — Roadmap

---

**Objetivo final:** um mapa 2D da sua casa — paredes e espaço livre — reconstruído a partir de
medições de rádio, validado contra um ground truth medido.

Cada fase tem um **critério de sucesso verificável**. Se falhar, não avance: o erro se propaga
e você vai culpar o algoritmo por um problema de coleta.

---

## Fase 0 — Ground truth: a planta baixa de verdade · *primeiro passo*

Contraintuitivo, mas é aqui que começa. **Sem um mapa de referência você não tem como saber se
o mapa de RF está certo** — e um mapa errado que parece plausível é o pior resultado possível.

**Como, a custo zero:**
1. Meça a casa com trena ou passos calibrados. Desenhe a planta em papel quadriculado.
2. Digite em `data/ground_truth.json` — copie `data/ground_truth.example.json` e substitua as
   medidas (formato em [`docs/09`](09-formato-dos-dados.md)).
3. Confira o que digitou e gere o plano de coleta:
   ```bash
   python3 src/groundtruth.py data/ground_truth.json --render
   python3 src/groundtruth.py data/ground_truth.json --plan --step 1.0
   ```
   O `--plan` diz quantos pontos visitar, estima o tempo de campo e imprime os comandos prontos.
4. Marque no chão a **origem (0,0)** e a grade com fita crepe.

**Alternativas gratuitas de maior precisão:**
- **BatMapper** e afins: reconstroem planta baixa com o **alto-falante e microfone** do celular,
  por eco acústico. Não é RF, mas é custo zero e bem mais preciso que Wi-Fi.
- **ARCore / LiDAR** do celular, se tiver: apps de medição gratuitos dão planta baixa em minutos.

**Critério de sucesso:** `groundtruth.py --render` desenha algo reconhecível como a sua casa,
sem avisos de validação, e o `--plan` gera ≥ 20 pontos.

---

## Fase 1 — Survey de RSSI georreferenciado · *implementada*

**Objetivo:** transformar a casa em um conjunto de dados de "raios".

**Como:** em cada ponto da grade, rodar o coletor. Ele registra RSSI de todos os APs visíveis,
com a posição `(x, y)` que você informa.

```bash
python3 src/survey.py --x 0 --y 0 --samples 20 --out data/raw/survey.jsonl
python3 src/survey.py --x 1 --y 0 --samples 20 --out data/raw/survey.jsonl
# ... repita para toda a grade
python3 src/survey.py --summary data/raw/survey.jsonl
```

**Regras que decidem o sucesso da fase:**
- **Mesma orientação** do dispositivo em todos os pontos (o corpo humano atenua ~3–6 dB; se você
  girar, injeta ruído sistemático). Marque uma direção "norte" e sempre aponte para lá.
- **≥ 15 amostras por ponto** — RSSI é ruidoso; a mediana é o que vale.
- **Casa vazia**, sem outras pessoas se movendo.
- **Cobrir todos os cômodos**, inclusive corredores e portas.

**Critério de sucesso:** ≥ 8 APs vistos em ≥ 80% dos pontos, e ≥ 20 pontos de grade.
Menos que isso e o problema inverso fica subdeterminado demais.

---

## Fase 2 — Reconstrução tomográfica · *implementada*

**Objetivo:** o mapa.

Duas etapas, ambas em `src/reconstruct.py`:

**2a. Localizar os APs.** Suas posições são desconhecidas. Estimadas por ajuste de mínimos
quadrados sobre o modelo log-distance: `RSSI(d) = A - 10·n·log10(d)`. APs fora da casa
(vizinhos) vão cair fora da grade — isso é esperado e até útil, porque os raios deles
atravessam a casa inteira.

**2b. Resolver a tomografia.** Cada par (AP, ponto de medição) define um raio. O **excesso de
atenuação** em relação ao espaço livre é a integral da densidade ao longo do raio. Montamos a
matriz de projeção e resolvemos com regularização de Tikhonov + suavidade.

```bash
python3 src/reconstruct.py data/raw/survey.jsonl --grid 0.5 --out data/processed/
```

Saída: mapa ASCII no terminal, PGM (abre em qualquer visualizador) e CSV.

**Critério de sucesso:** medido, não olhado — ver [`docs/13`](13-avaliacao.md).

```bash
python3 src/compare.py data/processed data/ground_truth.json --tipos divisoria
```

Considera-se aprovado quando a distância ponderada às paredes fica **abaixo de 0,6× o acaso**
e o F1 supera **2× o acaso**. O `compare.py` imprime essa leitura sozinho.

No baseline sintético isso deu F1 = 0,684 (3,5× o acaso) e 0,68 m contra 1,43 m do acaso.
Esse é o **teto**; espere menos com dados reais.

**Se der errado, nesta ordem:** (1) poucos pontos de coleta; (2) orientação inconsistente;
(3) APs mal localizados — fixe manualmente os que você conhece; (4) regularização forte demais.

---

## Fase 3 — Densificar com o celular

**Objetivo:** mais raios, mais ângulos, melhor mapa.

- Rodar o mesmo survey no celular (Termux, gratuito) dobra a quantidade de dados e adiciona
  uma altura diferente — o que dá alguma informação **3D** grosseira (piso vs. altura do peito).
- Testar **Wi-Fi RTT** com o app **WifiRttScan**. Se seu AP suportar FTM, você ganha distância
  real (1–2 m com 3+ APs) e pode **fixar as posições dos APs** em vez de estimá-las — o maior
  ganho de qualidade disponível.
- Incluir **BLE** como fonte extra de raios (o RSSI de BLE é mais ruidoso, mas são mais links).

**Critério de sucesso:** ≥ 500 raios válidos no dataset combinado.

---

## Fase 4 — Informação angular via BFI

**Objetivo:** sair da tomografia por atenuação e chegar em algo mais parecido com **eco**.

Capturar Compressed Beamforming Reports — que trafegam **em texto claro, antes da criptografia** —
e extrair AoA dos caminhos de multipercurso. Cada percurso forte é o eco de uma parede.

```bash
sudo apt install iw
sudo ip link set wlp2s0 down
sudo iw dev wlp2s0 set type monitor
sudo ip link set wlp2s0 up
sudo iw dev wlp2s0 set channel 36 80MHz
sudo tcpdump -i wlp2s0 -w data/raw/bfi.pcap
```
Depois, extrair os BFAs com a **Wi-BFI** (open source).

**Critério de sucesso:** ≥ 100 frames com Compressed Beamforming Report em 10 min.
Se vier zero, sua rede não faz sounding — coloque o AP em 802.11ac/ax 80 MHz e gere tráfego
(um streaming em outro aparelho). Se ainda assim vier zero, encerre a fase sem culpa.

⚠️ Durante a captura o Wi-Fi não conecta. Use o cabo (`enp1s0`).

---

## Fase 5 — Spectral scan do `ath10k`

**Objetivo:** sinal com resolução temporal alta, para detectar **mudança** no ambiente
(alguém passando) em cima do mapa estático.

```bash
PHY=$(ls /sys/kernel/debug/ieee80211/)
echo background > /sys/kernel/debug/ieee80211/$PHY/ath10k/spectral_scan_ctl
echo trigger    > /sys/kernel/debug/ieee80211/$PHY/ath10k/spectral_scan_ctl
timeout 60 cat /sys/kernel/debug/ieee80211/$PHY/ath10k/spectral_scan0 > data/raw/spectral.bin
echo disable    > /sys/kernel/debug/ieee80211/$PHY/ath10k/spectral_scan_ctl
```

O binário segue o formato `fft_sample_ath10k` de `spectral_common.h` do kernel — exige parser.

⚠️ Caveats documentados: o hardware ignora `spectral_count` e manda amostras infinitas (limite
por **tempo**, como no `timeout` acima); funciona melhor em VHT80 que em HT20/HT40.

**Critério de sucesso:** espectrograma em que dá para ver alguém passando na frente do laptop.

---

## Fase 6 — Longo prazo

- Mapa **2,5D**: repetir o survey em duas alturas e interpolar.
- Tomografia **diferencial**: mapa com a casa vazia menos mapa com pessoa → onde está a pessoa.
  Esta é a forma correta de "ver pessoas" com este hardware.
- Comparar o mapa de RF com o mapa acústico do BatMapper e quantificar o erro.
- Se o custo zero for relaxado: um **ESP32-S3** (US$ 5–8) traz CSI; um **HackRF** (US$ 150) traz
  fase e, com ela, holografia de verdade.

---

## Ordem de ataque

```
Fase 0  (1 tarde)          →  ground truth        ← não pule
Fase 1  (1 fim de semana)  →  survey
Fase 2  (1 fim de semana)  →  PRIMEIRO MAPA       ← o marco do projeto
Fase 3  (contínuo)         →  densificar
Fase 4  (projeto à parte)  →  BFI, se a rede cooperar
Fase 5  (projeto à parte)  →  spectral scan
```

**Chegue até a fase 2.** Se o primeiro mapa se parecer minimamente com a sua casa, o projeto
já provou seu ponto. Tudo depois disso é refinamento.
