# Alerting and DORA draft, detection-only (T4 notify + T5 report). Included by the root Makefile.
.PHONY: watch test-t5

watch: ## T3 engine on $NETWORK: prints alerts, posts them to Discord (ALERT_WEBHOOK_URL), writes DORA drafts to data/reports/
	$(PYTHON) -m backend.alerting

test-t5: ## Discord payload, incident, DORA classification and PDF (no network)
	$(PYTHON) -m pytest backend/tests/test_t5_*.py -q
