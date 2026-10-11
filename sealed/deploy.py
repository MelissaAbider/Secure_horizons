"""Deploys the T10 Safe and its teller-window module on $NETWORK, then writes sealed/deployments/<network>.json.

python -m sealed.deploy            (make seal-deploy; FORCE=1 to replace an existing deployment)

1. Safe v1.4.1: the canonical contracts on fuji, compiled from contracts/lib on a fresh anvil;
2. a Safe proxy owned by the asset manager (SAFE_OWNER_PKS, one key for now), threshold SAFE_THRESHOLD (default 1);
3. SealedListModule(safe, operator), with an empty root: nothing passes yet;
4. a Safe transaction signed by the asset manager enables the module;
5. the deployer mints test USDC to the Safe.
The scenario contracts (USDC, lend-avax, lend-eth) come from deployments/<network>.json (T1).
"""
from __future__ import annotations

import os
import sys
import time

from backend import chain, settings
from sealed import safe as S

SAFE_USDC = 1_000_000 * 10**6
OPERATOR_MIN_WEI = 5 * 10**16  # fuji: the operator pays gas for module.execute
OPERATOR_TOP_UP_WEI = 2 * 10**17


def link(tx_hash: str) -> str:
    return chain.explorer_tx(tx_hash) if settings.NETWORK == "fuji" else tx_hash


def fund_operator(operator, relayer) -> None:
    """fuji: the deployer tops the operator up to 0.2 test AVAX when it falls under 0.05 (anvil accounts are funded)."""
    w3 = chain.w3()
    if settings.NETWORK == "local" or w3.eth.get_balance(operator.address) >= OPERATOR_MIN_WEI:
        return
    tx = {"to": operator.address, "value": OPERATOR_TOP_UP_WEI, "gas": 21_000, "gasPrice": w3.eth.gas_price,
          "nonce": w3.eth.get_transaction_count(relayer.address, "pending"), "chainId": settings.CHAIN_ID}
    tx_hash = w3.eth.send_raw_transaction(relayer.sign_transaction(tx).raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"  operator topped up with {OPERATOR_TOP_UP_WEI / 10**18} test AVAX: {link('0x' + bytes(tx_hash).hex())}")


def already_deployed() -> bool:
    try:
        state = S.load_state()
    except RuntimeError:
        return False
    return len(chain.w3().eth.get_code(state["safe"])) > 0


def main() -> int:
    if already_deployed() and os.environ.get("FORCE") != "1":
        state = S.load_state()
        print(f"already deployed on {settings.NETWORK}: Safe {state['safe']}, module {state['module']} (FORCE=1 to redeploy)")
        return 0
    dep = chain.load_deployment()
    relayer = chain.account("deployer")
    owners = S.owner_accounts()
    operator = S.operator_account()
    print(f"T10 on {settings.NETWORK}: {S.front_door(S.threshold(), len(owners))}, operator {operator.address}")
    fund_operator(operator, relayer)

    singleton, factory = S.safe_singleton_and_factory(relayer)
    safe_address, tx_safe = S.create_safe([a.address for a in owners], S.threshold(), singleton, factory,
                                          int(time.time()), relayer)
    print(f"  Safe {safe_address}: {link(tx_safe)}")

    module_address, tx_module = S.deploy("SealedListModule", [safe_address, operator.address], relayer)
    print(f"  SealedListModule {module_address}: {link(tx_module)}")

    module = S.contract("SealedListModule", module_address)
    safe = S.contract("SafeL2", safe_address)
    data = safe.encode_abi("enableModule", args=[module_address])
    enabled = S.exec_safe_tx(safe_address, safe_address, data, owners[: S.threshold()], relayer)
    assert safe.functions.isModuleEnabled(module_address).call(), "module not enabled"
    print(f"  module enabled, signed by {', '.join(enabled['signers'])}: {link(enabled['tx_hash'])}")

    funded = chain.send(chain.token("USDC").functions.mint(safe_address, SAFE_USDC), relayer)
    print(f"  {SAFE_USDC // 10**6:,} test USDC minted to the Safe: {link(funded['tx_hash'])}")

    path = S.save_state({
        "network": settings.NETWORK,
        "chain_id": settings.CHAIN_ID,
        "explorer": settings.EXPLORER_URL,
        "deployed_at_block": chain.w3().eth.block_number,
        "safe": safe_address,
        "safe_version": safe.functions.VERSION().call(),
        "safe_singleton": singleton,
        "safe_factory": factory,
        "owners": [a.address for a in owners],
        "threshold": S.threshold(),
        "module": module_address,
        "operator": operator.address,
        "root": "0x" + module.functions.root().call().hex(),
        "txs": {"create_safe": tx_safe, "deploy_module": tx_module, "enable_module": enabled["tx_hash"],
                "mint_usdc": funded["tx_hash"]},
        "sealed": None,
        "assets": {"USDC": dep["assets"]["USDC"]},
    })
    print(f"wrote {path.relative_to(S.ROOT)}. Next: make seal PROTOCOLS=lend-avax")
    return 0


if __name__ == "__main__":
    sys.exit(main())
