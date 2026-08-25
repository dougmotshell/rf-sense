# rf-sense

> Estudo pessoal: **usar Wi-Fi e Bluetooth para "enxergar" o ambiente** — reconstruir a
> geometria do local (paredes, cômodos, espaço livre) sem câmera, usando só o laptop e o
> celular que eu já tenho. **Custo financeiro zero.**

---

<sub>
<i>Este projeto mede o rádio do ambiente, o que inevitavelmente capta sinais de terceiros.
Endereços MAC e SSIDs são dados pessoais: as medições brutas não são versionadas e não devem
ser publicadas — ver <a href="docs/05-etica-e-privacidade.md">docs/05</a>.</i>
</sub>

---

## O nome

**rf-sense** = **RF** + **sense**.

**RF** é *radiofrequência* — as ondas eletromagnéticas usadas para comunicação sem fio, aqui as
de Wi-Fi (2,4 e 5 GHz) e Bluetooth. **Sense** é *sensoriar*: usar essas ondas como instrumento
de medição do mundo físico, não como meio de transporte de dados.

Junto, **RF sensing** é o nome consagrado do campo — a ideia de que o rádio que já existe no
ambiente pode ser lido como um sensor. As ondas que o roteador emite para carregar seus pacotes
atravessam paredes, refletem em superfícies e são absorvidas por corpos. Cada uma dessas
interações deixa uma marca mensurável no sinal que chega até você. RF sensing é ler essa marca
de volta e inferir o que a causou.

É um campo real e ativo: o IEEE **ratificou** isso como **802.11bf-2025 (WLAN Sensing)** em
setembro de 2025, e provedores de internet já vendem detecção de presença embutida em roteadores
domésticos — uma implantação de mais de 10 milhões de roteadores reporta ~92,6% de acurácia de
detecção de movimento. O campo mais amplo, e o que dele se aproveita aqui, está em
[`docs/14`](docs/14-as-cinco-camadas.md) e [`docs/15`](docs/15-viabilizar-na-pratica.md).

Este projeto aplica a ideia a uma pergunta específica: **em vez de detectar pessoas, reconstruir
a geometria do lugar** — onde estão as paredes.

---

## A pergunta central, respondida de forma direta

**"Dá para usar Wi-Fi para gerar uma imagem 3D / topografia do ambiente?"**

Sim, a física permite — e já foi feito em laboratório (holografia de Wi-Fi, TUM 2017).
Mas **imageamento coerente exige medir a *fase* do sinal**, e nenhuma placa Wi-Fi comum
entrega fase. O chip deste laptop (**Atheros QCA6174 / `ath10k`**) não tem sequer ferramenta
de CSI disponível.

Então o projeto se divide em duas metades bem diferentes:

| | Imageamento **coerente** (holografia, SAR) | Mapeamento **incoerente** (tomografia, ocupação) |
|---|---|---|
| Precisa de fase? | **Sim** | Não — só potência |
| Produz | Imagem 3D, nuvem de pontos | Mapa 2D de atenuação / planta baixa |
| Resolução | ~cm | ~0,5–2 m (paredes, não objetos) |
| Hardware | SDR, CSI, arrays | **O que você já tem** |
| Viável aqui? | ❌ Não | ✅ **Sim** |

**Este projeto persegue a coluna da direita.** Não vamos gerar uma nuvem de pontos de
resolução centimétrica. Vamos gerar **um mapa da casa** — onde estão as paredes, onde é
espaço livre — resolvendo um problema inverso sobre centenas de medições de potência
feitas em posições diferentes. É tomografia, no espírito de um raio-X de baixíssima
resolução, não uma câmera.

## Sobre as manchetes "Wi-Fi enxerga através de paredes"

Você mandou três fontes (RuView/WiFi-DensePose, WhoFi da La Sapienza, matéria da Fast Company).
Elas são reais, mas descrevem **outra coisa**:

- Todas detectam ou identificam **pessoas**, não reconstroem **o ambiente**.
- Todas usam **CSI**, que exige hardware específico. O próprio RuView diz: é preciso
  "hardware capaz de CSI (ESP32-S3 ou NIC de pesquisa)"; laptops comuns só conseguem
  presença por RSSI.
- O RuView admite acurácia de pose de **~2,5% PCK@20** com labels proxy (a meta é 35%+),
  não tem demo em vídeo público e é alvo de ceticismo — embora a ciência de base seja real.

Ou seja: a manchete vende "visão de raio-X"; o artigo entrega "classificador de silhueta
em condições controladas". Detalhes em `docs/04-analise-das-fontes.md`.

## O que este projeto pretende entregar

1. Um **mapa 2D de atenuação** da sua casa, reconstruído por tomografia RF.
2. Uma **planta baixa aproximada** derivada desse mapa (paredes = regiões de alta atenuação).
3. Validação contra um **ground truth** medido — porque um mapa bonito e errado não vale nada.

## Hardware (tudo já disponível)

- **Laptop** Dell Latitude 3400 — Wi-Fi Atheros QCA6174 (`ath10k`), Bluetooth 4.2
- **Celular** — o sensor móvel que cria a diversidade espacial. É a peça mais importante.

Ver `docs/02-hardware.md`.

## Documentação

Se é a sua primeira vez aqui, o caminho é
**[`docs/17-comece-aqui.md`](docs/17-comece-aqui.md)** — manual em linguagem simples,
sem pressupor nada, com um roteiro de seis passos.

Índice completo em **[`docs/00-indice.md`](docs/00-indice.md)**.

| | |
|---|---|
| **[17 — Comece aqui](docs/17-comece-aqui.md)** | **o manual em linguagem simples — comece por este** |
| [01 — Viabilidade](docs/01-viabilidade.md) | a física, o muro da fase, o que dá e o que não dá |
| [02 — Hardware](docs/02-hardware.md) | inventário do laptop, checklist do celular |
| [03 — Roadmap](docs/03-roadmap.md) | as fases, com critério de sucesso cada uma |
| [04 — Análise das fontes](docs/04-analise-das-fontes.md) | RuView, WhoFi, MIT Tech Review, lidos criticamente |
| [05 — Ética e privacidade](docs/05-etica-e-privacidade.md) | o que se captura de terceiros, e as regras |
| [06 — Referências](docs/06-referencias.md) | papers e ferramentas, por tema |
| [07 — Teoria](docs/07-teoria-tomografia.md) | o modelo, o problema inverso, o solver |
| [08 — Manual de uso](docs/08-manual-de-uso.md) | parâmetros, procedimento de coleta, troubleshooting |
| [09 — Formato dos dados](docs/09-formato-dos-dados.md) | schemas, unidades, convenções |
| [10 — Validação sintética](docs/10-validacao-sintetica.md) | o experimento que prova que funciona |
| [11 — Glossário](docs/11-glossario.md) | RSSI, CSI, BFI, SAR, FTM, PCK... |
| [12 — Decisões de projeto](docs/12-decisoes.md) | as escolhas estruturais e o porquê |
| [13 — Avaliação](docs/13-avaliacao.md) | como saber, com número, se o mapa está certo |
| [14 — As cinco camadas](docs/14-as-cinco-camadas.md) | o campo de RF sensing inteiro, e o orçamento de resolução |
| [15 — Viabilizar na prática](docs/15-viabilizar-na-pratica.md) | as ações que saem do 14 — e o que muda no roadmap |
| [16 — Modos e POC](docs/16-modos-e-poc.md) | os nove modos free/pago, os cinco portões, e o que foi medido aqui |

## Estrutura

```
docs/       18 documentos — ver índice acima
src/        poc.py         o MVP: cinco portões e veredito
            modos.py       registro de modos free/pago e requisitos
            fontes.py      um backend de aquisição por modo
            probe.py       cadência · movimento · sonda · triangulação
            groundtruth.py simulate.py survey.py
            reconstruct.py cobertura.py compare.py
            orcamento.py   camadas.py
scripts/    check_capabilities.sh
data/       ground_truth.example.json  ·  raw/ e processed/ (gitignored)
```

## Começando

```bash
# 0. Dá para seguir, neste hardware, hoje? Cinco portões e um veredito.
python3 src/poc.py --modo free

# 0b. Quais modos existem, e o que roda nesta máquina
python3 src/modos.py --listar
python3 src/modos.py --detectar

# 1. O que o seu rádio permite (não altera nada no sistema)
./scripts/check_capabilities.sh

# 2. Validar o pipeline inteiro sem sair da cadeira, com uma planta conhecida
python3 src/simulate.py --out data/raw/sim.jsonl
python3 src/reconstruct.py data/raw/sim.jsonl --grid 0.5 --n-referencia 2.6
python3 src/compare.py data/processed data/ground_truth.example.json --tipos divisoria

# 3. Fase 0 — a planta da SUA casa, e o plano de coleta que ela gera
cp data/ground_truth.example.json data/ground_truth.json    # edite com suas medidas
python3 src/groundtruth.py data/ground_truth.json --render
python3 src/groundtruth.py data/ground_truth.json --plan --step 1.0

# 4. Campo: um comando por ponto (o --plan acima já os imprime prontos)
python3 src/survey.py --x 1 --y 1 --samples 15 --out data/raw/survey.jsonl
python3 src/survey.py --summary data/raw/survey.jsonl

# 5. Reconstruir e avaliar — só nas células que têm dado que as sustente
python3 src/reconstruct.py data/raw/survey.jsonl --grid 0.5 --n-referencia 2.6 --modo free
python3 src/compare.py data/processed data/ground_truth.json --tipos divisoria --cobertura

# 6. Entregar em camadas, cada uma com a procedência declarada
python3 src/camadas.py --survey data/raw/survey.jsonl --tipos divisoria
```

### Antes de gastar o fim de semana medindo

```bash
python3 src/probe.py cadencia --modo free    # a cadeia é rápida o bastante para o quê?
python3 src/orcamento.py                     # quantos pontos valem a pena, com número
```

Ver `docs/03-roadmap.md` para a ordem de ataque.

## O pipeline já funciona — validação sintética

`simulate.py` gera medições a partir de uma planta conhecida (8 x 6 m, uma parede vertical em
x=3.5 com vão de porta entre y=4.2 e 5.2, e uma parede horizontal em y=3.0 só na metade
direita), com 2 dB de ruído. `reconstruct.py` não sabe nada disso — recebe apenas RSSI e
posições. O que ele recupera:

```
  5.8 |.--=++@+##*:..:.|
  5.2 |- ... #-=..    :|
  4.8 |. :      ...:.::|   <- vão de porta: a parede some aqui, como deveria
  4.2 |+.  : -  ::-=-:=|
  3.8 |...=.-@+=::    .|
  3.2 |.     ##@*#=*#=:|   <- parede horizontal y=3.0, só na metade direita
  2.8 |*     %@#+-.:.: |
  2.2 |:    =+=--.:-=..|
  1.8 |.    -*+- -=--::|
  1.2 | .  ..=+:  .: ..|
  0.8 |      **-:.  :::|
  0.2 | ...:-:*+==: ...|
      +----------------+
      x de 0.0 a 8.0 m   (célula 0.50 m)
```

A coluna densa em x≈3.5, a parede horizontal restrita à metade direita e a falha no vão da
porta aparecem nas posições certas. É borrado — e vai ser borrado na vida real também. Wi-Fi
tem comprimento de onda de 5–12 cm e você está resolvendo um problema inverso mal-posto com
algumas centenas de raios. **Manchas na posição certa é o resultado esperado; bordas nítidas
seriam sinal de que algo está errado.**
