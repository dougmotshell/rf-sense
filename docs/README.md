# Documentação — rf-sense

**O índice de verdade é [`00-indice.md`](00-indice.md).** Comece por lá, ou direto pelo
manual em linguagem simples: [`17-comece-aqui.md`](17-comece-aqui.md).

## Onde os documentos moram

Os 18 documentos deste projeto são **arquivos numerados e planos** em `docs/`:
`00-indice.md`, `01-viabilidade.md`, … `17-comece-aqui.md`. Documento novo entra nesse
padrão e é registrado no índice.

O número é ordem de leitura sugerida, não hierarquia — e não é sequência estanque: o
`14` responde ao `04`, o `15` deriva do `14`, o `16` mede o que o `15` supôs. O índice
mostra os agrupamentos (Fundamentos, Execução, Técnico, Responsabilidade, Fontes).

## Deliberadamente ausente

Ausência declarada vale mais que árvore vazia, então:

- **`pt-br/architecture/` (C4), `pt-br/specs/` (SDD), `pt-br/decisions/` (ADR),
  `pt-br/manual/` — e os irmãos `en-us/` — são andaime de template e estão vazios.**
  Não use. O que cada um cobriria já existe em outro lugar, num projeto deste tamanho:

  | Árvore de template | Onde o conteúdo realmente está |
  |---|---|
  | `architecture/` (C4) | [`07 — Teoria`](07-teoria-tomografia.md) e o `docs/00` § Código. Um projeto de nove arquivos em `src/` não tem quatro níveis de C4 para descrever |
  | `specs/` (SDD) | [`03 — Roadmap`](03-roadmap.md), com critério de sucesso verificável por fase |
  | `decisions/` (ADR) | [`12 — Decisões`](12-decisoes.md), 21 decisões num arquivo. Mesma disciplina de um ADR, sem um arquivo por decisão |
  | `manual/` | [`17 — Comece aqui`](17-comece-aqui.md) e [`08 — Manual de uso`](08-manual-de-uso.md) |

- **Não há tradução en-US.** Uma árvore de stubs apontando para o pt-BR seria pior que
  a ausência: dá a impressão de bilinguismo sem entregar nada.

Se o projeto crescer ao ponto de precisar das quatro árvores, o caminho é migrar os
numerados para elas — não manter os dois padrões ao mesmo tempo.

## Regras

- Diagrama é texto: Mermaid (ou PlantUML) cercado no Markdown, para diferenciar e
  revisar. Imagem binária pode ilustrar, nunca ser a única fonte.
- **Todo número afirmado vem com o comando que o reproduz**, ao lado ou em seção
  própria. Ver [`16 §16.5`](16-modos-e-poc.md).
- **O que não funciona é documentado com o mesmo cuidado do que funciona**
  ([D12](12-decisoes.md)).
- Decisão registrada em [`12`](12-decisoes.md) é append-only: uma decisão superada ganha
  nota de superação, não reescrita. Número nunca é reusado.
- Ligação nos dois sentidos: quem afirma cita a decisão que o autoriza, e a decisão cita
  o documento que a aplica.
- Arquivos AUTORADOS: sem banner `managed-by:`, o gerador nunca toca aqui.
