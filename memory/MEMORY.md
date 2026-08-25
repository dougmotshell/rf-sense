# Memória — rf-sense

Índice. **Uma linha por entrada, no máximo 200 linhas**; o detalhe vai no arquivo por
tópico em `memory/<topico>.md`. Se uma entrada não cabe numa linha, ela não pertence
aqui.

Irmãos: [`AGENTS.md`](../AGENTS.md) (contrato) ·
[`docs/12-decisoes.md`](../docs/12-decisoes.md) (as 21 decisões do projeto, que são
append-only e **não** são memória).

## Entradas

**Nenhuma, e é o estado correto por enquanto.**

A regra abaixo — não registrar o que o repositório já conta — esvazia esta seção num
projeto que documenta tanto. Os candidatos naturais já têm dono melhor:

| O que se registraria | Onde já está |
|---|---|
| Cadência de 0,1 Hz e degrau de 1,25 dB deste rádio | [`docs/16 §16.3`](../docs/16-modos-e-poc.md) |
| Por que a sonda saiu do modo gratuito | [`D20`](../docs/12-decisoes.md) |
| Por que a máscara própria inverte a conclusão | [`D21`](../docs/12-decisoes.md) |
| Estado atual: bloqueado na Fase 0 | `make poc`, que mede em vez de lembrar |

Entrada aqui só se aparecer algo que **nenhum** desses lugares cobre e que se perderia
entre sessões — por exemplo uma peculiaridade do apartamento medido, ou um AP de vizinho
que muda de canal e estraga a coleta em determinado horário.

Índice vazio com a razão declarada vale mais que entrada inventada para preencher.

## Regras

- Data relativa vira data absoluta ("na semana passada" → `2026-08-17`).
- Não registre o que o repositório já conta: estrutura de código, histórico do git,
  conteúdo do `AGENTS.md`, decisões do `docs/12`.
- Nunca registre segredo, token, hostname real, PII ou nome de cliente. **BSSID e SSID
  são dado pessoal** — nem aqui.
- Entrada errada é apagada, não corrigida por acréscimo.
