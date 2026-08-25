# 17 — Comece aqui: o manual em linguagem simples

---

Este documento não pressupõe nada. Se você nunca ouviu falar de RSSI, tomografia ou
Wi-Fi sensing, comece por aqui e leia na ordem. O manual de referência com todas as
flags é o [`08`](08-manual-de-uso.md); este aqui explica **o que está acontecendo e
por quê**.

---

## 1. O que este projeto faz, sem jargão

Imagine um quarto escuro com várias lâmpadas espalhadas pela casa e pelos vizinhos.
Você não pode ver as lâmpadas nem as paredes. Mas pode andar pelo quarto com um
medidor de luz na mão e anotar, em cada lugar onde para, **quanta luz de cada lâmpada
chega até ali**.

Onde há parede entre você e uma lâmpada, chega menos luz. A parede faz **sombra**.

Se você fizer isso em muitos lugares diferentes, vai ter centenas de medições, e cada
uma diz "entre este ponto e aquela lâmpada, alguma coisa comeu X% da luz". Cruzando
todas essas sombras, dá para descobrir **onde estão as paredes** — porque uma parede é
justamente o lugar onde muitas sombras diferentes se cruzam.

É exatamente isso que o projeto faz, com uma troca: as lâmpadas são os **roteadores
Wi-Fi** (o seu e os dos vizinhos), e o medidor de luz é o **seu laptop ou celular**.
Ondas de rádio atravessam parede, mas perdem energia ao atravessar. Essa perda é a
sombra.

O resultado é um **mapa 2D da sua casa**: manchas escuras onde há parede, claro onde é
espaço livre. Custo: zero. Você já tem tudo.

## 2. O que ele NÃO faz — leia antes de se animar

Isto é importante e é melhor saber agora:

| Você pode ter imaginado | Realidade |
|---|---|
| Uma imagem 3D da casa, tipo scanner | ❌ Não. Precisaria de informação que placa Wi-Fi comum não entrega |
| Ver os móveis, o que está na mesa | ❌ Não. A resolução é de metros, não de centímetros |
| Ver pessoas, esqueleto, pose | ❌ Não com este hardware |
| Ver respiração ou batimento cardíaco | ❌ Não com este hardware |
| **Descobrir onde estão as paredes** | ✅ **Sim, e é isto o projeto** |

O mapa sai **borrado**, e isso é o resultado correto, não um defeito. Rádio Wi-Fi tem
onda de 5 a 12 cm e o problema matemático é difícil de resolver: manchas na posição
certa é o esperado. Se as bordas saírem nítidas, alguma coisa está errada.

O porquê disso tudo está em [`01`](01-viabilidade.md). Se as manchetes do tipo "Wi-Fi
vê através de paredes" te trouxeram aqui, leia [`04`](04-analise-das-fontes.md) e
[`14`](14-as-cinco-camadas.md).

## 3. O que você precisa

- Um **laptop com Linux** e Wi-Fi. Nada especial.
- **Python 3** e **numpy** (`pip install numpy` se faltar).
- Uma **trena** ou fita métrica. Ou passos calibrados, na pior das hipóteses.
- **Fita crepe** para marcar o chão.
- Uma tarde livre e paciência.

Não precisa: comprar nada, instalar driver, mexer no kernel, ser root.

## 4. O roteiro, em seis passos

Cada passo abaixo diz **o que rodar**, **o que vai aparecer** e **como saber se deu
certo**. Não pule passos: o erro de um passo aparece disfarçado como erro do seguinte.

---

### Passo 1 — Perguntar ao projeto se dá para começar

```bash
python3 src/poc.py --modo free
```

Isto não mede nada da sua casa ainda. Ele testa o **seu equipamento**, em cinco
checagens que ele chama de portões, e diz onde você está travado.

**O que vai aparecer:** cinco blocos, cada um com `PASSOU`, `ALERTA` ou `REPROVOU`, e
no fim um veredito. Provavelmente vai dizer `BLOQUEADO em P4` — e está certo, porque
você ainda não desenhou a planta da sua casa. É o passo 2.

**Se aparecer `REPROVOU` em P0, P1 ou P2:** aí o problema é o rádio, e o texto do
portão diz o quê. Vale ler antes de continuar.

---

### Passo 2 — Desenhar a planta da sua casa (a parte chata e mais importante)

Parece estranho começar desenhando a resposta. Mas pense: se você reconstruir um mapa
e ele parecer plausível, **como você vai saber se ele está certo?** Sem uma referência
medida, "ficou bom" é opinião. E um mapa errado que parece convincente é o pior
resultado possível, porque você acredita nele.

Então: meça a casa e digite as medidas.

```bash
cp data/ground_truth.example.json data/ground_truth.json
```

Abra `data/ground_truth.json` num editor. Cada parede é uma linha assim:

```json
{"x0": 3.5, "y0": 0.0, "x1": 3.5, "y1": 4.2, "atenuacao_db": 6.0, "tipo": "divisoria"}
```

Que se lê: *uma parede que começa no ponto (3,5 m · 0 m) e termina em (3,5 m · 4,2 m)*.

Três coisas a entender:

- **Escolha um canto da casa para ser o ponto (0,0)** e marque no chão com fita crepe.
  Todas as medidas saem dele. `x` cresce para um lado, `y` para o outro — você decide,
  só não mude depois.
- **`tipo`** é `"externa"` para as paredes de fora e `"divisoria"` para as de dentro.
  A diferença importa: paredes externas são impossíveis de detectar por este método
  (todos os seus pontos de medição estão do lado de dentro), então o projeto as ignora
  na hora de avaliar. Não é trapaça, é usar a régua certa — ver [`13`](13-avaliacao.md).
- **`atenuacao_db`** é um chute de quanto aquela parede engole de sinal. 6 para
  divisória de tijolo, 12 para parede externa grossa, 3 para drywall. Não precisa ser
  exato.

Depois de digitar, confira e peça o plano de coleta:

```bash
python3 src/groundtruth.py data/ground_truth.json --render
python3 src/groundtruth.py data/ground_truth.json --plan --step 1.0
```

**O que vai aparecer:** um desenho em texto da sua casa, e depois uma lista de pontos
para visitar com o comando pronto de cada um.

**Deu certo se:** o desenho parece a sua casa, não aparece nenhum aviso, e o plano
gera 20 pontos ou mais.

**Atalho, se você tem celular:** apps gratuitos de medição (ARCore, ou LiDAR se o
aparelho tiver) desenham planta em minutos e com mais precisão que trena. Vale usar.

---

### Passo 3 — Descobrir quantas medições valem a pena

```bash
python3 src/probe.py cadencia --modo free
python3 src/orcamento.py
```

O primeiro comando mede uma coisa que ninguém pensa em medir: **de quanto em quanto
tempo o número que você lê muda de verdade**. Não é a mesma coisa que a velocidade com
que você pergunta. Neste laptop, perguntando 13 vezes por segundo, o valor muda uma vez
a cada 9 segundos — o resto é o mesmo número repetido. Saber disso muda o que você
pode medir.

O segundo simula a coleta inteira, várias vezes, com espaçamentos diferentes, e diz
**qual é o menor esforço que ainda dá um mapa bom**.

**O que vai aparecer:** uma tabela com uma linha por espaçamento testado, e no fim uma
recomendação tipo "step 1.00 m → 48 pontos, ~72 min de campo".

**Como ler:** olhe a coluna `F1@comum`, não a `F1@prop`. Parece detalhe e não é: sob a
própria régua, medir menos *parece* melhor, porque a área difícil sai da conta. A
coluna `F1@comum` usa a mesma régua para todas as configurações e é a única que
compara de verdade.

---

### Passo 4 — Medir a casa

Este é o trabalho de campo. Marque a grade no chão com fita crepe e, em cada ponto,
rode um comando (o `--plan` do passo 2 já imprimiu todos, prontos):

```bash
python3 src/survey.py --x 1 --y 1 --samples 15 --out data/raw/survey.jsonl
python3 src/survey.py --x 2 --y 1 --samples 15 --out data/raw/survey.jsonl
# ... e assim por diante
```

**Quatro regras que decidem se vai funcionar.** Elas parecem exageradas e não são:

1. **Sempre a mesma orientação do aparelho.** Escolha uma direção — a janela, a porta,
   tanto faz — e aponte o laptop para lá em *todos* os pontos. Seu corpo engole 3 a
   6 dB de sinal, e o sinal que você persegue tem essa mesma ordem de grandeza. Se você
   girar, injeta erro do tamanho do que quer medir.
2. **Fique parado durante a coleta.** Cada ponto leva uns 2 minutos.
3. **Casa vazia.** Ninguém circulando.
4. **Cubra tudo**, inclusive corredores e vãos de porta. Os vãos são o que mais prova
   que o método funciona: a parede "desaparece" ali, e o mapa deve mostrar isso.

Ao terminar:

```bash
python3 src/survey.py --summary data/raw/survey.jsonl
```

**Deu certo se:** pelo menos 8 roteadores aparecem em 80% ou mais dos pontos, e você
tem 20 pontos ou mais. O próprio comando imprime esse veredito.

---

### Passo 5 — Fazer o mapa

```bash
python3 src/reconstruct.py data/raw/survey.jsonl --grid 0.5 --n-referencia 2.6 --modo free
```

**O que ele faz, em duas etapas.** Primeiro ele descobre onde estão os roteadores —
você não informou, e ele deduz a partir de como o sinal decai. Roteadores de vizinhos
vão cair fora da sua casa, e isso é bom: os raios deles atravessam tudo. Depois ele
resolve o problema das sombras cruzadas e monta o mapa.

**O que vai aparecer:** um desenho em texto onde caracteres densos (`@`, `#`, `%`) são
regiões de muita atenuação — as paredes — e espaços são área livre. Mais dois mapas
extras: quantos raios passaram por cada pedacinho, e se esses raios vinham de direções
variadas ou todos da mesma.

**Esses dois mapas extras são importantes** e a razão é simples: um pedaço do mapa
atravessado por 40 raios de direções diferentes é um resultado; um pedaço atravessado
por 2 raios quase paralelos é um chute com cara de resultado. Sem esses mapas, os dois
saem pintados igual e você não tem como distinguir.

---

### Passo 6 — Descobrir se o mapa está certo

```bash
python3 src/compare.py data/processed data/ground_truth.json --tipos divisoria --cobertura
python3 src/camadas.py --survey data/raw/survey.jsonl --tipos divisoria
```

O primeiro compara o seu mapa com a planta que você mediu no passo 2, e dá notas. O
segundo gera sete imagens sobrepostas, para você **ver** a comparação.

**Como ler as notas.** Nunca olhe um número sozinho — olhe sempre a comparação com o
acaso, que o comando imprime ao lado. "F1 de 0,62" não diz nada; "F1 de 0,62, que é
3,5 vezes melhor que chutar" diz tudo.

Duas famílias de nota, e as duas são necessárias:

- **Sobreposição** (`F1`, `IoU`): quantas células você acertou na mosca. É uma régua
  dura demais para um mapa borrado — meio metro de desvio já zera o acerto, mesmo com
  a mancha centrada no lugar certo.
- **Proximidade** (distância às paredes): a quantos metros, em média, o mapa colocou
  massa da parede real. **É a régua honesta para este projeto.** Um mapa de manchas
  acerta a posição sem acertar a célula.

**Deu certo se:** a distância ponderada ficar abaixo de 0,6× o acaso e o F1 acima de
2× o acaso. O comando imprime essa leitura por você, em português.

**O que fazer se não deu**, nesta ordem — e note que ajustar parâmetro é o **último**
item, não o primeiro:

| Sintoma | Causa mais provável |
|---|---|
| Mapa não melhor que o acaso | Referencial (0,0) diferente entre os dois arquivos |
| Manchas deslocadas todas para um lado | Um roteador mal localizado, arrastando os raios dele |
| Mapa muito uniforme, sem estrutura | Poucos pontos de coleta, ou todos na mesma região |
| Ruído demais | Orientação do aparelho mudou durante a coleta |
| Só depois de checar tudo acima | Regularização (`--lam`, `--mu`) forte demais |

---

## 5. Os modos, explicados sem jargão

O projeto chama de **modo** a resposta para "de onde vem o número que estou medindo".
Existem nove, e a diferença entre eles não é preferência: é o que a física de cada um
permite.

```bash
python3 src/modos.py --listar      # todos
python3 src/modos.py --detectar    # o que roda na sua máquina agora
```

Os que interessam no começo:

| modo | em palavras |
|---|---|
| **`sim`** | Inventa os dados a partir de uma planta que ele conhece. Serve para testar se o programa funciona, porque aqui você sabe a resposta certa. Use sempre que algo estranho acontecer. |
| **`free`** | O modo normal: lê a força do sinal Wi-Fi com uma ferramenta que já vem no Linux. Zero custo, zero configuração. |
| **`replay`** | Reprocessa uma coleta antiga do arquivo. Útil para testar mudanças sem sair da cadeira. |

Os pagos existem no registro para você saber **o que valeria comprar e o que não
valeria** — e a resposta é contraintuitiva:

- Um **módulo de radar de US$ 22** tem resolução muito melhor que o Wi-Fi e **não serve
  para este projeto**, porque ele entrega uma decisão pronta ("tem alguém a 2,3 m") em
  vez do dado bruto de onde essa resolução vive.
- Um **ESP32-S3 de US$ 8** tem resolução pior e é **a melhor compra que existe**, porque
  é o único barato que entrega uma informação chamada *fase* — a que abre a porta para
  tudo o que o projeto hoje não pode fazer.

Detalhe em [`16`](16-modos-e-poc.md).

## 6. Como ler o mapa que sai

Exemplo de saída real, do simulador:

```
  4.8 |. :      ...:.::|   <- aqui a parede desaparece: é o vão da porta
  3.2 |.     ##@*#=*#=:|   <- parede horizontal, só na metade direita
      +----------------+
      x de 0.0 a 8.0 m   (célula 0.50 m)
```

- Cada caractere é um quadrado de 50 cm da sua casa.
- A escala vai de espaço (nada) a `@` (muita atenuação): ` .:-=+*#%@`
- O número da esquerda é a coordenada `y`, em metros.
- `y` cresce **para cima**, como num gráfico — não como numa tabela.

**O que celebrar:** manchas onde há parede, buraco onde há porta, e ausência de manchas
no meio dos cômodos. **O que não esperar:** linhas retas e finas.

## 7. Quando algo quebrar

| O que aconteceu | O que fazer |
|---|---|
| `modo 'X' não pode rodar aqui` | `python3 src/modos.py --explicar X` — ele lista requisito por requisito |
| `numpy` não encontrado | `pip install numpy` |
| `Só N APs utilizáveis` | Baixe `--min-cobertura` para 0.4, ou colete mais pontos |
| `o ground truth não intersecta a área do mapa` | O (0,0) da planta e o da coleta são diferentes |
| Coleta lentíssima (8 s por amostra) | É normal e esperado: o rádio precisa varrer. Ver [`16 §16.3`](16-modos-e-poc.md) |
| Alguma coisa muito estranha | Rode tudo em `--modo sim` primeiro. Se quebrar lá, é o programa; se funcionar lá, é a coleta |
| Quero saber se eu quebrei algo no código | `make test` — roda o pipeline inteiro contra uma planta conhecida, ~1 min |

## 8. Palavras que vão aparecer

Aqui em uma frase cada; o glossário completo é o [`11`](11-glossario.md).

- **RSSI** — a força do sinal que chega. É o "medidor de luz" da analogia.
- **dB** — a unidade de "quanto engoliu". Uma parede comum engole ~6 dB.
- **AP** *(access point)* — roteador. Uma das "lâmpadas".
- **Raio** — a linha imaginária entre um roteador e um ponto onde você mediu.
- **Tomografia** — o método de cruzar muitas sombras para descobrir o que as causou.
  É a mesma ideia de uma tomografia médica, com resolução muito pior.
- **Ground truth** — a planta que você mediu com trena. A resposta certa, para comparar.
- **Fase** — a informação sobre *quando* a onda chegou, não só quanta energia. É o que
  falta neste hardware, e é por isso que não existe imagem 3D aqui.
- **Camada** — quão ambicioso é o que você quer medir: presença de alguém, localização,
  respiração, pose, identidade. Este projeto opera nas duas primeiras
  ([`14`](14-as-cinco-camadas.md)).
- **Portão** — uma checagem do `poc.py` que precisa passar antes de seguir.
- **Cadência** — de quanto em quanto tempo o número realmente muda.
- **Máscara de cobertura** — o recorte do mapa que tem dado suficiente para ser levado
  a sério.

## 9. Atalhos

```bash
make poc         # dá para seguir hoje?
make modos       # que modos existem e o que roda aqui
make cadencia    # a cadeia de medição é rápida o bastante para o quê?
make orcamento   # quantos pontos valem a pena
make sim         # o pipeline inteiro no simulador, resposta conhecida
make camadas     # as sete camadas sobrepostas
make test        # autoteste, ~1 min
```

## Em uma frase

Meça a casa com trena, ande por ela anotando a força do Wi-Fi, deixe o programa cruzar
as sombras, e depois **compare com a trena** — porque a única parte difícil deste
projeto não é a matemática, é a disciplina de medição.
