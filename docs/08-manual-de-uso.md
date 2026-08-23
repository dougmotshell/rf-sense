# 08 — Manual de uso

<sub><b>intelie</b> · Classificação ISO 27001: <b>PÚBLICO</b></sub>

---

## Requisitos

| Obrigatório | Status nesta máquina |
|---|---|
| `python3` | ✅ |
| `numpy` | ✅ |
| `nmcli` (NetworkManager) | ✅ |

| Opcional | Para quê |
|---|---|
| `matplotlib` | gráficos — o projeto já renderiza em ASCII e PGM sem ele |
| `iw` | modo monitor, fase 4 (BFI) — `sudo apt install iw` |
| `tshark` | dissecar frames de beamforming — `sudo apt install tshark` |

---

## `scripts/check_capabilities.sh`

Diagnóstico do que o rádio desta máquina permite. **Não altera nada no sistema** e roda sem
root (avisa o que precisaria de root).

```bash
./scripts/check_capabilities.sh
```

Verifica: chipset e driver, disponibilidade de CSI para aquele driver, spectral scan
(`CONFIG_ATH10K_SPECTRAL`, debugfs), modo monitor, versão do Bluetooth (AoA/Channel Sounding),
bibliotecas Python e existência de interface cabeada.

Legenda: `[ ok ]` disponível · `[ -- ]` indisponível · `[ ?? ]` inconclusivo (geralmente falta root).

---

## `src/simulate.py` — validar sem sair da cadeira

Gera um survey sintético a partir de uma planta **conhecida**. Como você sabe a resposta certa,
dá para verificar se o reconstrutor funciona antes de gastar um fim de semana medindo.

```bash
python3 src/simulate.py --out data/raw/sim.jsonl
```

| Flag | Padrão | Efeito |
|---|---|---|
| `--out` | `data/raw/sim.jsonl` | arquivo de saída |
| `--step` | `1.0` | espaçamento da grade de medição, em metros |
| `--samples` | `12` | amostras por ponto |
| `--noise` | `2.0` | desvio padrão do ruído, em dB (real fica entre 2 e 6) |
| `--seed` | `42` | semente — mesma semente, mesmos dados |

A planta e os APs estão em `PLANTA_EXEMPLO` e `APS_EXEMPLO`, no topo do arquivo. Editá-los para
imitar a sua casa é um bom teste: você descobre **quantos pontos precisa medir** antes de medir.

**Use `--noise` para calibrar expectativa.** Suba para 6 dB e veja o mapa degradar — é assim que
vai parecer na vida real.

---

## `src/groundtruth.py` — a planta de referência (fase 0)

Valida a planta que você mediu, desenha para conferência, e gera o **plano de coleta**:
quais pontos visitar e os comandos prontos.

```bash
cp data/ground_truth.example.json data/ground_truth.json   # e edite com as SUAS medidas
python3 src/groundtruth.py data/ground_truth.json                    # valida + desenha + plano
python3 src/groundtruth.py data/ground_truth.json --render
python3 src/groundtruth.py data/ground_truth.json --plan --step 1.0
```

| Flag | Padrão | Efeito |
|---|---|---|
| `--validate` | — | só valida o arquivo |
| `--render` | — | desenha a planta em ASCII (`#` parede, `+` porta) |
| `--plan` | — | gera o plano de coleta e os comandos |
| `--grid` | `0.5` | célula do desenho, em metros |
| `--step` | `1.0` | espaçamento da grade de coleta, em metros |
| `--margem-parede` | `0.4` | descarta pontos colados na parede (reflexão forte, viés de corpo) |
| `--survey-out` | `data/raw/survey.jsonl` | arquivo citado nos comandos gerados |

Sem nenhuma flag, faz as três coisas. **Sempre confira o `--render` antes de sair medindo** —
um erro de digitação na planta contamina toda a avaliação depois.

O `--plan` avisa se a grade gera menos de 20 pontos e estima o tempo de campo.

---

## `src/compare.py` — avaliar contra o ground truth

Transforma "o mapa ficou bom" em número. Metodologia completa em
[`docs/13`](13-avaliacao.md).

```bash
python3 src/compare.py data/processed data/ground_truth.json --tipos divisoria
```

| Flag | Padrão | Efeito |
|---|---|---|
| `--tipos` | todas | avalia só paredes destes tipos. **Use `divisoria`**: paredes externas são indetectáveis por construção |
| `--limiar` | percentil casado | densidade mínima (dB/m) para considerar parede |
| `--tolerancia` | 1 célula | raio, em metros, para contar uma previsão como próxima |

Imprime sobreposição (precisão, recall, F1, IoU), proximidade (distâncias às paredes), o
baseline aleatório de cada métrica, um mapa de acertos e erros, e uma leitura automática.

**Olhe a proximidade antes do IoU.** IoU baixo com boa proximidade é o resultado esperado:
manchas no lugar certo, mas espalhadas.

---

## `src/survey.py` — coletar

Roda **uma vez por ponto** da grade marcada no chão. Cada execução **acrescenta** ao arquivo
(modo append), então você acumula a casa inteira em um único `.jsonl`.

```bash
python3 src/survey.py --x 0 --y 0 --samples 15 --out data/raw/survey.jsonl
python3 src/survey.py --x 1 --y 0 --samples 15 --out data/raw/survey.jsonl --label "sala-centro"
```

| Flag | Padrão | Efeito |
|---|---|---|
| `--x`, `--y` | obrigatórios | posição em metros, na sua planta |
| `--z` | `1.0` | altura em metros (para um futuro mapa 2,5D) |
| `--samples` | `15` | varreduras neste ponto. **Não baixe disso** — RSSI é ruidoso |
| `--interval` | `1.0` | segundos entre varreduras |
| `--label` | `""` | rótulo livre, ex.: `"cozinha-porta"` |
| `--out` | `data/raw/survey.jsonl` | arquivo (append) |
| `--keep-bssid` | desligado | grava o MAC real. **Evite** — ver `docs/05` |
| `--summary ARQ` | — | não coleta; só resume um arquivo existente |

### Procedimento de coleta — as regras que decidem o resultado

1. **Marque uma grade no chão** com fita crepe, espaçamento ~1 m. Anote a origem `(0,0)`.
2. **Escolha uma direção "norte"** e aponte o laptop para ela **em todos os pontos**.
   O corpo humano atenua 3–6 dB; se você girar, injeta um viés sistemático que a tomografia
   vai interpretar como parede. Este é o erro nº 1.
3. **Casa vazia.** Ninguém circulando, nem você — fique parado durante a varredura.
4. **Cubra tudo**: cômodos, corredores, vãos de porta. Portas são a informação mais valiosa,
   porque é onde a parede *não* está.
5. **Não mude nada entre pontos**: não desligue o roteador, não mude de banda, não feche a tampa.
6. Ao terminar, rode o resumo.

### Resumo

```bash
python3 src/survey.py --summary data/raw/survey.jsonl
```

Imprime pontos coletados, APs distintos, cobertura de cada AP, amplitude do RSSI, e avalia o
critério de sucesso da fase 1 (**≥8 APs em ≥80% dos pontos** e **≥20 pontos**).

Se não passar, colete mais antes de reconstruir — o problema inverso fica instável e o mapa
vira arte abstrata.

---

## `src/reconstruct.py` — reconstruir

```bash
python3 src/reconstruct.py data/raw/survey.jsonl
python3 src/reconstruct.py data/raw/a.jsonl data/raw/b.jsonl --grid 0.4   # combina arquivos
```

| Flag | Padrão | Efeito |
|---|---|---|
| `--grid` | `0.5` | tamanho da célula em metros. Menor = mais detalhe **e mais instabilidade** |
| `--min-cobertura` | `0.6` | fração mínima de pontos em que o AP precisa aparecer para ser usado |
| `--n-percurso` | `2.6` | expoente log-distance para **localizar** os APs |
| `--n-referencia` | `2.0` | expoente de **referência** do excesso. Ver `docs/07 §7` ⚠️ |
| `--lam` | `0.05` | regularização de Tikhonov |
| `--mu` | `0.5` | peso da suavidade |
| `--out` | `data/processed` | diretório de saída |

### Como ler a saída

**Localização dos APs** — cada linha traz posição estimada, se caiu dentro ou fora da área
medida (APs de vizinhos caem fora, e isso é bom: os raios deles atravessam a casa toda),
`a_ref` e o `rmse` do ajuste.

> **`rmse` acima de ~6 dB significa posição não confiável.** Aumente `--min-cobertura` para
> descartar esse AP, ou colete mais pontos.

**Raios válidos** — a matéria-prima. Menos que `n_células/4` dispara aviso de sistema
subdeterminado. Com grade 0,5 m numa casa de 8×6 m são ~200 células, então mire em **≥500 raios**.

**Resíduo relativo** — `‖Mx−b‖/‖b‖`. Entre 20% e 50% é saudável com dados reais.
**Resíduo muito baixo é suspeito**, não bom: indica que você está ajustando ruído.

**O mapa ASCII** — rampa ` .:-=+*#%@` do livre ao denso, eixo Y crescendo para cima. O rodapé
traz a extensão em X, o tamanho da célula e o valor máximo em dB/m.

### Arquivos gerados em `--out`

| Arquivo | Conteúdo |
|---|---|
| `mapa.pgm` | imagem em tons de cinza, abre em qualquer visualizador ou GIMP |
| `mapa.csv` | a matriz de densidade, `ny` linhas × `nx` colunas, em dB/m |
| `aps.json` | posição estimada, `a_ref` e `rmse` de cada AP |

---

## Ajuste de parâmetros — o que mexer quando

| Sintoma | Provável causa | O que fazer |
|---|---|---|
| Mapa quase todo vazio | Excesso de atenuação ≈ 0 | Baixe `--n-referencia`; verifique se os APs foram bem localizados |
| Mapa uniformemente cinza | Viés do expoente (`docs/07 §7`) | Rode com `--n-referencia` igual a `--n-percurso` |
| Mapa granulado, tipo chuvisco | Regularização fraca | Suba `--mu` para 1.0–2.0 |
| Mapa borrado demais | Regularização forte | Baixe `--mu` para 0.2 |
| Paredes na posição errada | APs mal localizados | Confira o `rmse`; suba `--min-cobertura`; colete mais pontos |
| "Só N APs utilizáveis" | Cobertura baixa | Baixe `--min-cobertura` para 0.4, ou colete mais |
| "sistema muito subdeterminado" | Poucos raios | Suba `--grid` para 0.75 ou 1.0, ou colete mais pontos |
| Reconstrução muito lenta | Grade fina demais | Suba `--grid`; a localização dos APs é O(pontos × células) |

**Regra geral:** mexa em **um** parâmetro por vez e sempre compare com o mesmo dataset.
E antes de mexer em qualquer parâmetro, pergunte se o problema não é falta de dados — quase
sempre é.

---

## Fase 4 — captura de BFI (referência rápida)

```bash
sudo apt install iw
sudo ip link set wlp2s0 down
sudo iw dev wlp2s0 set type monitor
sudo ip link set wlp2s0 up
sudo iw dev wlp2s0 set channel 36 80MHz        # use o canal do SEU AP em 5 GHz
sudo tcpdump -i wlp2s0 -w data/raw/bfi.pcap

# para voltar ao normal:
sudo ip link set wlp2s0 down
sudo iw dev wlp2s0 set type managed
sudo ip link set wlp2s0 up
```

⚠️ **O Wi-Fi não conecta durante a captura.** Use o cabo (`enp1s0`).
⚠️ Grave **apenas** frames de gerenciamento e beamforming — ver `docs/05`.

Sem tráfego 802.11ac com sounding na rede, a captura vem vazia. Gere tráfego (um streaming em
outro aparelho) antes de concluir que não funciona.

---

## Fase 5 — spectral scan (referência rápida)

```bash
PHY=$(ls /sys/kernel/debug/ieee80211/)
echo background | sudo tee /sys/kernel/debug/ieee80211/$PHY/ath10k/spectral_scan_ctl
echo trigger    | sudo tee /sys/kernel/debug/ieee80211/$PHY/ath10k/spectral_scan_ctl
sudo timeout 60 cat /sys/kernel/debug/ieee80211/$PHY/ath10k/spectral_scan0 > data/raw/spectral.bin
echo disable    | sudo tee /sys/kernel/debug/ieee80211/$PHY/ath10k/spectral_scan_ctl
```

⚠️ Limite por **tempo**, não por contagem: o hardware ignora `spectral_count` e envia amostras
indefinidamente. O binário segue o formato `fft_sample_ath10k` de `spectral_common.h` do kernel
e ainda **não tem parser neste projeto**.
