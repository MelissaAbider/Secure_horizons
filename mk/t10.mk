# T10 · Sealed list: Safe, teller-window module, Merkle root (docs/tasks/T10.md). Included by the root Makefile.
# NETWORK comes from .env or the command line. Needs deployments/$NETWORK.json (T1) for USDC and the lending markets.
PROTOCOLS ?= lend-avax

.PHONY: seal-deploy seal seal-show seal-demo test-t10

seal-deploy: t1-build ## T10: Safe (owners, threshold) + SealedListModule, module enabled by the owners (FORCE=1 to redeploy)
	FORCE=$(FORCE) $(PYTHON) -m sealed.deploy

seal: t1-build ## T10: the owners sign the root of the list for PROTOCOLS (default lend-avax, e.g. lend-avax,lend-eth)
	$(PYTHON) -m sealed.seal --protocols $(PROTOCOLS)

seal-show: ## T10: print the sealed list and check it rebuilds the root stored on-chain
	$(PYTHON) -m sealed.seal --show

seal-demo: t1-build ## T10: agent proposals inside and outside the list, refusals replayed on-chain (NO_FORCE=1 to skip)
	$(PYTHON) -m sealed.demo $(if $(NO_FORCE),--no-force,)

test-t10: ## T10 tests: module (Foundry, real Safe 1.4.1) + list and end-to-end on anvil (NETWORK=local, make deploy)
	cd contracts && $(FORGE) test --match-path test/SealedListModule.t.sol
	$(PYTHON) -m pytest backend/tests/test_t10_*.py -q
