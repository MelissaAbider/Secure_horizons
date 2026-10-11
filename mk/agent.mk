# AI agent (proposes, never executes) and the API server for the EC2 VM.
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

.PHONY: agent-demo serve test-agent

agent-demo: ## agent proposal at block 45201838 after the incident ("14% APY" bait) -> REFUSED with reasons
	$(PYTHON) -m backend.agent demo

serve:      ## API on 0.0.0.0:8000 for the VM, one process (in-memory store): no --reload, no --workers
	$(PYTHON) -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

test-agent: ## agent tests (offline, boto3 stubbed)
	DRY_RUN_ACTIONS=true USE_FIXTURES=false $(PYTHON) -m pytest backend/tests/test_agent_*.py -q
