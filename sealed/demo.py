"""T10 demo: the owners seal a list, the agent proposes, the platform and the Safe decide.

python -m sealed.demo [--no-force]     (make seal-demo)

1. the owners tick lend-avax: 3 operations, root signed by the threshold of owners;
2. the agent (no key) makes six proposals; inside the list they run, outside they are refused;
3. each refusal is replayed as a compromised platform would (--no-force skips it): the module refuses on-chain;
4. the owners tick lend-eth too (new root, new signatures) and the lend-eth deposit now runs;
5. the agent withdraws everything back to the Safe, so the shared markets end as they started.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, Sequence

from backend import chain, settings
from sealed import safe as S
from sealed import seal, teller
from sealed.agent_stub import describe, exits, proposals
from sealed.deploy import SAFE_USDC, fund_operator, link

TOP_UP_BELOW = 300_000 * 10**6


def _usdc(amount: int) -> str:
    return f"{amount / 10**6:,.0f} USDC"


def top_up(state: dict[str, Any]) -> None:
    fund_operator(S.operator_account(), chain.account("deployer"))
    usdc = chain.token("USDC")
    if usdc.functions.balanceOf(state["safe"]).call() < TOP_UP_BELOW:
        chain.send(usdc.functions.mint(state["safe"], SAFE_USDC), chain.account("deployer"))


def show_decision(p: dict[str, Any], record: dict[str, Any]) -> None:
    print(f"\n[{p['id']}] agent: {describe(p)}  (source: {p['source']}: {p['why']})")
    if record["verdict"] == "EXECUTED":
        print("     ACCEPTED: every call is in the sealed list, the module ran it from the Safe")
        for tx in record["txs"]:
            print(f"       {link(tx)}")
        return
    print(f"     REFUSED by the platform, no transaction: {record['detail']}")
    forced = record.get("on_chain")
    if forced:
        print(f"     forced through the module (compromised platform): {forced['error']}, "
              f"{'reverted on-chain, no effect' if forced['reverted'] else 'NOT REVERTED'}")
        if forced.get("computedRoot"):
            print(f"       root recomputed by the module {forced['computedRoot']}")
            print(f"       seal kept by the module       {forced['sealedRoot']}")
        print(f"       {link(forced['tx_hash'])}")


def positions(state: dict[str, Any]) -> str:
    usdc = chain.load_deployment()["assets"]["USDC"]
    parts = [f"Safe {_usdc(chain.token('USDC').functions.balanceOf(state['safe']).call())}"]
    for dep_id in ("lend-avax", "lend-eth"):
        supplied = chain.lending(dep_id).functions.getUserSupplied(state["safe"], usdc).call()
        parts.append(f"{dep_id} {_usdc(supplied)}")
    return ", ".join(parts)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-force", action="store_true", help="do not replay refusals through the module")
    args = parser.parse_args(argv)
    force = not args.no_force

    state = S.load_state()
    top_up(state)
    print(f"== T10 sealed list demo on {settings.NETWORK}: Safe {state['safe']} "
          f"({state['threshold']} of {len(state['owners'])} owners), operator {state['operator']}")
    print("\n== 1. Front door: the owners tick lend-avax and sign the root")
    state = seal.seal(["lend-avax"])
    seal.show(state)
    print(f"\n   start: {positions(state)}")

    print("\n== 2. The agent proposes (it holds no key); the platform checks; the module executes")
    stub = proposals()
    counts = {"EXECUTED": 0, "REFUSED": 0}
    for p in stub:
        record = teller.decide(p, state, force=force)
        counts[record["verdict"]] += 1
        show_decision(p, record)

    print("\n== 3. Front door again: the owners tick lend-eth too, new root, new signatures")
    state = seal.seal(["lend-avax", "lend-eth"])
    print(f"   new root {state['root']} signed by {len(state['sealed']['signers'])} owners: "
          f"{link(state['sealed']['tx_hash'])}")
    retry = next(p for p in stub if p.get("protocol") == "lend-eth")
    record = teller.decide({**retry, "id": retry["id"] + "'"}, state, force=force)
    counts[record["verdict"]] += 1
    show_decision({**retry, "id": retry["id"] + "'"}, record)

    print("\n== 4. Exit: everything back to the Safe (sealed withdraw, amount = all)")
    for p in exits(["lend-avax", "lend-eth"]):
        record = teller.decide(p, state, force=force)
        counts[record["verdict"]] += 1
        show_decision(p, record)

    print(f"\n== End: {positions(state)}")
    print(f"   {counts['EXECUTED']} proposals executed, {counts['REFUSED']} refused; "
          f"decisions in {(settings.runtime_dir() / 'sealed_decisions.jsonl').relative_to(S.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
