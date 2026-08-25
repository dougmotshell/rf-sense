# 00 — Índice da documentação

---

**rf-sense** — usar Wi-Fi e Bluetooth para reconstruir a geometria de um ambiente interno,
com laptop e celular apenas, a custo zero.

## Por onde começar

| Se você quer... | Leia |
|---|---|
| Entender se isso é possível | [01 — Viabilidade](01-viabilidade.md) |
| Saber o que fazer amanhã | [03 — Roadmap](03-roadmap.md) |
| Rodar as ferramentas | [08 — Manual de uso](08-manual-de-uso.md) |
| Entender a matemática | [07 — Teoria](07-teoria-tomografia.md) |
| Ver se já funciona | [10 — Validação sintética](10-validacao-sintetica.md) |
| Saber se o SEU mapa ficou certo | [13 — Avaliação](13-avaliacao.md) |
| Um termo desconhecido | [11 — Glossário](11-glossario.md) |
| Entender o campo mais amplo de RF sensing | [14 — As cinco camadas](14-as-cinco-camadas.md) |
| Saber o que mudar no projeto a partir dele | [15 — Viabilizar na prática](15-viabilizar-na-pratica.md) |
| Saber se dá para seguir, hoje, neste hardware | [16 — Modos e POC](16-modos-e-poc.md) |

## Todos os documentos

### Fundamentos

- **[01 — Viabilidade](01-viabilidade.md)** — a física, o divisor de águas da fase, o que o
  hardware permite e o que não permite. **O documento mais importante.**
- **[02 — Hardware](02-hardware.md)** — inventário do laptop, checklist do celular,
  o que cada limitação implica, e o que um upgrade destravaria.
- **[04 — Análise crítica das fontes](04-analise-das-fontes.md)** — RuView, WhoFi, MIT Tech
  Review: o que as manchetes prometem versus o que os trabalhos entregam.
- **[14 — As cinco camadas do RF sensing](14-as-cinco-camadas.md)** — o campo inteiro em uma
  escada de capacidade, o orçamento de resolução (banda vs. abertura), 802.11bf e ISAC, e por
  que quase nada do campo ajuda diretamente aqui.
- **[11 — Glossário](11-glossario.md)** — RSSI, CSI, BFI, SAR, FTM, PCK e os demais termos.

### Execução

- **[03 — Roadmap](03-roadmap.md)** — as fases, cada uma com critério de sucesso verificável.
- **[16 — Modos e POC](16-modos-e-poc.md)** — os nove modos (free a US$ 150), os cinco
  portões do POC, e **o que foi medido nesta máquina**: cadência de 0,1 Hz, degrau de
  1,25 dB, e a correção que isso impôs a [`15 §2`](15-viabilizar-na-pratica.md).
- **[15 — Viabilizar na prática](15-viabilizar-na-pratica.md)** — as ações que saem do [`14`](14-as-cinco-camadas.md):
  teste de movimento, pessoa como sonda, mapa de cobertura, entrega em camadas. Altera a ordem
  das fases do [`03`](03-roadmap.md).
- **[08 — Manual de uso](08-manual-de-uso.md)** — todas as ferramentas, todos os parâmetros,
  procedimento de coleta e tabela de troubleshooting.
- **[09 — Formato dos dados](09-formato-dos-dados.md)** — schemas de entrada e saída, unidades,
  convenções de referencial.

### Técnico

- **[07 — Teoria: tomografia RF](07-teoria-tomografia.md)** — modelo direto, problema inverso,
  regularização, o solver, o viés do expoente, e por que não dá para fazer melhor sem fase.
- **[10 — Validação sintética](10-validacao-sintetica.md)** — o experimento que prova que o
  pipeline funciona, e o que ele revelou.
- **[13 — Avaliação](13-avaliacao.md)** — as métricas, por que duas famílias, o baseline medido
  e as metas para os dados reais.
- **[12 — Decisões de projeto](12-decisoes.md)** — as escolhas estruturais e o porquê de cada uma.

### Responsabilidade

- **[05 — Ética e privacidade](05-etica-e-privacidade.md)** — o que o projeto inevitavelmente
  captura de terceiros, as proteções já no código, e as regras de conduta.

### Fontes

- **[06 — Referências](06-referencias.md)** — papers, ferramentas e documentação, por tema.

## Código

| Arquivo | Papel | Doc |
|---|---|---|
| `scripts/check_capabilities.sh` | O que este rádio permite | [08](08-manual-de-uso.md) |
| `src/groundtruth.py` | Valida a planta, desenha e gera o plano de coleta | [08](08-manual-de-uso.md), [09](09-formato-dos-dados.md) |
| `src/simulate.py` | Survey sintético de planta conhecida | [08](08-manual-de-uso.md), [10](10-validacao-sintetica.md) |
| `src/survey.py` | Coleta de RSSI georreferenciado | [08](08-manual-de-uso.md), [09](09-formato-dos-dados.md) |
| `src/reconstruct.py` | Tomografia: localiza APs e resolve o mapa | [07](07-teoria-tomografia.md), [08](08-manual-de-uso.md) |
| `src/compare.py` | Avalia o mapa contra o ground truth | [13](13-avaliacao.md) |
| `src/poc.py` | **O MVP**: cinco portões e veredito | [16](16-modos-e-poc.md) |
| `src/modos.py` | Registro de modos free/pago e requisitos | [16](16-modos-e-poc.md) |
| `src/fontes.py` | Um backend de aquisição por modo | [16](16-modos-e-poc.md) |
| `src/probe.py` | Cadência, teste de movimento, sonda, triangulação | [15 §1–2](15-viabilizar-na-pratica.md) |
| `src/cobertura.py` | Onde o mapa tem direito de existir | [15 §3](15-viabilizar-na-pratica.md) |
| `src/orcamento.py` | Quantos pontos vale a pena medir | [15 §4](15-viabilizar-na-pratica.md) |
| `src/camadas.py` | Entrega em camadas com procedência | [15 §7](15-viabilizar-na-pratica.md) |

## Estado atual

| Fase | Estado |
|---|---|
| 0 — Ground truth (planta real) | 🟡 ferramenta pronta (`groundtruth.py`) — **falta medir a casa** |
| 1 — Survey de RSSI | ✅ implementada, não executada em campo |
| 2 — Reconstrução tomográfica | ✅ implementada e **validada**: F1 3,5× o acaso ([13](13-avaliacao.md)) |
| 2b — Avaliação objetiva | ✅ implementada (`compare.py`) |
| 3 — Densificar com o celular | ⬜ pendente |
| 4 — BFI em modo monitor | ⬜ pendente — requer `iw` e tráfego 802.11ac |
| 5 — Spectral scan `ath10k` | ⬜ pendente — requer parser de `fft_sample_ath10k` |
| 0b — Teste de movimento (camada 1) | ✅ implementado, **protocolo estático** ([16 §16.3](16-modos-e-poc.md)) |
| 1b — Pessoa como sonda (valida APs) | ✅ implementada, validada em `sim`; ⚠️ fora do modo `free` por cadência |
| 2c — Mapa de cobertura de raios | ✅ implementado (`cobertura.py`, `compare.py --cobertura`) |
| POC — os cinco portões | ✅ `poc.py`; hoje **BLOQUEADO em P4**: falta a planta da casa |

## Em uma frase

Não dá para gerar uma imagem 3D do ambiente com este hardware — imageamento coerente exige fase,
e nenhuma placa Wi-Fi comum a expõe. Dá para reconstruir **onde estão as paredes**, resolvendo
um problema inverso de atenuação sobre centenas de medições de potência. É um raio-X de
baixíssima resolução, e é gratuito.
