# T2 · Scenario (TASKS.md T2). Included by the root Makefile. NETWORK comes from .env or the command line.
SEED ?= 0
VARIANT ?= default
MINUTES ?= 5

.PHONY: seed attack normal reset test-t2

seed: ## put the deployed contracts in the reference state (does nothing if already done)
	$(PYTHON) -m scenario.seed

attack: ## replay the rsETH attack (SEED=0 default params, SEED=n replayable draw, VARIANT=default|slow|usdc)
	$(PYTHON) -m scenario.attack --seed $(SEED) --variant $(VARIANT)

normal: ## harmless traffic for MINUTES minutes (blocking), writes a RunRecord labelled normal
	$(PYTHON) -m scenario.normal --minutes $(MINUTES) --seed $(SEED)

reset: ## redeploy (make deploy FORCE=1) then seed, monitoring paused meanwhile
	$(PYTHON) -m scenario.reset

test-t2: ## T2 tests (chain tests need NETWORK=local, anvil and make deploy)
	$(PYTHON) -m pytest backend/tests/test_t2_*.py -q
