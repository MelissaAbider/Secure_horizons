# Root Makefile (TASKS.md 2.11). Owner: T0.
# Each task adds its own targets in mk/tN.mk. The Python scripts read .env themselves (python-dotenv), and a variable
# set on the command line wins over .env: NETWORK=local make deploy. Never set NETWORK in a makefile.

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
.DEFAULT_GOAL := help

include $(wildcard mk/*.mk)

.PHONY: help setup backend demo test lint

help: ## list the available targets
	@grep -hE '^[a-zA-Z0-9_.-]+:.*## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  %-18s %s\n", $$1, $$2}'

setup: ## create .venv, install Python deps, fetch the contracts' libraries, npm deps when the dashboard exists
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
	git submodule update --init --recursive
	@if [ -f frontend/package.json ]; then npm --prefix frontend install; fi
	@command -v forge >/dev/null || [ -x $(HOME)/.foundry/bin/forge ] || echo "Foundry missing: curl -L https://foundry.paradigm.xyz | bash && foundryup"

backend: ## API on :8000 with the .env settings (fixtures by default; make live for real data)
	$(PYTHON) -m uvicorn backend.main:app --port 8000

demo: ## local end to end: anvil, deploy, seed, backend with the engine on, dashboard
	@for t in chain deploy seed frontend; do $(MAKE) -n $$t >/dev/null 2>&1 || { echo "make demo needs the '$$t' target (TASKS.md 2.11)"; exit 1; }; done
	@mkdir -p data && ($(MAKE) chain > data/anvil.log 2>&1 &) && sleep 2
	NETWORK=local $(MAKE) deploy seed
	NETWORK=local ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false $(PYTHON) -m uvicorn backend.main:app --port 8000 & $(MAKE) frontend

test: ## run every test suite (chain tests need NETWORK=local, anvil and make deploy)
	@for t in test-t0 test-t1 test-t2 test-t3 test-t4 test-t5 test-t6 test-t7 test-t8 test-t9 test-t10 test-agent; do \
		if $(MAKE) -n $$t >/dev/null 2>&1; then echo "== $$t"; $(MAKE) --no-print-directory $$t || exit 1; fi; \
	done

lint: ## static checks: ruff on the Python code (pyproject.toml)
	$(PYTHON) -m ruff check .
