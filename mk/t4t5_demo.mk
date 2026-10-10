# Local T4 + T5 demo UI (dry-run). Not part of the product.
DEMO_PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)
.PHONY: t4t5-ui test-t4t5_demo
test-t4t5_demo: ## (no tests: demo UI only; root `make test` calls test-<mk file name>)
	@true
t4t5-ui: ## local T4+T5 demo UI on http://localhost:8000/demo (dry-run, offline)
	$(DEMO_PY) -m uvicorn demo.t4t5.server:app --port 8000
