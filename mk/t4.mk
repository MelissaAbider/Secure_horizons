# T4 · Response: withdraw buttons on the Discord fraud alert (docs/discord-actions.md). Included by the root Makefile.
.PHONY: test-t4

test-t4: ## T4 tests: Discord withdraw buttons (signature, allow-list, fixed button ids, teller window), offline
	$(PYTHON) -m pytest backend/tests/test_t4_*.py -q
