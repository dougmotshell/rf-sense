# rf-sense

Estudo pessoal que usa Wi-Fi e Bluetooth para **reconstruir a geometria de um ambiente
interno** — onde estão as paredes — com laptop e celular apenas, a custo financeiro zero.
Público: uma pessoa, no seu próprio apartamento, com uma trena.

Este arquivo é o **contrato canônico**. `CLAUDE.md` e `.github/copilot-instructions.md`
o importam; nunca duplique conteúdo neles. Codex, Copilot, Cursor e Gemini CLI leem
este arquivo nativamente.

Irmãos: `.claude/agents/` (agentes) · `skills/` (procedimentos) · `.claude/rules/`
(regras por caminho) · `docs/` (18 documentos numerados) · `memory/`.

## Stack

Python 3.12 · **numpy é a única dependência** (`requirements.txt`). `pyserial` é
opcional e serve a um backend só.

Não há scipy, não há matplotlib, não há framework de teste. Isso é decisão registrada,
não omissão: [D4](docs/12-decisoes.md) implementa o solver em numpy puro e
[D11](docs/12-decisoes.md) renderiza em ASCII e PGM, porque "custo zero" inclui não
exigir instalação.

## Comandos

| Ação | Comando |
|---|---|
| Instalar | `pip install -r requirements.txt` |
| Rodar (dá para seguir hoje?) | `make poc` · `python3 src/poc.py --modo free` |
| Testar | `make test` · `./scripts/selftest.sh` |
| Lint / formatar | não há — nenhum linter configurado |
| Pipeline no simulador | `make sim` |
| Sincronizar superfícies de IA | `python3 scripts/sync-ai-surfaces.py` |

`make test` roda o pipeline inteiro contra uma planta conhecida e assere o baseline de
[`docs/13`](docs/13-avaliacao.md). Leva ~1 min, não usa rádio nem rede.

## Convenções que diferem do padrão da ferramenta

- **Identificadores em pt-BR**, junto com a prosa: `traçar_raio`, `medidas`, `resolver`,
  `cobertura`. Inclui acentos. É deliberado — o código e os documentos falam a mesma
  língua, e o custo de traduzir os conceitos duas vezes era maior que o de acentuar
  identificadores. Nomes de arquivo e flags de CLI seguem a mesma língua (`--cobertura`,
  `--aps-fixos`).
- **Prosa só em pt-BR.** Não existe árvore en-US preenchida, e criar uma vazia seria
  pior que não ter.
- **Documento novo entra em `docs/NN-nome.md`**, numerado, plano, e é registrado em
  `docs/00-indice.md`. As árvores `docs/pt-br/` e `docs/en-us/` são andaime de template
  e estão vazias — ver `docs/README.md`.
- Nomes de arquivos e pastas em **lowercase** (`kebab-case`), exceto onde a convenção do
  próprio arquivo exige outra grafia (`README.md`, `AGENTS.md`).
- **Todo número afirmado é reproduzível.** Quando a documentação diz "0,113 Hz" ou
  "F1 3,5× o acaso", o comando que produz aquilo aparece junto. Ver
  [`docs/16 §16.5`](docs/16-modos-e-poc.md).
- **O que não funciona é documentado com o mesmo cuidado do que funciona**
  ([D12](docs/12-decisoes.md)). Um "não é possível, e aqui está exatamente por quê" é
  entrega tão legítima quanto código que roda.

## Armadilhas

Uma linha por armadilha; cada uma já custou tempo aqui.

- **Perguntar rápido ao `nmcli` não devolve dado novo.** 13 consultas/s, valor mudando a
  cada 9 s. "15 amostras" pode ser 3 valores repetidos cinco vezes. Meça a cadência
  antes: `make cadencia` ([D20](docs/12-decisoes.md)).
- **Forçar rescan custa ~8 s por varredura.** É o preço do dado fresco, e é de onde vem
  a estimativa de 2 min por ponto de coleta.
- **Comparar execuções sob a máscara de cobertura própria de cada uma dá conclusão
  invertida:** medir menos parece melhor, porque a máscara encolhe para a parte fácil.
  Use a régua comum do `orcamento.py` ([D21](docs/12-decisoes.md)).
- **Na sonda, mínimo na ponta do trajeto é armadilha geométrica:** significa que a reta
  do AP cruza fora do trecho percorrido, e a direção sai errada. Filtrado por
  `--margem-borda` ([`docs/16 §16.4`](docs/16-modos-e-poc.md)).
- **Referencial (0,0) diferente entre `ground_truth.json` e o survey** produz um mapa que
  não é melhor que o acaso, sem nenhum erro na tela. É a primeira coisa a checar.
- **Girar o dispositivo durante a coleta injeta erro do tamanho do sinal.** Corpo humano
  atenua 3–6 dB; parede interna, ~6 dB.
- **Seis dos nove backends de `fontes.py` nunca rodaram contra hardware.** Carregam
  `VERIFICADO = False` e avisam. Depure por `dump_bruto()`, que mostra bytes crus e
  continua certo mesmo se o parser estiver errado ([D19](docs/12-decisoes.md)).
- **`--n-percurso` e `--n-referencia` diferentes injetam viés de `6·log₁₀(d)` dB** que a
  tomografia espalha como fundo difuso. As duas configurações são legítimas e respondem
  a perguntas diferentes ([D6](docs/12-decisoes.md), `docs/07`).
- **O hardware ignora `spectral_count`** e envia amostras indefinidamente: limite a
  captura por **tempo**, não por contagem.
- **Trocar o salt do hash de BSSID invalida datasets antigos** ([D8](docs/12-decisoes.md)).

## Nunca

- Editar arquivo com o banner `managed-by:` — edite a fonte e rode o gerador.
- Escrever segredo, token, hostname real, PII ou nome de cliente. **BSSID e SSID são
  dado pessoal** sob a LGPD: `data/` inteiro está no `.gitignore`
  ([D8](docs/12-decisoes.md), [D9](docs/12-decisoes.md), `docs/05`).
- Inventar arquitetura, decisão, número ou passo de usuário: use `TODO:`.
- Apresentar como testado um backend que nunca viu o hardware.
- Aplicar branding corporativo ou rótulo de classificação: **este é projeto pessoal**, e
  marcá-lo como documentação interna de empresa atribuiria a ela algo que não é dela.

## Documentação

18 documentos em `docs/`, numerados e planos, com índice em
[`docs/00-indice.md`](docs/00-indice.md).

Portas de entrada, por leitor:

| Quem chega | Vai para |
|---|---|
| Nunca viu o projeto | [`17 — Comece aqui`](docs/17-comece-aqui.md) |
| Quer saber se é possível | [`01 — Viabilidade`](docs/01-viabilidade.md) |
| Quer rodar | [`08 — Manual de uso`](docs/08-manual-de-uso.md) |
| Quer saber por que uma escolha foi feita | [`12 — Decisões`](docs/12-decisoes.md) |
| Quer saber se dá para seguir hoje | [`16 — Modos e POC`](docs/16-modos-e-poc.md) |

## Memória

`memory/MEMORY.md` é o índice (uma linha por entrada, até 200 linhas); o detalhe vai
nos arquivos por tópico.
