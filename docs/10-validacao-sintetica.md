# 10 — Validação sintética

<sub>Executado em 2026-08-23</sub>

---

Antes de medir a casa de verdade, é preciso saber se o reconstrutor funciona. Este documento
registra o experimento que responde a isso — e o que ele revelou sobre o pipeline.

## Método

`simulate.py` gera medições a partir de uma planta **conhecida**, aplicando perda de espaço
livre + atenuação por parede atravessada + ruído gaussiano. `reconstruct.py` recebe **apenas
RSSI e posições** — não sabe nada sobre a planta, sobre onde estão os APs, nem quantas paredes
existem.

**Cenário:** apartamento de 8 × 6 m.

| Elemento | Geometria | Atenuação |
|---|---|---|
| Contorno externo | retângulo 8 × 6 m | 12 dB |
| Parede vertical | `x = 3.5`, de `y=0` a `y=4.2` e de `y=5.2` a `y=6` | 6 dB |
| **Vão de porta** | `x = 3.5`, entre `y=4.2` e `y=5.2` | — (aberto) |
| Parede horizontal | `y = 3.0`, de `x=3.5` a `x=8.0` | 6 dB |

**Coleta:** 48 pontos em grade de 1 m · 12 amostras por ponto · 8 APs (1 interno, 7 "vizinhos"
fora do apartamento) · ruído σ = 2 dB · seed 42.

**Reconstrução:** grade de 0,5 m → 16 × 12 = 192 células · 383 raios válidos.

```bash
python3 src/simulate.py --out data/raw/sim.jsonl
python3 src/reconstruct.py data/raw/sim.jsonl --grid 0.5
```

## Resultado A — padrão (`--n-referencia 2.0`)

```
Excesso de atenuação: mediana 3.4 dB, máx 14.4 dB
Resíduo relativo: 31.0%

  5.8 |.--=++@+##*:..:.|
  5.2 |- ... #-=..    :|
  4.8 |. :      ...:.::|
  4.2 |+.  : -  ::-=-:=|
  3.8 |...=.-@+=::    .|
  3.2 |.     ##@*#=*#=:|
  2.8 |*     %@#+-.:.: |
  2.2 |:    =+=--.:-=..|
  1.8 |.    -*+- -=--::|
  1.2 | .  ..=+:  .: ..|
  0.8 |      **-:.  :::|
  0.2 | ...:-:*+==: ...|
      +----------------+
      x de 0.0 a 8.0 m   (célula 0.50 m, máx 4.0 dB/m)
```

As estruturas estão lá, mas sobre um **fundo difuso** que polui o mapa inteiro.

## Resultado B — sem viés de expoente (`--n-referencia 2.6`)

```
Excesso de atenuação: mediana 0.0 dB, máx 9.6 dB
Resíduo relativo: 49.3%

  5.8 |      %:-::.    |
  5.2 |:     =.        |
  4.8 |  :      .      |     <- vão de porta: parede ausente, corretamente
  4.2 |::  : :    -.. .|
  3.8 |   : .@-.:-     |
  3.2 |      +%@+*:=+::|     <- parede horizontal, só da metade para a direita
  2.8 |:     =%#=.     |
  2.2 |.    .=:.: ..   |
  1.8 |     .+-  .: .  |
  1.2 |    . ..    :   |
  0.8 |      :=     :. |
  0.2 |       ++...    |
      +----------------+
      x de 0.0 a 8.0 m   (célula 0.50 m, máx 2.6 dB/m)
```

**Muito mais limpo.** O fundo praticamente desaparece e as três estruturas ficam evidentes.

## Análise

### O que foi recuperado corretamente

| Estrutura real | Onde aparece no mapa | ✓ |
|---|---|---|
| Parede vertical em `x=3.5` | coluna densa em `x ≈ 3.0–4.0` | ✅ |
| Vão de porta, `y` entre 4.2 e 5.2 | a coluna **some** nessas linhas | ✅ |
| Parede horizontal em `y=3.0`, apenas `x>3.5` | linha densa em `y≈3.2`, **só na metade direita** | ✅ |
| Assimetria da parede horizontal | metade esquerda permanece livre | ✅ |

O vão de porta é o resultado mais significativo. Ele não é uma estrutura *presente* — é uma
**ausência**, dentro de uma parede que existe acima e abaixo. Recuperá-lo prova que o
reconstrutor está resolvendo o problema inverso de verdade, e não apenas borrando a região
onde há mais raios.

### O que não foi recuperado

**O contorno externo do apartamento não aparece** — e está correto que não apareça. Todos os
pontos de medição estão *dentro* do apartamento, e não há raio algum que percorra o contorno
tangencialmente. A parede externa é atravessada por quase todos os raios de forma quase
idêntica, então sua contribuição vira uma **constante** absorvida pelo `a_ref` de cada AP.

Lição transferível: **a tomografia só enxerga o que os raios discriminam.** Estrutura que afeta
todos os raios igualmente é indistinguível de uma mudança na potência de transmissão.

### A descoberta: o viés do expoente

O contraste entre A e B expôs um viés sistemático descrito em `docs/07 §7`. Quando
`--n-referencia` (2.0) é menor que `--n-percurso` (2.6), o excesso de atenuação carrega um termo
espúrio `10·(2.6−2.0)·log₁₀(d) = 6·log₁₀(d)` dB, que cresce com a distância. A tomografia não
tem como saber que é fantasma e o distribui como fundo difuso.

Igualar os dois expoentes elimina o termo. O preço: `x` deixa de ser atenuação absoluta e passa
a ser **desvio em relação à parede média** da casa. Para *ver a planta*, isso é preferível.

Note que o **resíduo relativo subiu** de 31% para 49,3% no mapa visualmente melhor. Isso não é
contradição — é a evidência mais clara de que **resíduo baixo não significa mapa bom**. No caso
A, boa parte do resíduo era "explicada" ao acomodar o viés como densidade espúria. Ajustar bem
uma quantidade fantasma é ajustar ruído.

Essa descoberta gerou a flag `--n-referencia`, que não existia na primeira versão.

## Conclusões

1. **O pipeline funciona.** Recupera paredes, assimetrias e aberturas a partir apenas de RSSI e
   posições.
2. **Rode sempre as duas configurações** de `--n-referencia` e compare. São interpretações
   diferentes do mesmo dado.
3. **Não use resíduo relativo como métrica de qualidade** do mapa. Use inspeção visual contra o
   ground truth.
4. **O resultado é borrado, e vai continuar sendo.** Wi-Fi tem comprimento de onda de 5–12 cm e
   estamos resolvendo um problema inverso mal-posto com centenas de raios. Manchas na posição
   certa é o resultado esperado; bordas nítidas indicariam erro.

## Limites desta validação

O simulador usa **exatamente o mesmo modelo direto** que o reconstrutor inverte: propagação em
linha reta, atenuação aditiva, ruído gaussiano branco. Isso valida a **matemática**, não a
**física**.

A realidade tem multipercurso, desvanecimento de pequena escala, anisotropia de antena e o corpo
do operador (`docs/07 §9`) — nada disso está simulado. **Espere resultado pior na casa de
verdade**, e trate estes mapas como o teto de qualidade, não como previsão.

## Avaliação quantitativa

A inspeção visual acima virou número em [`docs/13`](13-avaliacao.md): restrito às divisórias
internas — as únicas fisicamente recuperáveis — o resultado B dá **F1 = 0,684, 3,5× o acaso**,
com a massa do mapa a **0,68 m** das paredes reais contra **1,43 m** de uma célula ao acaso.

## Reproduzir

```bash
python3 src/simulate.py --out data/raw/sim.jsonl --seed 42
python3 src/reconstruct.py data/raw/sim.jsonl --grid 0.5                      # resultado A
python3 src/reconstruct.py data/raw/sim.jsonl --grid 0.5 --n-referencia 2.6   # resultado B
```

**Experimentos que valem a pena** antes de medir a casa:

- `--noise 6` — o ruído realista. Veja quanto degrada.
- `--step 2.0` — metade dos pontos de coleta. Descubra quanto trabalho de campo é mesmo necessário.
- Editar `PLANTA_EXEMPLO` para a sua casa — assim você sabe o que esperar antes de sair medindo.

E para medir o efeito de cada experimento em vez de julgar no olho:

```bash
python3 src/compare.py data/processed data/ground_truth.example.json --tipos divisoria
```
