# T4 · Response and evidence. Included by the root Makefile (T0); until then: make -f mk/t4.mk <target>
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

.PHONY: verify tamper restore decision-demo test-t4

verify:  ## verify a decision from its evidence file: make verify ID=DEC-…
	$(PYTHON) -m backend.cli verify $(ID)

tamper:  ## demo only: make tamper ID=DEC-… FIELD=decision.actions.2.params.asset VALUE=DAI
	$(PYTHON) -m backend.cli tamper $(ID) --field $(FIELD) --value '$(VALUE)'

restore: ## put back the evidence file saved by tamper: make restore ID=DEC-…
	$(PYTHON) -m backend.cli restore $(ID)

decision-demo: ## dry-run replay of R1 at block 45201812 -> data/evidence/DEC-fuji-45201812-1.json
	DRY_RUN_ACTIONS=true $(PYTHON) -m backend.cli demo

test-t4: ## T4 tests (dry-run; T4-25 skips without anvil)
	DRY_RUN_ACTIONS=true USE_FIXTURES=false $(PYTHON) -m pytest backend/tests/test_t4_*.py -q
