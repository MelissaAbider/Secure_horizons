# T1 · On-chain contracts (TASKS.md T1). Included by the root Makefile. NETWORK comes from .env or the command line.
FORGE ?= $(if $(shell command -v forge),forge,$(HOME)/.foundry/bin/forge)
ANVIL ?= $(if $(shell command -v anvil),anvil,$(HOME)/.foundry/bin/anvil)

.PHONY: chain deploy abi fund-roles test-t1 t1-build

chain: ## local anvil chain, one block per second
	$(ANVIL) --block-time 1

t1-build: ## compile the contracts
	cd contracts && $(FORGE) build

deploy: t1-build ## deploy on $NETWORK, write deployments/$NETWORK.json and abi/ (fuji: FORCE=1 to overwrite)
	FORCE=$(FORCE) $(PYTHON) contracts/script/deploy.py

abi: t1-build ## export the ABIs to abi/
	$(PYTHON) contracts/script/deploy.py --abi-only

fund-roles: ## fuji: give each role at least AMOUNT test AVAX from the deployer (default 0.01)
	$(PYTHON) contracts/script/fund_roles.py --amount $(or $(AMOUNT),0.01)

test-t1: ## contract tests, plus the deployment check when a local deployment exists
	cd contracts && $(FORGE) test
	$(PYTHON) -m pytest backend/tests/test_t1_deployment.py -q
