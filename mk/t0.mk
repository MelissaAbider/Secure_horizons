# T0 · Foundations (TASKS.md T0). Included by the root Makefile.
.PHONY: test-t0 fixtures

test-t0: ## T0 tests: contract, fixture routes, settings, store, wiring
	$(PYTHON) -m pytest backend/tests/test_t0_*.py -q

fixtures: ## regenerate fixtures/ from backend/models.py (T0 only, then commit models + fixtures + types.ts together)
	$(PYTHON) -m fixtures._generate
