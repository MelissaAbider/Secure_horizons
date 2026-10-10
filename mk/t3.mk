.PHONY: test-t3 replay-t3

test-t3: ## run deterministic KelpDAO surveillance tests
	$(PYTHON) -m pytest backend/tests/test_t3_*.py -q

replay-t3: ## replay attack fixtures (override with FILE=fixtures/snapshots_normal.jsonl)
	$(PYTHON) -m backend.engine --replay $(or $(FILE),fixtures/snapshots_attack.jsonl)
