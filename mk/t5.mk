# T5 · Incident and DORA. Included by the root Makefile (T0); until then: make -f mk/t5.mk <target>
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

.PHONY: test-t5 dora-report dora-demo

test-t5:      ## T5 tests (offline, no AWS)
	$(PYTHON) -m pytest backend/tests/test_t5_*.py -q

dora-report:  ## write data/reports/$(ID).md from the running backend
	$(PYTHON) -m backend.dora report --id $(ID) --api http://127.0.0.1:8000

dora-demo:    ## print the incident and DORA report for the scenario (offline, no API); uses the T4 decision-demo evidence if present
	$(PYTHON) -m backend.dora demo
