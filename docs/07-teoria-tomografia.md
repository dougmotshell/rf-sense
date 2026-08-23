# 07 — Teoria: tomografia RF por atenuação

<sub><b>intelie</b> · Classificação ISO 27001: <b>PÚBLICO</b></sub>

---

O coração matemático do projeto. Explica exatamente o que `src/reconstruct.py` calcula,
por que funciona, e onde erra.

## 1. O modelo direto

Uma onda de rádio que sai de um AP e chega a um receptor perde potência por dois motivos:

**(a) Espalhamento geométrico.** A energia se distribui numa esfera crescente. Em dB:

```
    P(d) = A − 10·n·log₁₀(d)
```

- `P(d)` — potência recebida a distância `d`, em dBm
- `A` — potência de referência a 1 m, em dBm (absorve ganho de antena e potência de TX)
- `n` — expoente de perda de percurso: **2,0** no espaço livre, **3–4** típico em interiores

**(b) Obstáculos no caminho.** Cada parede, laje ou armário atravessado subtrai mais alguns dB.
Modelamos isso como um campo escalar de **densidade de atenuação** `ρ(x,y)`, em **dB/m**,
integrado ao longo do raio:

```
    P_medido = A − 10·n₀·log₁₀(d) − ∫_raio ρ(s) ds
```

Ar tem `ρ ≈ 0`. Drywall tem alguns dB/m. Alvenaria tem bastante. **É por isso que o mapa de
`ρ` é aproximadamente a planta baixa.**

## 2. O problema inverso

Invertemos a equação acima. Para cada medição `i` (um par AP↔ponto), definimos o
**excesso de atenuação**:

```
    bᵢ  =  [ A − 10·n₀·log₁₀(dᵢ) ]  −  P_medidoᵢ   =   ∫_raio_i ρ(s) ds
                    ↑ o que se esperaria           ↑ o que se mediu
```

Discretizamos o espaço numa grade de células quadradas. A integral vira soma:

```
    bᵢ  =  Σⱼ  Mᵢⱼ · xⱼ           ou, em forma matricial:   M·x = b
```

- `x` — vetor de `nx·ny` incógnitas: a densidade de cada célula, em dB/m
- `M` — matriz de projeção: `Mᵢⱼ` é o **comprimento (em metros) do raio i dentro da célula j**
- `b` — vetor de excessos medidos, em dB

Isto é **exatamente a formulação da tomografia computadorizada**. A diferença em relação a um
tomógrafo médico: ele controla a geometria dos raios com precisão milimétrica e dispara
milhares deles; nós usamos os APs que por acaso existem e algumas centenas de medições.

## 3. Por que é preciso andar pela casa

O sistema `M·x = b` só é solucionável se os raios **cruzarem em ângulos variados**. Um receptor
parado gera um raio por AP — e todos partem do mesmo ponto, formando um leque, nunca uma malha.

Um leque não determina o mapa: qualquer densidade colocada em qualquer lugar ao longo de um raio
explica igualmente bem aquela medição. Só quando dois raios de direções diferentes cruzam a
mesma célula é que a ambiguidade se resolve.

**Consequência prática:** a qualidade do mapa depende muito mais de **quantos pontos de coleta**
você visita do que de qualquer parâmetro do algoritmo.

## 4. Regularização — e por que ela é obrigatória

Com ~400 raios e ~200 células, o sistema parece sobredeterminado. Não é: os raios se concentram
em corredores geométricos, muitas células recebem pouquíssima cobertura, e o RSSI é ruidoso.
O problema é **mal-posto** — pequenas variações em `b` produzem grandes variações em `x`.

A solução é não pedir apenas o `x` que melhor explica os dados, mas o `x` que explica os dados
*e* é plausível como planta baixa:

```
    minimizar   ‖M·x − b‖²  +  λ·‖x‖²  +  μ·‖D·x‖²     sujeito a   x ≥ 0
                ─────┬─────    ───┬───     ────┬────                 ──┬──
                  fidelidade   Tikhonov   suavidade            não-negatividade
```

| Termo | Papel | Flag |
|---|---|---|
| `‖M·x − b‖²` | Explicar as medições | — |
| `λ·‖x‖²` | Preferir a solução de menor energia; suprime densidade onde não há evidência | `--lam` |
| `μ·‖D·x‖²` | `D` é o laplaciano discreto. Penaliza mapas granulados e favorece estruturas contínuas — que é o que paredes são | `--mu` |
| `x ≥ 0` | Restrição física: **não existe parede que amplifique sinal** | fixo |

**Como ajustar:** `λ` e `μ` altos → mapa liso, borrado, conservador. Baixos → mapa granulado que
"explica" o ruído. Comece com os padrões (`λ=0.05`, `μ=0.5`) e mexa em um de cada vez.

O **resíduo relativo** impresso ao final é `‖M·x − b‖ / ‖b‖`. Resíduo muito baixo com dados reais
é motivo de suspeita, não de comemoração: significa que você está ajustando ruído.

## 5. O solver

Gradiente projetado, em numpy puro (sem scipy). O gradiente do objetivo é:

```
    ∇ = 2·(MᵀM·x − Mᵀb) + 2λ·x + 2μ·Dᵀ D·x
```

e a cada passo projetamos de volta no ortante positivo:

```
    x ← max(x − lr·∇, 0)
```

Essa projeção é o que impõe `x ≥ 0`. O passo `lr` é estimado como `1/‖MᵀM‖₂`, o que garante
estabilidade. São 400 iterações por padrão — o problema é pequeno e converge rápido.

*Alternativas consideradas e recusadas:* equações normais diretas (`np.linalg.solve`) não impõem
não-negatividade; ART/SART clássico convergem bem mas são mais difíceis de regularizar; NNLS
exigiria scipy. Ver `docs/12`.

## 6. Localizar os APs

As posições dos APs são **desconhecidas** — os seus, você até sabe, mas os dos vizinhos não.
E são justamente os dos vizinhos que dão os melhores raios, porque atravessam a casa inteira.

`localizar_ap()` estima `(x_ap, y_ap, A)` minimizando o erro do modelo log-distance sobre todas
as medições daquele AP. Duas escolhas de implementação:

- **`A` em forma fechada.** Para uma posição candidata, o `A` ótimo é a média dos resíduos —
  não precisa ser buscado. Isso reduz a busca de 3 para 2 dimensões.
- **Busca em grade grosseiro-para-fino**, com margem generosa além da área medida (APs de
  vizinhos ficam fora). Mais lenta que um otimizador, mas não cai em mínimo local — e a
  superfície de erro do log-distance tem vários.

O `rmse` impresso por AP é o diagnóstico: **acima de ~6 dB, desconfie da posição estimada**.
Se você conhece a posição real de um AP seu, fixá-la manualmente melhora o mapa inteiro.

## 7. O viés do expoente ⚠️

**Esta é a sutileza mais importante do pipeline, e a mais fácil de errar.**

Dois expoentes distintos entram na conta:

- `--n-percurso` (padrão **2,6**) — usado para **localizar** os APs. Um valor tipicamente indoor
  ajusta melhor a posição, porque o decaimento real do sinal dentro de uma casa é mais rápido
  que no espaço livre.
- `--n-referencia` (padrão **2,0**) — usado para calcular o **excesso** `b`.

Quando os dois diferem, aparece um termo espúrio. Se o AP foi ajustado com `n₁` e o excesso é
medido contra `n₀`:

```
    b  =  [A − 10·n₀·log₁₀ d] − [A − 10·n₁·log₁₀ d − atenuação_real]
       =  10·(n₁ − n₀)·log₁₀(d)  +  atenuação_real
          ─────────┬──────────
              viés que CRESCE com a distância
```

Com os padrões, isso são `6·log₁₀(d)` dB de atenuação fantasma. A tomografia não tem como saber
que é fantasma, então **espalha esse excesso pelo mapa como um fundo difuso** — visível como
manchas espúrias em regiões distantes dos APs.

**As duas configurações válidas:**

| Configuração | O que `x` significa | Quando usar |
|---|---|---|
| `n_ref = 2.0` (padrão) | Atenuação **absoluta** em dB/m acima do espaço livre | Quer o valor físico; aceita fundo difuso |
| `n_ref = n_percurso` | **Desvio** em relação à atenuação média da casa | Quer contraste e paredes nítidas |

Na segunda, o modelo log-distance já absorveu a parede "média", e o mapa mostra apenas onde há
*mais* obstáculo que a média. Perde-se o offset absoluto; ganha-se muito em nitidez.

Na validação sintética, igualar os dois **eliminou o fundo e tornou as paredes nítidas** —
ver `docs/10`. **Rode as duas e compare**; são interpretações diferentes do mesmo dado, não
uma certa e uma errada.

## 8. Traçado de raio

`traçar_raio()` amostra o segmento AP→ponto uniformemente (8 amostras por metro, por padrão) e
acumula `ds` na célula que contém cada amostra.

Isto é uma aproximação do algoritmo de Siddon, que calcula os comprimentos exatos de interseção.
A aproximação é adequada porque a amostragem (12,5 cm) é bem mais fina que a célula (50 cm), e
porque o erro de discretização é pequeno perto do ruído de 2–6 dB do próprio RSSI. Refinar o
traçado antes de reduzir o ruído de medição seria otimizar a parte errada.

## 9. Premissas — e onde elas quebram

Toda a formulação assume que o sinal viaja em **linha reta** do AP ao receptor e que a perda é
**aditiva ao longo dessa reta**. Na vida real, o rádio faz outras coisas:

| Fenômeno | Efeito no mapa | Mitigação |
|---|---|---|
| **Multipercurso** — o sinal chega por reflexões, não só direto | Excesso subestimado (a reflexão "contorna" a parede) | Mediana de muitas amostras; APs distantes |
| **Desvanecimento de pequena escala** — mover 10 cm muda o RSSI em vários dB | Ruído grande | ≥15 amostras por ponto |
| **Corpo do operador** — você atenua 3–6 dB | Viés **sistemático**, o pior tipo | **Mesma orientação sempre** |
| **Anisotropia da antena** | Ganho varia com a direção | Mesma orientação; APs distribuídos |
| **APs multibanda** | Mesmo AP em 2,4 e 5 GHz tem BSSIDs distintos | Tratados como APs independentes — o que está correto |
| **Pessoas se movendo** | Ruído não-estacionário | Colete com a casa vazia |

A premissa que mais quebra é a de linha reta. É por isso que o resultado é uma **mancha na
posição da parede** e não uma linha — e é por isso que resolução melhor que ~0,5 m não é
alcançável por este caminho, independentemente de quanto você refine o código.

## 10. Por que não dá para fazer melhor sem fase

Um radar mede **tempo de voo** e obtém a distância de cada eco. Nós medimos apenas **potência
total**, que é uma integral ao longo do caminho — perdemos toda a informação de *onde*, no
caminho, a atenuação aconteceu. Só recuperamos essa informação estatisticamente, cruzando muitos
raios.

Com acesso à **fase** (CSI ou SDR), seria possível separar os componentes de multipercurso por
tempo de chegada e localizar refletores diretamente — que é o que holografia e SAR fazem. Essa
porta está fechada neste hardware (ver `docs/02`).

**A tomografia por atenuação é o melhor que a física permite com potência apenas.** Não é uma
implementação preguiçosa de algo melhor — é o limite teórico da informação disponível.
