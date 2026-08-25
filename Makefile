# harness-bootstrap >>>
# Neutral sensor interface. CI, pre-commit and the PostToolUse hook all call these
# targets, so nothing downstream knows your stack. Fill the TODO commands once and
# every consumer starts working.
#
# A TODO target FAILS on purpose — a sensor that silently succeeds is worse than no
# sensor. See templates/harness/README.md for the per-stack recipe.

.DEFAULT_GOAL := help
.PHONY: help test lint typecheck format lint-file format-file sync sync-check harness harness-gate harness-report poc modos sim camadas orcamento cadencia

TODO = @printf 'TODO: fill the `%s` target in the Makefile.\n' $@ && exit 1

help:  ## List the targets
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

test:  ## SNS-01/05 — autoteste de ponta a ponta, sem hardware (~1 min)
	./scripts/selftest.sh

lint:  ## SNS-02 — run the linter over the whole tree (ruff, eslint, golangci-lint)
	$(TODO)

typecheck:  ## SNS-03 — type check (mypy --strict, tsc --noEmit, or a typed language)
	$(TODO)

format:  ## SNS-04 — format the whole tree (ruff format, prettier, gofmt, rustfmt)
	$(TODO)

# --- one file at a time: called by the PostToolUse hook, so keep these fast ---

lint-file:  ## Lint just $(FILE)
	$(TODO)

format-file:  ## Format just $(FILE) in place
	$(TODO)

# --- AI surfaces -----------------------------------------------------------

sync:  ## Regenerate the AI surfaces from their authored sources
	python3 scripts/sync-ai-surfaces.py

sync-check:  ## Fail if a generated surface drifted from its source
	python3 scripts/sync-ai-surfaces.py --check

harness:  ## Score the harness (36 checks, 108 points, levels L0-L4)
	npx -y harness-score

harness-gate:  ## The same scan as a gate — fails below MIN_LEVEL (default 3)
	npx -y harness-score --min-level $(or $(MIN_LEVEL),3)

harness-report:  ## Write the scan as markdown and as JSON, for a PR or a baseline
	npx -y harness-score --md harness-report.md --json > harness-report.json
# harness-bootstrap <<<

# --- rf-sense: atalhos do projeto ------------------------------------------
# Fora do bloco gerenciado acima de propósito: são específicos deste projeto,
# não sensores do harness.

poc:  ## Dá para seguir, neste hardware, hoje? Cinco portões e um veredito
	python3 src/poc.py --modo $(or $(MODO),free)

modos:  ## Os nove modos free/pago, e o que roda nesta máquina
	python3 src/modos.py --listar
	@echo
	python3 src/modos.py --detectar

cadencia:  ## Portão 0: a cadeia de medição é rápida o bastante para o quê?
	python3 src/probe.py cadencia --modo $(or $(MODO),free) --dur $(or $(DUR),45)

orcamento:  ## Quantos pontos de coleta valem a pena, com número
	python3 src/orcamento.py

sim:  ## Pipeline inteiro no simulador, onde a resposta é conhecida
	python3 src/simulate.py --out data/raw/sim.jsonl
	python3 src/reconstruct.py data/raw/sim.jsonl --grid 0.5 --n-referencia 2.6 --modo sim
	python3 src/compare.py data/processed data/ground_truth.example.json \
		--tipos divisoria --cobertura

camadas:  ## Sete camadas com procedência declarada, a partir do último mapa
	python3 src/camadas.py --survey $(or $(SURVEY),data/raw/sim.jsonl) --tipos divisoria
