# T5 · Incident and DORA. Included by the root Makefile (T0); until then: make -f mk/t5.mk <target>
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

.PHONY: test-t5 dora-report dora-demo dora-pdf dora-pdf-demo
dora-pdf:      ## write data/reports/$(ID).pdf from the running backend: make dora-pdf ID=INC-…
	$(PYTHON) -m backend.dora_pdf api --id $(ID) --api http://127.0.0.1:8000
dora-email:    ## e-mail the scenario DORA PDF: make dora-email TO=you@example.com (SMTP_* in .env)
	@$(PYTHON) -m backend.mailer --to "$(TO)"
dora-pdf-demo: ## write the scenario DORA report as PDF (offline) -> data/reports/INC-20261011-001.pdf
	$(PYTHON) -m backend.dora_pdf demo

test-t5:      ## T5 tests (offline, no AWS)
	$(PYTHON) -m pytest backend/tests/test_t5_*.py -q

dora-report:  ## write data/reports/$(ID).md from the running backend
	$(PYTHON) -m backend.dora report --id $(ID) --api http://127.0.0.1:8000

dora-demo:    ## print the incident and DORA report for the scenario (offline, no API); uses the T4 decision-demo evidence if present
	$(PYTHON) -m backend.dora demo
