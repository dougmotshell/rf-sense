# 14 — As cinco camadas do RF sensing

<sub>Pesquisa: 2026-08-25</sub>

---

Análise do vídeo **"AI Can See Without Cameras. WiFi Was Just the Beginning."**
(Bilawal Sidhu, 31/07/2026, `olaQ3-m271M`) e das fontes que ele cita, lidos contra a mesma
pergunta de sempre: **isso reconstrói a geometria do ambiente, e roda no meu hardware?**

Este documento é o mapa do campo. O que **fazer** com ele está em
[`15 — Viabilizar na prática`](15-viabilizar-na-pratica.md).

---

## 14.0 Procedência: o que foi verificado e o que não foi

Honestidade sobre a base desta análise, porque ela muda o peso de cada afirmação abaixo:

| Fonte | Acesso | Consequência |
|---|---|---|
| Descrição do vídeo, capítulos, lista de fontes | ✅ completa | base factual desta análise |
| Transcrição / áudio do vídeo | ❌ não obtida | citações diretas do autor: nenhuma |
| Artigo-companheiro no Substack (`spatialintelligence.ai`) | 🟡 só a prévia | detalhes do capítulo 03:28 inacessíveis |
| Artigo anterior, *Your WiFi Can See You* | ✅ | papers e escada de capacidade confirmados |
| Papers e patentes citados | ✅ por título/DOI | verificáveis independentemente |

**Implicação direta:** a taxonomia de cinco camadas abaixo é uma **reconstrução minha** a partir
do título do capítulo (03:28 "Five Layers of RF Sensing") e da lista de capacidades da descrição
("breathing, heartbeats, location, pose, emotion and identity"). Não é uma citação. A ordem e os
nomes são meus; a substância vem dos papers, que são checáveis. Se algum dia a transcrição
estiver disponível, corrigir aqui.

Isto não é preciosismo: o projeto já decidiu ([D12](12-decisoes.md)) que documentar o limite do
que se sabe vale tanto quanto documentar o que se sabe.

---

## 14.1 A tese central, e por que ela importa aqui

> O rádio está se tornando um **meio de sensoriamento** tanto quanto um meio de comunicação —
> e a mesma infraestrutura que já existe pode, com IA, comunicar **e** perceber, em escala de
> sala, de prédio e de cidade, sem câmera.

Esta é a tese, e ela é sólida. O que a torna relevante para o rf-sense não é a parte
espetacular (batimento cardíaco através da parede), é a parte estrutural: **o sensoriamento
deixou de ser um subproduto acidental do rádio e passou a ser uma função declarada dele**. O
IEEE 802.11bf-2025 e o ISAC de 5G/6G são exatamente isso — ver §14.5.

Para um projeto que hoje precisa arrancar informação de sensoriamento de um canal que não foi
feito para entregá-la (RSSI de beacon), a notícia é boa a médio prazo e irrelevante a curto.

---

## 14.2 As cinco camadas

Cada camada exige estritamente mais informação de canal que a anterior. É uma escada, e o
degrau em que o hardware para é o degrau em que o projeto para.

### Camada 1 · Presença e movimento
**Mede:** há alguém no ambiente; algo mudou.
**Exige:** apenas **variação de potência ao longo do tempo**. Nada de fase, nada de banda larga.
**Evidência de escala:** implantação em >10 milhões de roteadores domésticos com ~92,6% de
acurácia de detecção de movimento. Provedores já vendem isso embutido.
**Veredito rf-sense:** ✅ **ao alcance hoje, com o hardware atual.** É a única camada da escada
que este laptop alcança sem nada novo. Ver [`15 §1`](15-viabilizar-na-pratica.md).

### Camada 2 · Localização e rastreamento
**Mede:** onde a pessoa/objeto está, com que trajetória.
**Exige:** distância (tempo de voo) ou ângulo (múltiplas antenas) ou muitos links com posições
conhecidas.
**Fontes:** localização mmWave em ambientes internos complexos (*Remote Sensing* 16(14):2572);
Wi-Fi RTT/FTM (802.11mc) e 802.11az.
**Veredito rf-sense:** 🟡 **parcial e invertido.** O projeto usa a camada 2 ao contrário: em vez
de descobrir onde a pessoa está a partir de posições conhecidas, ele descobre a geometria a
partir de posições que **você informa**. É o mesmo problema inverso com as incógnitas trocadas.
Wi-Fi RTT ([`03` Fase 3](03-roadmap.md)) é o que fecharia essa camada de graça.

### Camada 3 · Sinais vitais
**Mede:** respiração, batimento cardíaco.
**Exige:** sensibilidade a deslocamento sub-milimétrico → **fase coerente** ou radar FMCW de
banda larga. Deslocamento do tórax na respiração: ~4–12 mm. Do batimento: ~0,5 mm.
**Fontes:** MIT Vital-Radio; detecção de batimento através de parede com radar 24 GHz de canal
único; monitoramento com FMCW 77 GHz.
**Veredito rf-sense:** ❌ **fora de alcance, e por um fator enorme.** Precisão de deslocamento
de 0,5 mm com RSSI de beacon é da ordem de mil vezes além do que o canal entrega. Não é questão
de esforço.

### Camada 4 · Pose e gesto
**Mede:** esqueleto 3D, gesto de mão.
**Exige:** CSI multi-antena (ou radar mmWave) + rede treinada + dataset rotulado.
**Fontes:** DensePose from WiFi (CMU 2023); Person-in-WiFi 3D (CVPR 2024, ~92 mm de erro por
junta para uma pessoa, ~125 mm para três); Google **Soli** (60 GHz, gesto de mão em milímetros).
**Veredito rf-sense:** ❌ **fora de alcance** — já documentado em [`01 §5`](01-viabilidade.md) e
[`04`](04-analise-das-fontes.md). O que muda com este vídeo: nada. O que ele confirma: que a
lacuna entre "manchete" e "condição de laboratório" continua sendo o padrão do campo.

### Camada 5 · Identidade e estado interno
**Mede:** quem é a pessoa; possivelmente o estado emocional.
**Exige:** tudo da camada 3 ou 4, mais assinatura biométrica estável.
**Fontes:** RDGait (identidade por marcha com radar de chip único, `10.1145/3678552`); dataset de
reconhecimento de emoção em mmWave (*Nature*, `s41597-...`); WhoFi (95,5%, ver
[`04`](04-analise-das-fontes.md)); pesquisa de Karlsruhe reportando acurácia próxima de 100% em
197 participantes usando dados de beamforming.
**Veredito rf-sense:** ❌ **fora de alcance — e fora de escopo por decisão, não por limitação.**
Ver §14.7.

### Resumo

| Camada | Informação mínima | Hardware mínimo | rf-sense |
|---|---|---|---|
| 1 · Presença/movimento | potência vs. tempo | qualquer NIC | ✅ hoje |
| 2 · Localização | tempo de voo ou ângulo | RTT/FTM, ou muitos links | 🟡 invertida |
| 3 · Sinais vitais | fase, sub-mm | radar FMCW / CSI calibrado | ❌ |
| 4 · Pose/gesto | CSI multi-antena + IA | ESP32-S3, mmWave, GPU | ❌ |
| 5 · Identidade | biometria estável | idem 3/4 | ❌ e vetado |

---

## 14.3 A assimetria que o vídeo revela sem dizer

**Todas as cinco camadas são sobre pessoas. O rf-sense é sobre paredes.** Parece um detalhe de
alvo; é uma diferença de física.

Uma pessoa **se move**. Isso dá de graça três coisas que o campo inteiro explora:

1. **Doppler** — a frequência de retorno desloca-se, o que separa o alvo do fundo estático.
2. **Subtração de fundo** — tudo que não muda pode ser cancelado. O ambiente vira ruído
   descartável, e o alvo vira o resíduo.
3. **Repetição** — respiração e batimento são periódicos, então filtrar na frequência certa
   ganha uma quantidade absurda de SNR.

Uma parede não oferece nenhuma das três. Ela é exatamente o fundo que todo mundo subtrai.

**Consequência prática, e é a mais importante deste documento:** o rf-sense escolheu o alvo
*mais difícil* do campo com o hardware *mais fraco* do campo. Isso não invalida o projeto —
[`01`](01-viabilidade.md) já mostrou que tomografia por atenuação funciona sem Doppler nem fase.
Mas explica por que praticamente nenhum trabalho citado no vídeo ajuda diretamente aqui, e por
que o mapa sintético de [`10`](10-validacao-sintetica.md) é borrado por natureza e não por
imperícia.

E aponta a inversão útil: **se o movimento é o insumo mais barato do campo, use-o.** É o que a
tomografia diferencial faz ([`15 §2`](15-viabilizar-na-pratica.md)).

---

## 14.4 A escada de frequência — e o número que faltava no projeto

O vídeo (e a prévia do artigo) contrapõe Wi-Fi em 5 GHz, que dá um "borrão de granularidade
grossa", a mmWave em 24–60 GHz, que dá uma "imagem clínica". A intuição comum é que a diferença
está no comprimento de onda. **Está principalmente na largura de banda.**

Resolução em **alcance** (ao longo do raio) de qualquer sistema de eco:

```
ΔR = c / (2·B)          c = 3·10⁸ m/s,  B = largura de banda
```

| Sistema | Banda B | ΔR |
|---|---|---|
| Wi-Fi HT20 | 20 MHz | **7,5 m** |
| Wi-Fi VHT80 | 80 MHz | 1,88 m |
| Wi-Fi VHT160 | 160 MHz | 0,94 m |
| Radar 24 GHz ISM | 250 MHz | 0,60 m |
| mmWave 60 GHz (módulo típico) | 4 GHz | **3,75 cm** |
| Radar automotivo 77–81 GHz | 4 GHz | 3,75 cm |

Resolução **transversal** ao raio vem de outra coisa — da **abertura**, real ou sintética:

```
Δ⊥ ≈ R · λ / D          D = abertura,  R = distância
```

Com abertura sintética de 1 m em 5 GHz (λ = 6 cm), a 3 m de distância: **18 cm**. É exatamente
por isso que a holografia de Wi-Fi da TUM funciona com banda estreita
([`01 §2`](01-viabilidade.md)): quem paga a resolução transversal é a abertura. As duas
afirmações convivem — banda resolve *ao longo* do raio, abertura resolve *através* dele.

**E o RSSI?** Um beacon entrega **um número de potência**. Não há espectro, então B → 0 e
`ΔR = ∞`: **a tomografia por atenuação não tem resolução em alcance nenhuma.** Ela não sabe
*onde* no raio estava a parede — sabe apenas que o raio inteiro perdeu 12 dB. Toda a resolução
do mapa vem do **cruzamento de raios de posições diferentes**, ou seja: da abertura formada
pelos seus pontos de coleta.

Isso é a justificativa física de [D3](12-decisoes.md) ("o celular é o sensor principal") e do
critério da Fase 1. Não é heurística: **caminhar mais é o único ganho de resolução disponível
neste hardware.** Nenhum ajuste de regularização substitui um ponto de coleta.

---

## 14.5 Escala de cidade: 802.11bf e ISAC

A parte do vídeo que mais muda o horizonte do projeto, e a que menos aparece nas manchetes.

| Fato | Estado |
|---|---|
| **IEEE 802.11bf-2025** (WLAN Sensing) | ✅ **ratificado em 26/09/2025**, emenda ao 802.11-2024 |
| Escopo | bandas isentas de licença abaixo de 7,125 GHz **e** 60 GHz direcional |
| O que define | descoberta de capacidade, setup de sessão, troca e reporte de medições — amplitude, fase, atraso, Doppler, ângulo |
| O que **não** define | nenhum modelo de IA nem garantia de resultado (presença, pose) |
| Chegada a roteador doméstico | estimativa de 2027–2028; rótulo "Wi-Fi 6/7" **não** implica suporte |
| Celular | ISAC em 5G/6G; **Reliance Jio** em 26 GHz mmWave; patente da **T-Mobile** para varredura de ambiente pela própria rede |

**Por que isto importa concretamente para o rf-sense:** o muro do projeto
([`01 §3`](01-viabilidade.md)) é que o QCA6174 não expõe fase e o `ath10k` não tem ferramenta de
CSI. O 802.11bf ataca exatamente essa causa: ele **padroniza a interface pela qual um cliente
pede medições de canal ao AP e as recebe**. Se e quando isso chegar ao hardware doméstico, a
informação que hoje exige firmware modificado passa a ter API.

Não é plano — é vigilância tecnológica. O que observar está em
[`15 §6`](15-viabilizar-na-pratica.md).

---

## 14.6 Ghost Murmur: como o vídeo trata uma alegação disputada

O vídeo dedica um capítulo (11:33) ao relato — disputado — de que magnetometria quântica teria
ajudado a localizar um piloto americano abatido no Irã. E separa com cuidado:

- **No registro:** o resgate aconteceu; a CIA referiu-se a "exquisite technologies" (reportagem
  da AP).
- **Contestado:** o método de sensoriamento alegado e o alcance atribuído a ele (análise técnica
  na *Scientific American*).

Vale registrar aqui não pelo conteúdo — magnetometria quântica não tem nenhuma relação com este
projeto — mas pelo **método**: separar explicitamente o que está documentado do que está
atribuído, no mesmo parágrafo, sem resolver a diferença a favor da narrativa mais interessante.

É a mesma disciplina de [`04`](04-analise-das-fontes.md) e de [D12](12-decisoes.md). Quando o
campo inteiro opera com manchetes que prometem raio-X, essa separação é a única defesa.

---

## 14.7 O que importar do método dele, e o que não importar

O autor não é pesquisador de RF; é engenheiro e comunicador (ex-PM de computação espacial e
mapas 3D no Google, curador de tecnologia do TED). O valor dele para este projeto é
**estruturação e legibilidade**, não técnica de RF.

**Vale importar:**

1. **A escada de camadas como linguagem.** Dizer "este projeto para na camada 1 e ataca a
   camada 2 invertida" comunica em uma frase o que [`01`](01-viabilidade.md) leva três páginas
   para estabelecer.
2. **Camadas como forma de entrega.** O projeto paralelo dele, `gods-eye-view` (MIT, dados
   exclusivamente públicos, 13 camadas sobrepostas num globo, "cada linha de código
   inspecionável"), mostra um padrão aplicável: o valor não está numa camada, está em
   **sobrepor camadas com procedência declarada**. O rf-sense hoje entrega um blob ASCII.
   Ver [`15 §7`](15-viabilizar-na-pratica.md).
3. **A exclusão deliberada como escolha de design.** O `gods-eye-view` recusa por decisão de
   projeto busca por pessoa, reconhecimento facial e rastreamento individual — e **diz isso na
   documentação**. É exatamente a postura de [`05`](05-etica-e-privacidade.md), e é um bom
   precedente para tornar explícito: *o rf-sense mapeia o ambiente, não as pessoas nele.*

**Não vale importar:**

- O enquadramento espetacular. "Seu Wi-Fi pode te ver" é bom título e péssima especificação.
- As camadas 3 a 5 em qualquer forma. Não é falta de esforço, é ordem de magnitude (§14.2).
- A suposição de que resultado de laboratório escala para casa. Todos os números de acurácia
  citados no campo vêm de ambiente controlado, sujeito parado, casa vazia.

---

## Em uma frase

O campo todo aponta para **pessoas em movimento**, porque movimento é o insumo mais barato que
existe em RF; o rf-sense aponta para **paredes paradas**, que é o alvo que todos os outros
subtraem — e a lição aproveitável não é mudar de alvo, é usar o movimento como ferramenta e a
banda/abertura como orçamento de resolução declarado.
