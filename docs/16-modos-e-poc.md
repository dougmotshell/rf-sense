# 16 — Modos de operação e o POC

<sub>Medições nesta máquina: 2026-08-25</sub>

---

Dois assuntos que só fazem sentido juntos: **modos** (de onde o sinal vem, e o que
cada origem permite) e o **POC** (a pergunta única — dá para seguir, neste hardware,
hoje?). O primeiro é um registro declarativo; o segundo é o que mede a realidade e
confronta o registro com ela.

Implementa a escada de [`14`](14-as-cinco-camadas.md) e as ações de
[`15`](15-viabilizar-na-pratica.md).

---

## 16.1 O que é um modo

Um **modo** é um par *(fonte de dados, camada de sinal que ela entrega)*, e ele fixa
três coisas de uma vez:

1. Qual **camada** da escada fica ao alcance ([`14 §14.2`](14-as-cinco-camadas.md)).
2. Qual **resolução em alcance** a física permite, via `ΔR = c/(2·B)`
   ([`14 §14.4`](14-as-cinco-camadas.md)). Sem espectro, `B → 0` e não existe
   resolução ao longo do raio.
3. O que precisa **existir na máquina, ou ser comprado**.

```bash
python3 src/modos.py --listar         # a tabela inteira
python3 src/modos.py --gratis         # só os de custo zero
python3 src/modos.py --detectar       # o que roda NESTA máquina agora
python3 src/modos.py --camadas        # a escada, e qual modo destrava cada degrau
python3 src/modos.py --explicar free  # detalhe de um modo, com requisitos checados
```

### Os nove modos

| modo | custo | fase? | ΔR alcance | camadas 1–5 | backend |
|---|---|---|---|---|---|
| `sim` | grátis | não | inexistente | ✅ ✅ ❌ ❌ ❌ | planta conhecida + oclusor móvel |
| `free` | grátis | não | inexistente | ✅ 🟡 ❌ ❌ ❌ | RSSI de beacon via `nmcli` |
| `replay` | grátis | herda | herda | ✅ ✅ 📝 📝 ❌ | JSONL gravado |
| `free-root` | grátis | não | 1,87 m | ✅ ❌ ❌ ❌ ❌ | spectral scan `ath10k` (debugfs) |
| `free-bfi` | grátis | 🟡 ângulos | 1,87 m | ✅ 📝 ❌ ❌ ❌ | CBFR em modo monitor |
| `free-rtt` | grátis | não | — | 🟡 ✅ ❌ ❌ ❌ | Wi-Fi RTT/FTM, export do celular |
| `pago-csi` | US$ 8 | **sim** | 3,75 m | ✅ ✅ 📝 📝 ❌ | ESP32-S3 + ESP32 CSI Toolkit |
| `pago-mmwave` | US$ 22 | não | 0,60 m | ✅ ✅ 🟡 ❌ ❌ | módulo 24 GHz UART (LD2450) |
| `pago-sdr` | US$ 150 | **sim** | 7,49 m | ✅ ✅ 📝 📝 ❌ | IQ bruto (HackRF, TI IWR6843) |

✅ funciona · 🟡 parcial · 📝 código escrito, hardware não testado · ❌ fora

Duas leituras que a tabela torna óbvias e a conversa comum esconde:

- **O módulo mmWave de US$ 22 tem resolução em alcance 100× melhor que o Wi-Fi
  (0,60 m contra 7,5 m em HT20) e continua não servindo para geometria**, porque
  entrega uma *lista de alvos já decidida* em vez do perfil onde essa resolução vive.
  É a armadilha de [`15 §5`](15-viabilizar-na-pratica.md), agora explícita no código.
- **O ESP32-S3 de US$ 8 tem resolução pior que o módulo mmWave e é a melhor compra**,
  porque é o único item barato que devolve **fase** — o divisor de águas de
  [`01 §1`](01-viabilidade.md).

### A regra de precedência dos requisitos

`modos.py` classifica cada modo em `pronto`, `falta`, `comprar` ou `incerto`. A
precedência **não** é a ordem da lista: um requisito de **compra vence um binário
ausente**. Dizer "falta `hackrf_transfer`" a quem não tem um HackRF é diagnóstico
errado — não se instala o caminho para fora de não possuir o equipamento.

`incerto` existe para o que software não consegue verificar: se o seu AP suporta FTM,
se há tráfego 802.11ac com sounding na rede. Isso não é "disponível" nem "faltando";
é **teste manual**, e o registro diz qual.

### Backends verificados e não verificados

Só três backends foram exercitados de verdade: `sim`, `nmcli` e `replay`. Os outros
seis têm o parser escrito a partir da documentação do protocolo e **nunca rodaram
contra hardware**. Estão marcados com `VERIFICADO = False`, avisam em tempo de
execução, e o aviso viaja para dentro do `mapa_meta.json`.

Cada um oferece `dump_bruto()`, que mostra os bytes ou linhas crus sem
interpretação:

```bash
python3 src/fontes.py --modo pago-mmwave --fonte-dev /dev/ttyUSB0 --bruto
python3 src/fontes.py --modo free-root --bruto
```

Isso é deliberado: **se o parser estiver errado, o dump continua certo**, e é por ele
que se depura. Um parser não testado que finge estar testado é pior que nenhum.

---

## 16.2 O POC: cinco portões

```bash
python3 src/poc.py --modo free          # diagnostica o rádio real
python3 src/poc.py --modo sim           # prova a matemática de ponta a ponta
python3 src/poc.py --so-matematica      # pula o hardware
```

| portão | mede | critério |
|---|---|---|
| **P0 cadência** | quantas vezes por segundo o número **muda** | ≥ 0,05 Hz estático · ≥ 1 Hz dinâmico |
| **P1 quantização** | o menor degrau de sinal distinguível | degrau < 3 dB (senão engole o corpo humano) |
| **P2 visibilidade** | canais estáveis | ≥ 3 para funcionar, ≥ 8 pelo critério da Fase 1 |
| **P3 matemática** | reconstrói uma planta **conhecida**? | mesmo critério da Fase 2: F1 > 2× acaso e d < 0,6× acaso |
| **P4 campo** | existe ground truth da casa real? | ≥ 1 parede interna |

P0–P2 medem o rádio e dependem do `--modo`. **P3 roda sempre em modo `sim`**, porque
validar a matemática exige conhecer a resposta — é o único jeito de separar "o
algoritmo está errado" de "a coleta está ruim" ([D10](12-decisoes.md)).

O POC **para no primeiro portão reprovado** e diz qual. Seguir com um portão
reprovado não elimina o problema; move ele para depois, onde custa mais para achar.

---

## 16.3 O que foi medido nesta máquina

Dell Latitude 3400 · Atheros QCA6174 (`ath10k`) · modo `free` via `nmcli`.

### P0 — cadência: o achado que mudou o plano

| regime | consultas | latência mediana | mudanças de valor |
|---|---|---|---|
| cache (`--sem-rescan`) | **12,95 Hz** | 0,05 s | **0,113 Hz** |
| rescan forçado (o que o `survey.py` faz) | 0,13 Hz | **7,99 s** | 0,085 Hz |

**Teto de ~0,1 Hz nos dois regimes.** Um caminho é rápido e devolve valor velho; o
outro devolve valor fresco e custa 8 segundos. Não há terceira opção neste rádio.

Três consequências, e nenhuma delas era previsível sem medir:

1. **A pessoa como sonda ([`15 §2`](15-viabilizar-na-pratica.md)) não é viável no modo
   `free`.** Ela cronometra a queda contra uma caminhada que dura 1–3 s, e isso exige
   ≥ 2 Hz. Fica para `free-root` (spectral scan) ou `pago-csi`. **Isto corrige uma
   premissa de `docs/15`, que assumia cadência suficiente sem tê-la medido.**
   A matemática da sonda está validada — só não neste modo (§16.4).

2. **O teste de movimento passa a ter protocolo estático.** A pessoa fica *parada* na
   reta AP↔receptor por alguns minutos, e se compara medianas com um trecho vazio:
   ```bash
   python3 src/probe.py gravar --modo free --label vazio --dur 180 --out data/raw/ab-vazio.jsonl
   python3 src/probe.py gravar --modo free --label bloq  --dur 180 --out data/raw/ab-bloq.jsonl
   python3 src/probe.py movimento --ab data/raw/ab-vazio.jsonl data/raw/ab-bloq.jsonl
   ```

3. **"Amostras por ponto" e "medições independentes" são coisas diferentes.** A
   `--samples 15` do `survey.py` força rescan a cada amostra, então ali são 15
   medições reais — ao custo de ~2 min por ponto, que é de onde vem a estimativa de
   um fim de semana em [`03`](03-roadmap.md). Mas qualquer coleta que **não** force
   rescan produz o mesmo valor repetido: a mediana de 15 leituras de 3 valores
   distintos é a mediana de 3 valores. Por isso o `probe.py movimento --ab` conta
   **valores distintos**, não leituras.

### P1 — quantização

| grandeza | valor medido |
|---|---|
| menor degrau distinguível | **1,25 dB** |
| corpo humano (3 dB) | 2,4 degraus |
| parede interna (6 dB) | 4,8 degraus |

O `nmcli` reporta qualidade inteira de 0 a 100 e o projeto a converte para dBm
([`survey.py`](../src/survey.py)); o degrau observado é consequência disso. Funciona
— com pouca margem, e é bom saber a margem antes de interpretar um mapa.

### P2 e P3

- **P2:** 11 canais estáveis. Acima dos 8 do critério da Fase 1. ✅
- **P3:** com 48 pontos simulados e ruído de 2 dB, F1 = 0,656 (2,9× o acaso) e
  distância ponderada 0,60 m (0,48× o acaso). ✅ — **teto da matemática, não previsão
  da física** ([D10](12-decisoes.md)).

### Veredito atual

**BLOQUEADO em P4:** não existe `data/ground_truth.json`. O bloqueio do projeto hoje
não é hardware, não é algoritmo e não é dinheiro — é uma tarde com trena e fita
crepe ([D2](12-decisoes.md), [`03` Fase 0](03-roadmap.md)).

---

## 16.4 A sonda, validada onde é validável

A matemática de [`15 §2`](15-viabilizar-na-pratica.md) foi verificada contra a planta
do simulador, onde a resposta é conhecida — três gravações de receptores diferentes,
oclusor caminhando, triangulação por interseção de retas:

| AP | posição real | triangulada | erro |
|---|---|---|---|
| `meu-roteador` | (1,0 · 5,0) | (1,02 · 4,94) | **0,06 m** |
| `vizinho-oeste` | (−4,0 · 3,0) | (−4,48 · 3,01) | **0,48 m** |

Para comparação, o ajuste log-distance de [D5](12-decisoes.md) errou 0,56 e 0,68 m
nos cruzamentos previstos para os mesmos APs. O método funciona e é mais preciso —
**e a cadência do modo `free` não o alcança.** As duas coisas são verdade ao mesmo
tempo, e registrar só a primeira seria propaganda.

### O filtro de borda, achado pelo autoteste

A primeira versão triangulou o AP `corredor` com **2,89 m de erro**, e o
`scripts/selftest.sh` reprovou. A causa não era código, era geometria: a reta daquele
AP até o receptor cruzava o caminho em y = 5,75, **fora** do trecho percorrido (y de 1
a 5). A queda mais funda caiu na ponta do trajeto — não porque a pessoa cruzou ali, mas
porque foi o mais perto que ela chegou da reta — e a direção inferida saiu errada.

`probe.py` agora descarta mínimos nas pontas do trajeto (`--margem-borda`, 8% por
padrão). Não há como distinguir "cruzou no fim do caminho" de "cruzou depois do fim",
então as duas são descartadas: **um AP mal triangulado é pior que um AP ausente**,
porque desloca todos os raios dele e a tomografia espalha o erro pelo mapa sem
sinalizar nada.

O custo é perder o caso legítimo em que o AP está exatamente no fim do trajeto —
`meu-roteador`, em (1 · 5), com o caminho terminando em (1 · 5), passou a ser
descartado. Com o filtro, o que sobra é medido melhor: `vizinho-oeste` foi de 0,48 para
**0,21 m** de erro, porque os raios ruins saíram da mediana.

**Na prática:** caminhe trechos que passem *de fato* por baixo da reta do AP, e o
`sonda` diz quais canais descartou e por quê.

Quando houver um caminho ≥ 2 Hz, o consumo já está pronto:

```bash
python3 src/probe.py triangular g1.jsonl g2.jsonl --out data/processed
python3 src/reconstruct.py <survey> --aps-fixos data/processed/aps_medidos.json
```

---

## 16.5 Como refazer estas medidas

Nada aqui deve ser aceito por estar escrito. Todos os números de §16.3 saem de:

```bash
python3 src/probe.py cadencia --modo free --dur 45                # rescan forçado
python3 src/probe.py cadencia --modo free --dur 45 --sem-rescan   # cache
python3 src/poc.py --modo free --dur 45 --out data/processed/poc.json
```

O `--out` grava o veredito com data e detalhe por portão. Refaça em outra máquina,
ou em outro rádio, e os números **vão** mudar — a tabela de §16.3 é sobre este
laptop, não sobre Wi-Fi em geral.

---

## Em uma frase

O registro de modos diz o que cada origem de sinal *promete*; o POC mede o que ela
*entrega*; e a diferença entre os dois, neste laptop, foi um fator de vinte na
cadência — o suficiente para tirar a pessoa-como-sonda do modo gratuito e devolver
o protocolo estático em seu lugar.
