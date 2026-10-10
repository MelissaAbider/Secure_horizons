# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

.PHONY: test-t0 t4t5-e2e t4t5-demo

test-t0:   ## T0 shim tests (offline, dry-run; eth-account tests skip without it)
	DRY_RUN_ACTIONS=true USE_FIXTURES=false $(PYTHON) -m pytest backend/tests/test_t0_shim_*.py -q

t4t5-e2e:  ## T4+T5 end-to-end through the T0 shim wiring (dry-run)
	DRY_RUN_ACTIONS=true USE_FIXTURES=false $(PYTHON) -m pytest backend/tests/test_t0_shim_e2e.py -v

t4t5-demo: ## print decision, incident and verify for R1 at 45201812 (dry-run)
	DRY_RUN_ACTIONS=true $(PYTHON) -m backend.t0_shim_demo
