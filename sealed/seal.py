"""Seal: the asset manager ticks protocols, the platform builds the list, the manager signs its root (T10).

python -m sealed.seal --protocols lend-avax[,lend-eth]   (make seal PROTOCOLS=...)
python -m sealed.seal --show                             (make seal-show: print the list, check the on-chain root)

The root goes on-chain only through a Safe transaction signed by the asset manager: the operator, the module
and the agent cannot change it. The list is published in sealed/deployments/<network>.json: it is not secret,
anyone can rebuild the root from it (python -m sealed.tree sealed/deployments/<network>.json).
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, Sequence

from backend import chain, settings
from sealed import safe as S
from sealed.deploy import link
from sealed.tree import MerkleTree, Operation, check_published, protocol_operations


def operations(protocols: Sequence[str], safe_address: str) -> list[Operation]:
    dep = chain.load_deployment()
    markets = {x["id"]: x["address"] for x in dep["lending"]}
    unknown = [p for p in protocols if p not in markets]
    if unknown:
        raise SystemExit(f"unknown protocol(s) {unknown}; known: {sorted(markets)}")
    ops = []
    for p in protocols:
        ops += protocol_operations(p, markets[p], dep["assets"]["USDC"], safe_address)
    return ops


def seal(protocols: Sequence[str]) -> dict[str, Any]:
    state = S.load_state()
    ops = operations(protocols, state["safe"])
    tree = MerkleTree([op.leaf for op in ops])
    module = S.contract("SealedListModule", state["module"])
    data = module.encode_abi("setRoot", args=[tree.root])
    signed = S.exec_safe_tx(state["safe"], state["module"], data, S.owner_accounts()[: state["threshold"]],
                            chain.account("deployer"))
    on_chain = module.functions.root().call()
    assert on_chain == tree.root, "the module did not store the signed root"
    state["root"] = "0x" + tree.root.hex()
    state["sealed"] = {
        "protocols": list(protocols),
        "root": state["root"],
        "leaves": [op.to_json() for op in ops],
        "safe_tx_hash": signed["safe_tx_hash"],
        "signers": signed["signers"],
        "tx_hash": signed["tx_hash"],
        "block": signed["block_number"],
    }
    S.save_state(state)
    return state


def show(state: dict[str, Any]) -> int:
    sealed = state.get("sealed")
    if not sealed:
        print("nothing sealed yet: make seal PROTOCOLS=lend-avax")
        return 1
    on_chain = "0x" + S.contract("SealedListModule", state["module"]).functions.root().call().hex()
    print(f"Sealed list on {state['network']} — Safe {state['safe']} ({S.front_door(state['threshold'], len(state['owners']))})")
    print(f"  ticked: {', '.join(sealed['protocols'])}")
    for x in sealed["leaves"]:
        args = ", ".join(a if a == "*" else _short(a) for a in x["args"])
        print(f"  {x['leaf'][:10]}…  {x['label']:<42} {x['signature'].split('(')[0]}({args})")
    print(f"  root (the seal)  {sealed['root']}")
    print(f"  signed SafeTx    {sealed['safe_tx_hash']} by {', '.join(_short(s) for s in sealed['signers'])}")
    print(f"  sealing tx       {link(sealed['tx_hash'])}")
    problem = check_published(sealed)
    match = on_chain == sealed["root"]
    print(f"  rebuilt from the published list: {'OK' if problem is None else problem}")
    print(f"  root stored by the module:       {'OK, same root' if match else 'MISMATCH ' + on_chain}")
    return 0 if problem is None and match else 1


def _short(value: str) -> str:
    return value[:6] + "…" + value[-4:] if isinstance(value, str) and value.startswith("0x") else str(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--protocols", default="lend-avax", help="comma separated lending deployment ids")
    parser.add_argument("--show", action="store_true", help="print the sealed list and check the on-chain root")
    args = parser.parse_args(argv)
    if args.show:
        return show(S.load_state())
    protocols = [p.strip() for p in args.protocols.split(",") if p.strip()]
    state = seal(protocols)
    print(f"sealed {len(state['sealed']['leaves'])} operations on {settings.NETWORK}, "
          f"signed by {', '.join(state['sealed']['signers'])}")
    return show(state)


if __name__ == "__main__":
    sys.exit(main())
