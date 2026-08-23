# 13 — Avaliação: como saber se o mapa está certo

<sub>Baseline medido em 2026-08-23</sub>

---

Um mapa reconstruído errado que parece plausível é o pior resultado possível deste projeto —
pior que nenhum mapa, porque você acredita nele. Este documento define como transformar
"ficou bom" em número.

Ferramenta: `src/compare.py`. Insumos: o mapa (`data/processed/`) e o ground truth da fase 0.

## Por que duas famílias de métrica

Uma métrica sozinha engana, em direções opostas.

### Sobreposição — IoU, precisão, recall, F1

Conta quantas células previstas como parede realmente são parede.

**É dura demais com este projeto.** A tomografia RF produz manchas de meio metro; um
deslocamento de uma célula já zera a interseção mesmo com a mancha centrada no lugar certo.
IoU baixo aqui não significa necessariamente mapa ruim.

### Proximidade — distância às paredes

Quão longe, em metros, a massa do mapa está da parede real mais próxima. Três números:

| Métrica | O que mede |
|---|---|
| Distância **mediana** das células previstas | quão certeiras são as previsões binarizadas |
| Distância **ponderada pela densidade** | onde o mapa concentra energia, sem depender de limiar |
| Mesma medida **para uma célula ao acaso** | o denominador que dá sentido às duas acima |

**Esta é a família honesta para este projeto.** O que importa não é acertar a célula exata —
é a mancha estar no lugar certo.

## As três decisões metodológicas

### 1. Binarização por percentil casado

Comparar um mapa contínuo (dB/m) com uma máscara binária exige escolher um limiar — e o limiar
é um grau de liberdade que permite fabricar o resultado desejado.

`compare.py` remove esse grau de liberdade: por padrão prevê **exatamente tantas células
quantas o ground truth tem**. Assim precisão e recall são estruturalmente iguais e não há como
inflar uma às custas da outra. Use `--limiar` para fixar um valor físico, quando quiser.

### 2. Baseline aleatório, sempre impresso

Um F1 de 0,62 não diz nada isolado. Se 44% das células são parede, prever ao acaso já dá 0,438 —
e 0,62 vira um ganho modesto de 1,4×. O baseline é impresso junto de cada métrica, sempre.

### 3. Filtro por tipo de parede — `--tipos divisoria`

Paredes **externas são indetectáveis por construção** neste setup: todos os pontos de coleta
ficam do lado de dentro, nenhum raio as percorre tangencialmente, e a atenuação que elas
impõem é praticamente idêntica para todos os raios — logo vira constante absorvida pelo `a_ref`
de cada AP (`docs/10`).

Avaliar contra elas não mede o sistema; mede uma impossibilidade física. `--tipos divisoria`
restringe a avaliação ao que é **de fato recuperável**.

Isto não é aliviar a régua — é aplicar a régua correta. A limitação continua documentada; o que
muda é não deixá-la mascarar o sinal real.

## Baseline atual — dados sintéticos

Reconstrução de `data/raw/sim.jsonl` com `--grid 0.5 --n-referencia 2.6`, 383 raios, 8 APs,
avaliada contra `data/ground_truth.example.json`.

| Métrica | Todas as paredes | **Só divisórias** |
|---|---|---|
| Células parede | 84 (44% da grade) | 38 (20% da grade) |
| Precisão / Recall | 61,9% | **68,4%** |
| F1 | 0,619 (acaso 0,438 → **1,4×**) | **0,684** (acaso 0,198 → **3,5×**) |
| IoU | 0,448 | **0,520** |
| Distância mediana das previsões | 0,25 m | **0,25 m** |
| Distância ponderada pela densidade | 0,41 m | 0,68 m |
| ↳ mesma medida ao acaso | 0,66 m (1,6×) | 1,43 m (**2,1×**) |
| Previsões a < 0,5 m de parede real | 62% | **68%** |

```
  5.8 |      ##oo      |
  5.2 |      #.        |
  4.8 |  o             |    <- vão de porta: corretamente vazio
  4.2 |o   o #.   o    |
  3.8 |   o  ##  o     |
  3.2 |      #########.|    <- parede horizontal, só da metade para a direita
  2.8 |o     ####......|
  2.2 |      ## o      |
  1.8 |      ##   o    |
  1.2 |      ..        |
  0.8 |      ##        |
  0.2 |      .#o       |
      +----------------+
      '#' parede detectada   'o' falso positivo   '.' parede perdida
```

**Leitura:** a parede vertical em `x=3.5` é recuperada em quase toda a sua extensão; a
horizontal em `y=3.0` aparece corretamente restrita à metade direita; o vão de porta entre
`y=4.2` e `5.2` fica vazio. Os falsos positivos são esparsos e não formam estrutura falsa.

**Este é o teto**, não a previsão. O simulador usa o mesmo modelo direto que o reconstrutor
inverte — valida a matemática, não a física (`docs/10`). Na casa real há multipercurso,
desvanecimento e o corpo do operador. **Espere números piores.**

## Metas para os dados reais

| Nível | Distância ponderada vs. acaso | F1 vs. acaso | Leitura |
|---|---|---|---|
| Falhou | ≥ 0,85× | ~1× | Não está melhor que o acaso |
| Sinal fraco | 0,6–0,85× | 1,2–1,8× | Há sinal; colete mais pontos |
| **Funcionou** | **< 0,6×** | **> 2×** | As manchas estão nas paredes |

`compare.py` imprime essa leitura automaticamente ao final.

## Uso

```bash
# avaliação completa
python3 src/compare.py data/processed data/ground_truth.json

# só o que é fisicamente recuperável (recomendado)
python3 src/compare.py data/processed data/ground_truth.json --tipos divisoria

# com limiar físico em vez de percentil
python3 src/compare.py data/processed data/ground_truth.json --limiar 1.0
```

| Flag | Padrão | Efeito |
|---|---|---|
| `--tipos` | todas | avaliar só paredes destes tipos, separados por vírgula |
| `--limiar` | percentil casado | densidade mínima (dB/m) para considerar parede |
| `--tolerancia` | 1 célula | raio, em metros, para contar uma previsão como próxima |

## Como usar isto para melhorar o mapa

**Compare configurações, não valores absolutos.** O uso mais produtivo é rodar `reconstruct.py`
com parâmetros diferentes e ver qual sobe a razão contra o acaso:

```bash
for n in 2.0 2.3 2.6; do
  python3 src/reconstruct.py data/raw/survey.jsonl --n-referencia $n --out /tmp/m$n
  python3 src/compare.py /tmp/m$n data/ground_truth.json --tipos divisoria | grep ponderada
done
```

⚠️ **Cuidado com o overfitting de parâmetro.** Se você ajustar `--lam`, `--mu` e
`--n-referencia` até maximizar o F1 contra o seu ground truth, o resultado não generaliza para
outra casa. Ajuste no máximo um ou dois, e prefira sempre mais dados a mais ajuste: o insumo
escasso deste projeto é **cobertura espacial**, não sintonia fina (`docs/12`, D3).
