# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
-include .env
export

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)
.DEFAULT_GOAL := help

include mk/*.mk

TEST_TARGETS := $(patsubst mk/%.mk,test-%,$(sort $(wildcard mk/t*.mk)))

.PHONY: help setup backend test

help: ## list targets
	@grep -hE '^[a-zA-Z0-9_.-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  %-16s %s\n", $$1, $$2}'

setup: ## pip install -r requirements.txt if present
	@if [ -f requirements.txt ]; then $(PYTHON) -m pip install -r requirements.txt; else echo "no requirements.txt (T0 owns it)"; fi

backend: ## API on :8000, single worker (shim: USE_FIXTURES=false make backend for live T4/T5 routes)
	$(PYTHON) -m uvicorn backend.main:app --port 8000 --workers 1

test: $(TEST_TARGETS) ## all task tests (test-t0 and every test-tN)
