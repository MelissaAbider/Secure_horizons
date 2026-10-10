# Root Makefile (TASKS.md 2.11). Owner: T0.
# Each task adds its own targets in mk/tN.mk. The Python scripts read .env themselves (python-dotenv), and a variable
# set on the command line wins over .env: NETWORK=local make deploy. Never set NETWORK in a makefile.

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
.DEFAULT_GOAL := help

include $(wildcard mk/*.mk)

.PHONY: help setup backend demo test

help: ## list the available targets
	@grep -hE '^[a-zA-Z0-9_.-]+:.*## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  %-18s %s\n", $$1, $$2}'

setup: ## create .venv and install Python deps; npm and forge deps when their task has created them
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
	@if [ -f frontend/package.json ]; then npm --prefix frontend install; fi
	@if [ -f contracts/foundry.toml ]; then cd contracts && forge install; fi

backend: ## API on :8000 (one worker; every route serves fixtures until its task plugs in)
	$(PYTHON) -m uvicorn backend.main:app --port 8000

demo: ## local end to end: anvil, deploy, seed, backend with the engine on, dashboard
	@for t in chain deploy seed frontend; do $(MAKE) -n $$t >/dev/null 2>&1 || { echo "make demo needs the '$$t' target (TASKS.md 2.11)"; exit 1; }; done
	@mkdir -p data && ($(MAKE) chain > data/anvil.log 2>&1 &) && sleep 2
	NETWORK=local $(MAKE) deploy seed
	NETWORK=local ENGINE_ENABLED=true USE_FIXTURES=false DRY_RUN_ACTIONS=false $(PYTHON) -m uvicorn backend.main:app --port 8000 & $(MAKE) frontend

test: ## run the tests of every task that has a test-tN target
	@for t in test-t0 test-t1 test-t2 test-t3 test-t4 test-t5 test-t6 test-t7 test-t8 test-t9; do \
		if $(MAKE) -n $$t >/dev/null 2>&1; then echo "== $$t"; $(MAKE) --no-print-directory $$t || exit 1; fi; \
	done
