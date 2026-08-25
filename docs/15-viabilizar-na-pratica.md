# 15 — Viabilizar na prática: o que muda no projeto

<sub>Pesquisa: 2026-08-25</sub>

---

O que fazer com o que [`14`](14-as-cinco-camadas.md) levantou. Cada item aqui é uma ação, com
custo, pré-requisito e critério de sucesso — no formato do [`03`](03-roadmap.md), porque a
maioria destes itens **entra** no roadmap.

Regra que organiza a lista: **nada aqui gasta dinheiro, exceto §5, que está marcado como
opcional e fora do escopo de custo zero.**

---

## 1 · Descer para a camada 1 antes de subir: o teste de movimento

**Ideia importada:** presença/movimento é a única camada da escada que este hardware alcança
([`14 §14.2`](14-as-cinco-camadas.md)) — e é a que 10 milhões de roteadores já entregam com
~92,6% de acurácia. É resultado barato, imediato e **verificável sem ground truth de planta**.

**Por que isso vale antes da Fase 1 e não depois da Fase 5:** o risco número um do projeto não é
o algoritmo, é a **cadeia de medição**. Se o RSSI que o `nmcli` devolve estiver excessivamente
suavizado, cacheado pelo NetworkManager, ou atualizado a cada 30 s, a tomografia inteira é
construída sobre lixo — e você só descobre isso depois de um fim de semana medindo a casa. O
teste de movimento detecta essa falha em quinze minutos.

**Procedimento, com o código que já existe:**

```bash
# laptop parado num ponto fixo, casa vazia, ninguém entre ele e o AP
python3 src/survey.py --x 2 --y 2 --samples 30 --out data/raw/mov-vazio.jsonl

# repetir com uma pessoa parada exatamente na linha entre o laptop e um AP conhecido
python3 src/survey.py --x 2 --y 2 --samples 30 --out data/raw/mov-bloqueado.jsonl

python3 src/survey.py --summary data/raw/mov-vazio.jsonl
python3 src/survey.py --summary data/raw/mov-bloqueado.jsonl
```

**Critério de sucesso:** o AP bloqueado perde **≥ 3 dB** de mediana entre as duas condições,
e os APs em outras direções **não** perdem. Corpo humano atenua 3–6 dB em 2,4/5 GHz — número já
citado em [`03` Fase 1](03-roadmap.md) como fonte de ruído. Aqui ele é o **sinal**.

**Se falhar:** o problema é a cadeia de medição, não a física. Ordem de investigação:
(1) intervalo real de atualização do scan — forçar `nmcli device wifi rescan` entre amostras;
(2) suavização/histerese do driver; (3) AP com controle de potência automático; (4) mediana
sobre janela longa demais escondendo a variação.

**Custo:** 15 minutos. **Ganho:** valida ou invalida todo o resto do projeto.

---

## 2 · A pessoa como sonda: validar a localização dos APs com um oclusor móvel

**Este é o item de maior retorno da lista.** Ataca o elo mais fraco do projeto.

O ponto fraco declarado é a **posição estimada dos APs** ([D5](12-decisoes.md), e
[`03` Fase 2](03-roadmap.md) lista "APs mal localizados" como terceira causa de falha). Hoje
essas posições vêm de ajuste de mínimos quadrados sobre um modelo log-distance — e não há
como verificá-las de forma independente. Um AP mal localizado desloca todos os raios dele, e a
tomografia espalha o erro pelo mapa inteiro sem sinalizar nada.

**A ideia, emprestada da assimetria de [`14 §14.3`](14-as-cinco-camadas.md):** movimento é o
insumo mais barato em RF — então use um corpo humano como **atenuador de posição conhecida**.

O receptor fica fixo em `R`. O AP está na posição estimada `Â`. Uma pessoa caminha
perpendicularmente à reta `R–Â`, e você registra RSSI continuamente.

- Se `Â` estiver **certa**, a queda de 3–6 dB acontece quando a pessoa cruza a reta geométrica.
- Se `Â` estiver **errada**, a queda acontece em outro ponto do percurso — e o deslocamento
  angular entre onde caiu e onde deveria cair **mede o erro de estimativa**.

Você acabou de obter uma medição de erro de localização de AP sem trena, sem RTT e sem custo.
Repetido de dois pontos `R` diferentes, dá para **triangular a posição real do AP** e fixá-la
manualmente — que é justamente a mitigação recomendada em [`03` Fase 2](03-roadmap.md).

**Pré-requisito de ferramenta:** hoje o `survey.py` amostra e sai. Este teste exige série
temporal contínua com marcação de tempo. Especificação mínima de um `src/probe.py`:

| Entrada | `--ap <id de AP>` `--dur <s>` `--hz <taxa>` |
|---|---|
| Saída | JSONL de `{t, ap_id, rssi}` a taxa máxima que o driver permitir |
| Anotação | tecla pressionada marca "a pessoa cruzou agora" no registro |
| Análise | localizar o mínimo de RSSI e comparar com o instante anotado |

**Critério de sucesso:** o mínimo de RSSI e a marca manual caem dentro de **1 s** um do outro,
para ≥ 3 APs. Se cair, você tem tanto validação de AP quanto — de graça — uma demonstração
funcional de camada 1.

**Consequência para o roadmap:** este teste deveria ser **Fase 1b**, entre survey e
reconstrução. Ele é o único mecanismo proposto até agora que verifica um AP *individualmente*,
em vez de só olhar o mapa final e torcer.

---

## 3 · Mapa de cobertura: dizer em quais células o mapa tem direito de existir

**Ideia importada:** as camadas sobrepostas com procedência declarada do `gods-eye-view`
([`14 §14.7`](14-as-cinco-camadas.md)) — e, mais duro, a física de
[`14 §14.4`](14-as-cinco-camadas.md): sem largura de banda, **toda** a resolução vem do
cruzamento de raios. Logo, uma célula atravessada por 40 raios em ângulos variados é um
resultado; uma célula atravessada por 2 raios quase paralelos é um chute com aparência de
resultado.

Hoje o mapa não distingue as duas. Ele apresenta 200 células com a mesma tinta, e o leitor
supõe confiança uniforme onde ela não existe. É o mesmo pecado que [D14](12-decisoes.md) eliminou
na binarização — grau de liberdade escondido — mas na dimensão espacial.

**O que fazer:** a matriz de projeção `M` já é construída em `reconstruct.py`. As duas
estatísticas saem dela sem física nova:

| Camada | Cálculo | O que revela |
|---|---|---|
| Contagem de raios por célula | número de linhas de `M` com peso não nulo naquela coluna | onde há dado |
| Diversidade angular por célula | dispersão dos ângulos desses raios (ex.: 1 − \|média dos vetores unitários\|) | onde o dado **cruza** |

Salvar como `cobertura.csv` + `cobertura.pgm`, no mesmo referencial de
[`mapa_meta.json`](09-formato-dos-dados.md) ([D16](12-decisoes.md) já garante que dá para
sobrepor).

**Ganho imediato em cima de código existente:** o `compare.py` passa a poder avaliar **só as
células cobertas**. Isso é exatamente o argumento de [D15](12-decisoes.md) — "avaliar apenas o
que é fisicamente recuperável" — aplicado à cobertura em vez de ao tipo de parede. Sem isso, as
métricas de [`13`](13-avaliacao.md) misturam falha de reconstrução com ausência de medição, e
não há como saber qual das duas você está medindo.

**Critério de sucesso:** ≥ 80% das células com contagem ≥ 5 raios **e** diversidade angular
acima do limiar escolhido. Abaixo disso, a resposta não é ajustar regularização: é caminhar mais
([`14 §14.4`](14-as-cinco-camadas.md)).

---

## 4 · Declarar o orçamento de resolução

**Ideia importada:** a escada de frequência de [`14 §14.4`](14-as-cinco-camadas.md).

O projeto afirma resolução de "0,5 a 2 m" em [`01`](01-viabilidade.md) e usa célula de 0,5 m como
padrão. Os dois números são plausíveis, mas nenhum está derivado. Com `B → 0`, a resolução em
alcance é **infinita** (inexistente) e a resolução efetiva é fixada por três coisas, todas
sob seu controle:

| Fator | Onde está hoje | Efeito |
|---|---|---|
| Espaçamento dos pontos de coleta | `--step` do `groundtruth.py --plan` | define a abertura de medição |
| Diversidade angular obtida | §3 acima | define se a abertura é real ou degenerada |
| Força da regularização | parâmetros do solver ([`07`](07-teoria-tomografia.md)) | define quanto do mapa é dado e quanto é suavidade imposta |

**Ação concreta, sem coletar nada:** usar o simulador ([D10](12-decisoes.md)) para varrer
`--step` de 0,5 a 2,0 m e traçar a métrica de [`13`](13-avaliacao.md) contra número de pontos.
Isso produz a curva "quantos pontos você precisa medir para que a célula de 0,5 m signifique
alguma coisa" — e, com ela, uma escolha de grade justificada em vez de herdada.

**Cuidado já documentado:** o simulador valida a matemática, não a física
([`10`](10-validacao-sintetica.md)). A curva é um teto, não uma previsão.

---

## 5 · A escada de hardware, revista com os preços do campo ⚠️ *fora do custo zero*

O vídeo aponta módulos de radar baratos como a virada de acessibilidade do campo. É verdade —
com uma ressalva que nenhuma manchete menciona e que decide se a compra serve ou não para
**este** projeto.

**A ressalva:** quase todos os módulos baratos entregam **decisões**, não sinal. Presença
sim/não, distância até o alvo, taxa de respiração. Para tomografia e imageamento você precisa
de **perfil de alcance bruto** (range-Doppler ou ADC cru). Um módulo que só diz "tem alguém a
2,3 m" resolve camada 1 e 2 e não contribui em nada para geometria.

| Item | ~Custo | Saída | Serve para |
|---|---|---|---|
| HLK-LD2410 (24 GHz) | US$ 3–6 | presença + distância grosseira | camada 1 |
| Seeed 101991030 (24 GHz, FMCW) | **US$ 6,90** | presença configurável, ESPHome/Arduino | camada 1 |
| **ESP32-S3 + ESP32 CSI Toolkit** | **US$ 5–8** | **CSI: amplitude + fase por subportadora** | camadas 1–4 · **melhor compra do projeto** |
| DFRobot SEN0395 (24 GHz, 9 m) | US$ 20–30 | presença, alcance, ângulo limitado | camadas 1–2 |
| Seeed MR60BHA2 (60 GHz) | US$ 25–30 | respiração e pulso já processados | camada 3 (fechada) |
| TI IWR6843 / AWR1642 EVM | US$ 200–300 | **ADC bruto**, range-Doppler | imageamento de verdade |
| HackRF One | US$ 150 | IQ bruto em banda estreita | holografia ([D1](12-decisoes.md)) |

**Conclusão que não muda:** o **ESP32-S3 continua sendo a melhor compra**, e por um motivo que
o vídeo não dá — é o único item barato que devolve **fase**, e fase é o divisor de águas de
[`01 §1`](01-viabilidade.md). Um módulo mmWave de US$ 7 tem resolução em alcance cem vezes
melhor que o Wi-Fi (3,75 cm contra 7,5 m em HT20) e mesmo assim não ajuda, porque não expõe o
perfil onde essa resolução vive.

**Sobre "a versão de US$ 22"** (capítulo 10:17 do vídeo): não consegui confirmar qual placa é —
sem transcrição, e o artigo-companheiro está atrás de paywall. Um resumo secundário do texto
dele menciona "chips de radar de US$ 30". A faixa de preço está certa; o modelo específico é
**desconhecido** e não deve ser adivinhado. Se a transcrição aparecer, corrigir aqui e em
[`14 §14.0`](14-as-cinco-camadas.md).

---

## 6 · Vigilância tecnológica: 802.11bf é o desbloqueio que não custa nada

O muro do projeto é firmware ([`01 §3`](01-viabilidade.md)), e o 802.11bf-2025 padroniza
exatamente a interface que hoje falta: pedir medições de canal ao AP e recebê-las
([`14 §14.5`](14-as-cinco-camadas.md)). Nada a fazer hoje; muito a perder se ninguém olhar.

**Gatilhos para revisitar [D1](12-decisoes.md):**

| Observar | Onde | Se acontecer |
|---|---|---|
| Suporte a sensing no `mac80211` / `ath1xk` | changelog do kernel, `iw list` | testar imediatamente |
| Chipset doméstico com 802.11bf documentado (não só rótulo Wi-Fi 6/7) | datasheet do fabricante | é o momento de trocar de AP |
| 802.11az (ranging de próxima geração) no Android | `WifiRttManager` | resolve posição e AP de uma vez |
| Roteador do provedor expondo medições de sensing | app/API do provedor | fonte gratuita de camada 1–2 |

**Enquanto isso, o desbloqueio já disponível continua sendo Wi-Fi RTT/FTM** — já na
[Fase 3](03-roadmap.md), e vale repetir por que: fixar as posições dos APs elimina a maior
fonte de erro sistemático do mapa. É a Fase 3 que, na prática, deveria vir antes da Fase 2.

---

## 7 · Entregar em camadas, não em blob

**Ideia importada:** o `gods-eye-view` — 13 camadas sobrepostas, dados exclusivamente públicos,
procedência declarada por camada, código inspecionável.

A saída atual do projeto é um mapa ASCII e um PGM. É honesta e serve para depurar, mas não
permite responder à única pergunta que um leitor faz: *isto está certo?* Para isso é preciso ver
o mapa **contra** a referência, e ver onde havia dado.

**Camadas propostas, todas derivadas de arquivos que já existem ou de §3:**

| # | Camada | Origem |
|---|---|---|
| 0 | planta do ground truth | `groundtruth.py --render` |
| 1 | mapa de atenuação | `mapa.csv` |
| 2 | posições estimadas dos APs, com incerteza | `reconstruct.py` (+ §2 para a incerteza) |
| 3 | cobertura: contagem e diversidade angular de raios | §3 |
| 4 | pontos de coleta efetivamente visitados | `survey.jsonl` |
| 5 | diferença mapa − ground truth | `compare.py` |

Manter [D11](12-decisoes.md) intacta: sem dependência nova. Seis PGMs com o mesmo referencial de
[`mapa_meta.json`](09-formato-dos-dados.md) já permitem sobreposição em qualquer visualizador, e
o ASCII continua sendo a saída de terminal.

---

## 8 · Regulatório: o obstáculo que o vídeo mostra sem nomear

O capítulo 08:42 ("Why India Blocked the Pixel 4") é um caso concreto: o Pixel 4 não foi lançado
na Índia porque o Soli opera em **60 GHz**, faixa que o WPC indiano não havia liberado para uso
público — nem licenciada nem isenta. O aparelho inteiro ficou fora do mercado por causa de uma
faixa de espectro.

Isso não afeta as Fases 0–5, que usam **receptores** em faixas Wi-Fi já homologadas. Passa a
importar no momento em que o projeto **emitir** algo — e é exatamente o que qualquer módulo de
radar da tabela de §5 faz.

**Situação no Brasil**, para registro (verificar antes de comprar, não confiar nesta linha):

- **57–71 GHz**: há uso não licenciado previsto, com condições de EIRP e exigência de
  compartilhamento de acesso ao meio — **Ato Anatel nº 14448/2017** e alterações
  (nº 4776/2020, nº 423/2022, nº 14158/2025). O Brasil aparece entre os países que isentaram
  licença nessa faixa, ao contrário da Índia.
- **24,00–24,25 GHz** (narrowband): requisitos próprios, item 4.1.4 do Anexo I do mesmo Ato.
- **Homologação**: exigida para comercialização no país. Módulo de desenvolvimento importado
  para uso experimental próprio é situação distinta, e não vou opinar sobre ela aqui — não é
  matéria deste documento e eu não sou a fonte certa.

**Ação:** nenhuma agora. Registrado para que, se a compra de um módulo mmWave um dia entrar em
pauta, o item "verificar faixa e homologação" já esteja na lista em vez de ser descoberto depois.

---

## 9 · A linha que este projeto não atravessa

O campo inteiro descrito em [`14`](14-as-cinco-camadas.md) aponta para pessoas: respiração,
batimento, marcha, identidade, emoção. As camadas 3 a 5 estão fora de alcance deste hardware —
mas "fora de alcance" é uma limitação, e limitação muda quando alguém compra um ESP32-S3.

Por isso vale converter em decisão explícita, no espírito do `gods-eye-view`, que recusa
rastreamento individual por design e documenta a recusa:

> **O rf-sense mapeia o ambiente, não as pessoas nele.** Movimento humano é usado como
> ferramenta de calibração (§1, §2) e como sinal diferencial agregado — nunca para identificar,
> caracterizar ou acompanhar um indivíduo. Isso vale mesmo que o hardware passe a permitir.

Duas consequências operacionais, coerentes com [`05`](05-etica-e-privacidade.md):

- Os testes de §1 e §2 usam **você mesmo** como oclusor, em casa vazia, com consentimento
  trivial. Nunca terceiros que não saibam.
- Uma série temporal de RSSI é registro de ocupação. `data/` inteiro já está no `.gitignore`
  ([D9](12-decisoes.md)); as séries de §2 entram na mesma regra, e vale apagá-las depois da
  análise — elas não são reutilizáveis e são o dado mais sensível que o projeto produz.

---

## 10 · O que isto muda no roadmap

| Item | Fase | Custo | Depende de |
|---|---|---|---|
| §1 teste de movimento | **nova 0b**, antes do survey | 15 min | nada |
| §2 pessoa como sonda | **nova 1b**, antes da reconstrução | 1 h + `src/probe.py` | §1 passar |
| §3 mapa de cobertura | dentro da Fase 2 | código, sem coleta | matriz `M` já existente |
| §4 orçamento de resolução | antes da Fase 1 | só simulador | nada |
| §6 Wi-Fi RTT | **promover** Fase 3 → antes da Fase 2 | zero | AP com FTM |
| §7 entrega em camadas | dentro da Fase 2 | código, sem coleta | §3 |
| §5 hardware | Fase 6 | dinheiro | decisão de relaxar custo zero |
| §8 regulatório | só se §5 | zero | — |

**A ordem revista, e o motivo:**

```
0   ground truth                  ← inalterado, não pule
0b  teste de movimento            ← 15 min que validam a cadeia de medição
4'  orçamento de resolução        ← decide --step antes de gastar o fim de semana
3'  Wi-Fi RTT (se o AP cooperar)  ← promovido: fixa os APs, remove o maior erro
1   survey
1b  pessoa como sonda             ← verifica cada AP individualmente
2   reconstrução + cobertura      ← o marco, agora com camada de confiança
```

Nenhum item novo custa dinheiro e nenhum contradiz uma decisão de
[`12`](12-decisoes.md) — três delas (D3, D5, D15) ganham verificação empírica que antes não
tinham.
