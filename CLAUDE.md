@AGENTS.md

`AGENTS.md` é canônico: tudo que vale para Claude Code, Codex e Copilot vive lá. Aqui
fica só o que é específico do Claude Code. Se uma seção serviria para as três CLIs,
ela está no lugar errado.

## Subagentes

Nenhum específico deste projeto ainda. `.claude/agents/example-specialist.md` é o
andaime do template, não um agente real — não o acione.

Se um dia houver um, o candidato óbvio é um revisor de asserções numéricas: quem checa
que todo número afirmado na documentação tem, ao lado, o comando que o reproduz.

## Comandos de barra

Gerados por `scripts/sync-ai-surfaces.py` a partir de `skills/` e `.claude/agents/`.
Hoje existe só o par de exemplo do template (`/example-procedure`,
`/example-specialist`); nenhum comando real deste projeto.

Os atalhos deste projeto são alvos de Makefile, não comandos de barra:
`make poc` · `make modos` · `make cadencia` · `make orcamento` · `make sim` ·
`make camadas` · `make test`.

## Servidores MCP

Nenhum. `.mcp.json` está vazio de propósito: o projeto não fala com serviço externo
nenhum, e não deve. Ele lê o rádio local e escreve em `data/`.

## Gerado vs. autorado

`.claude/skills/` e `.claude/commands/` são **gerados**. Edite `skills/<n>/SKILL.md`
ou `.claude/agents/<n>.md` e rode `python3 scripts/sync-ai-surfaces.py`.
Nunca edite um arquivo que abre com `managed-by:`.

## Ao trabalhar neste repositório

- Rode `make test` antes de afirmar que algo funciona. Ele demora ~1 min e já pegou
  dois defeitos que a leitura não pegou ([`docs/16 §16.4`](docs/16-modos-e-poc.md),
  [D21](docs/12-decisoes.md)).
- Número novo na documentação vem com o comando que o produz, ao lado.
- Backend que você não pôde testar contra hardware: marque `VERIFICADO = False` e
  implemente `dump_bruto()`. Não há vergonha em não ter a placa; há em fingir que tem.
