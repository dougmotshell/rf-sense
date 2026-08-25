# 12 — Decisões de projeto

---

Registro das decisões estruturais e do porquê. Serve para não refazer a mesma discussão daqui
a seis meses — e para saber o que revisitar se uma premissa mudar.

---

### D1 · Perseguir tomografia por atenuação, não imageamento coerente

**Contexto.** O objetivo declarado é "enxergar o ambiente": mapa, visão 3D, topografia.

**Decisão.** Reconstruir um mapa 2D de atenuação, abandonando explicitamente holografia e SAR.

**Por quê.** Imageamento coerente exige **fase**. O QCA6174 (`ath10k`) não expõe fase e não tem
ferramenta de CSI utilizável — o Atheros CSI Tool é exclusivo de `ath9k`. Não há workaround por
software: é limitação de firmware. Tomografia precisa apenas de potência, que é universalmente
disponível.

**Descartado.** Holografia (Holl & Reinhard), SAR, reconstrução neural (GeRaF usa radar mmWave
de 77 GHz e 32 h de treino em H100).

**Revisitar se.** Aparecer um SDR (HackRF, ~US$ 150) ou um ESP32-S3 (~US$ 8, dá CSI). O HackRF é
o único item que devolve fase e reabre a porta da holografia.

---

### D2 · Ground truth como fase 0, antes de qualquer coleta de RF

**Decisão.** Medir e digitalizar a planta real **antes** de coletar um único RSSI.

**Por quê.** Um mapa reconstruído errado que parece plausível é o pior resultado possível — pior
que nenhum mapa, porque você acredita nele. Sem referência independente não existe avaliação,
apenas impressão. É o erro que a maioria dos projetos amadores comete.

**Custo.** Uma tarde com trena e fita crepe.

---

### D3 · O celular é o sensor principal, não o laptop

**Por quê.** Tomografia exige raios cruzando em **ângulos variados**. Um receptor parado produz
um leque de raios saindo do mesmo ponto — e um leque não determina o mapa (`docs/07 §3`). A
diversidade espacial é o insumo escasso, e ela vem de **andar pela casa**.

**Consequência.** A qualidade do mapa depende mais de quantos pontos você visita do que de
qualquer parâmetro do algoritmo. Otimizar código antes de coletar dados é otimizar a parte errada.

---

### D4 · numpy puro, sem scipy

**Decisão.** Implementar o solver com gradiente projetado em numpy, sem depender de scipy.

**Por quê.** numpy já está instalado; scipy não. "Custo zero" inclui não exigir instalação. O
problema é pequeno (~200 células, ~400 raios) e converge em 400 iterações. O gradiente projetado
impõe `x ≥ 0` naturalmente, o que `np.linalg.solve` não faz.

**Descartado.** `scipy.optimize.nnls` (dependência), equações normais diretas (não impõem
não-negatividade), ART/SART (convergem bem, mas regularizar é mais trabalhoso).

**Revisitar se.** A grade passar de ~2000 células, quando `MᵀM` denso começa a pesar.

---

### D5 · Busca em grade para localizar APs, não otimizador

**Por quê.** A superfície de erro do modelo log-distance tem múltiplos mínimos locais. Um
otimizador local cairia no errado dependendo do chute inicial. A busca grosseiro-para-fino é
mais lenta, mas robusta — e o espaço de busca é pequeno.

**Otimização aplicada.** `a_ref` tem solução em forma fechada dada a posição candidata (é a média
dos resíduos), o que reduz a busca de 3 para 2 dimensões.

---

### D6 · Dois expoentes de perda de percurso, ambos configuráveis

**Contexto.** Descoberto durante a validação sintética (`docs/10`): usar um expoente para
localizar APs (2,6) e outro para calcular o excesso (2,0) injeta um viés de `6·log₁₀(d)` dB, que
a tomografia espalha como fundo difuso.

**Decisão.** Manter os dois separados, expor `--n-referencia` e documentar o trade-off, em vez de
escolher um padrão único.

**Por quê.** As duas configurações são legítimas e respondem a perguntas diferentes:
`n_ref = 2.0` dá atenuação **absoluta**; `n_ref = n_percurso` dá **desvio em relação à parede
média**, com contraste muito melhor. Esconder essa escolha atrás de um padrão silencioso
produziria mapas que o usuário não saberia interpretar.

**Padrão escolhido.** `2.0`, porque é fisicamente interpretável. Mas a documentação recomenda
rodar as duas e comparar.

---

### D7 · Amostragem uniforme no traçado de raio, não Siddon

**Por quê.** A amostragem (12,5 cm) é 4× mais fina que a célula (50 cm), e o erro de
discretização resultante é pequeno perto do ruído de 2–6 dB do RSSI. Refinar o traçado antes de
reduzir o ruído de medição seria otimizar a parte errada do orçamento de erro.

**Revisitar se.** A célula chegar perto do passo de amostragem (grade < 0,2 m).

---

### D8 · Hash do BSSID por padrão, SSID nunca gravado

**Decisão.** `survey.py` grava SHA-256 truncado do BSSID com salt fixo. SSID não é gravado.
`--keep-bssid` existe, mas é opt-in.

**Por quê.** BSSID é **dado pessoal** sob a LGPD: identifica um equipamento e, por consequência,
um domicílio (bases como a WiGLE mapeiam BSSID → coordenada). SSID frequentemente contém nome de
família. O hash com salt fixo preserva o que a tomografia precisa — que o mesmo AP tenha o mesmo
id entre execuções — sem preservar o que ela não precisa.

**Consequência.** Mudar o salt invalida datasets antigos. É um custo aceitável.

---

### D9 · `data/` inteiro no `.gitignore`

**Por quê.** Um `survey.jsonl` com BSSIDs reais é, na prática, um mapa da rede da vizinhança.
O padrão seguro é não versionar nada de `data/`; publicar exige ação deliberada, não descuido.

---

### D10 · Simulador dentro do projeto

**Por quê.** Permite validar a matemática sem trabalho de campo, e — mais importante — permite
**dimensionar o esforço antes de gastá-lo**: editando `PLANTA_EXEMPLO` para a sua casa e variando
`--step` e `--noise`, você descobre quantos pontos precisa medir antes de sair medindo.

**Limitação assumida e documentada.** O simulador usa o mesmo modelo direto que o reconstrutor
inverte. Valida a **matemática**, não a **física** (`docs/10`, seção final).

---

### D11 · Saída em ASCII e PGM, matplotlib opcional

**Por quê.** matplotlib não está instalado e "custo zero" inclui não exigir instalação. ASCII
funciona por SSH e cola direto na documentação; PGM binário abre em qualquer visualizador e são
30 linhas de código sem dependência. O CSV cobre análise quantitativa.

---

### D12 · Documentar o que **não** funciona com o mesmo cuidado do que funciona

**Por quê.** A maior parte do tempo perdido neste domínio vem de perseguir capacidades que o
hardware não tem, animado por manchetes. `docs/01` e `docs/04` existem para tornar esse muro
visível **antes** do investimento de esforço, não depois.

Um "não é possível, e aqui está exatamente por quê" bem fundamentado é entrega tão legítima
quanto código que roda.

---

### D13 · Duas famílias de métrica, com baseline aleatório sempre visível

**Decisão.** `compare.py` reporta sobreposição (IoU, F1) **e** proximidade (distância às
paredes), cada uma acompanhada do valor esperado ao acaso.

**Por quê.** Sobreposição é dura demais com mapas borrados: meia célula de deslocamento zera a
interseção mesmo com a mancha centrada corretamente. Proximidade é a métrica honesta para
tomografia RF. Reportar só uma delas engana — em direções opostas.

O baseline aleatório existe porque nenhum valor absoluto é interpretável aqui. F1 = 0,62 parece
bom até se descobrir que o acaso dá 0,438.

---

### D14 · Binarização por percentil casado, não por limiar escolhido

**Decisão.** Por padrão, prever exatamente tantas células quantas o ground truth tem.

**Por quê.** O limiar é um grau de liberdade que permite fabricar o resultado desejado —
subindo-o, a precisão sobe e o recall cai, e escolhe-se o ponto que favorece a narrativa.
O percentil casado elimina isso: precisão e recall ficam estruturalmente iguais.
`--limiar` continua disponível para quando se quer um valor físico.

---

### D15 · Avaliar apenas o que é fisicamente recuperável

**Decisão.** `--tipos divisoria` restringe a avaliação às paredes internas.

**Por quê.** Paredes externas são indetectáveis por construção: todos os pontos de coleta estão
do lado de dentro, nenhum raio as percorre tangencialmente, e a atenuação que impõem é quase
idêntica para todos os raios — vira constante absorvida pelo `a_ref` (`docs/10`).

Avaliar contra elas não mede o sistema, mede uma impossibilidade. Não é aliviar a régua; é usar
a régua certa. A limitação segue documentada — o que muda é ela não mascarar o sinal real.

---

### D16 · O mapa carrega a própria georreferência

**Decisão.** `reconstruct.py` grava `mapa_meta.json` com origem, grade, dimensões **e os
parâmetros que geraram aquele mapa**.

**Por quê.** Sem origem e escala, `mapa.csv` é uma matriz sem posição no mundo e não há como
sobrepô-la ao ground truth. Sem os parâmetros, comparar duas execuções vira adivinhação — e
comparar execuções é justamente o uso mais produtivo do `compare.py`.

---

### D17 · Modo como registro declarativo, não como flag solta

**Decisão.** Um único registro (`src/modos.py`) declara, por modo, a camada alcançável, a
largura de banda, se há fase, os requisitos verificáveis e o estado de verificação do
backend. Todas as ferramentas consultam esse registro.

**Por quê.** A alternativa era cada ferramenta ter suas próprias flags de hardware. Isso
espalha a mesma pergunta — "isto funciona aqui?" — por seis lugares que discordam entre
si. Pior: sem um lugar onde a **camada** e o **ΔR** estejam declarados, volta a confusão
que [`01`](01-viabilidade.md) e [`04`](04-analise-das-fontes.md) existem para combater, só
que dentro do próprio código.

**Consequência.** Quando o hardware muda, muda-se uma entrada do registro, não seis
ferramentas. E `--explicar` responde por escrito o que antes era tentativa e erro.

---

### D18 · Requisito de compra vence requisito ausente

**Decisão.** Ao classificar um modo, um requisito do tipo `compra` tem precedência sobre
um binário ou dispositivo faltando.

**Por quê.** Dizer "falta `hackrf_transfer`" a quem não tem um HackRF é diagnóstico errado:
sugere que um `apt install` resolve. Não se instala o caminho para fora de não possuir o
equipamento. A precedência deliberadamente **não** é a ordem da lista de requisitos.

**Consequência.** Existe um quarto estado, `incerto`, para o que software não consegue
verificar — se o seu AP suporta FTM, se há tráfego com sounding na rede. Não é
"disponível" nem "faltando": é **teste manual**, e o registro diz qual.

---

### D19 · Backend não verificado se declara, e sempre oferece o dado cru

**Decisão.** Dos nove backends, seis nunca rodaram contra hardware. Cada um carrega
`VERIFICADO = False`, avisa em tempo de execução, propaga o aviso para o `mapa_meta.json`,
e implementa `dump_bruto()`.

**Por quê.** A alternativa honesta seria não escrever esses parsers. Mas eles são o passo
que alguém com o hardware na mão completa em minutos, e escrevê-los agora é trabalho útil
— **desde que não finjam estar testados**. Um parser não testado que se apresenta como
testado produz números plausíveis e errados, que é o pior resultado possível ([D12](#)).

O `dump_bruto()` é a saída disso: se o parser estiver errado, o dump continua certo. É por
ele que se depura, e é ele que torna o parser corrigível por quem tiver a placa.

---

### D20 · Cadência é portão, e vem antes de tudo

**Decisão.** O `poc.py` mede a taxa com que o valor **muda** antes de qualquer coleta, e
trata isso como portão bloqueante.

**Por quê.** Descoberto medindo: neste laptop o modo `free` consulta o `nmcli` a 12,95 Hz e
o valor muda a 0,113 Hz — um fator de 114. Consultar mais rápido não gera informação nova,
só repete o cache. Sem esse portão, "15 amostras por ponto" pareceria significar 15
medições independentes, e a mediana sobre elas pareceria mais confiável do que é.

**Consequência direta.** A pessoa como sonda ([`15 §2`](15-viabilizar-na-pratica.md))
precisa de ≥ 2 Hz e **saiu do modo gratuito** — a matemática está implementada e validada
no simulador, e a cadência é que não existe. Em seu lugar entrou o protocolo **estático**
de comparação A/B, que é o que 0,1 Hz permite.

**Registrar isto importa** porque `docs/15` foi escrito assumindo cadência suficiente sem
tê-la medido. A correção veio de uma medição de 45 segundos, e é exatamente o que um portão
serve para produzir.

---

### D21 · Máscara de cobertura na avaliação, com régua comum entre configurações

**Decisão.** `compare.py --cobertura` avalia só as células sustentadas por dados, e
recalcula o baseline do acaso sob a mesma máscara. `orcamento.py` compara configurações
diferentes sob uma **régua comum**, nunca sob a máscara própria de cada uma.

**Por quê.** A primeira parte é [D15](#) aplicado à cobertura em vez de ao tipo de parede:
avaliar onde nenhum raio passou mistura falha de reconstrução com ausência de medição, e
nenhuma métrica separa as duas depois.

A segunda parte corrige um erro que a primeira versão cometeu. Sob a própria máscara, o
resultado **melhora** quando se mede menos: com poucos pontos a máscara encolhe para o
miolo fácil da casa, as bordas difíceis saem da conta, e o número sobe. A ferramenta
chegou a afirmar que 12 pontos empatavam com 70. É o mesmo grau de liberdade escondido que
[D14](#) eliminou no limiar, reaparecendo na dimensão espacial.

**Consequência.** Três colunas, cada uma respondendo a uma pergunta diferente — funciona
onde há dado? qual configuração é melhor? quanto da casa você cobriu? — e aprovação
exigindo as três. Com isso o padrão de `--step 1.0` passou a ser **derivado**: é o mais
barato que passa, e 0,75 m custa +38 min de campo por +0% de F1.
