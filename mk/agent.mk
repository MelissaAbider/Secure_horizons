# Allocation agent: Claude on Bedrock picks the markets through MCP tools; the platform checks and executes. Included by the root Makefile.
.PHONY: agent-once agent-mcp agent-tools test-agent

agent-once: ## one agent cycle against a fresh process store (use the dashboard button for the live backend)
	$(PYTHON) -m backend.autopilot once

agent-mcp: ## MCP server (stdio) proxying the running backend's agent tools: claude mcp add secure-horizons -- .venv/bin/python -m backend.mcp_server
	$(PYTHON) -m backend.mcp_server

agent-tools: ## list the MCP tools the running backend exposes
	@curl -s http://127.0.0.1:8000/api/agent/tools | $(PYTHON) -m json.tool

test-agent: ## agent tests (offline: Bedrock, chain and teller stubbed)
	$(PYTHON) -m pytest backend/tests/test_agent_*.py -q
