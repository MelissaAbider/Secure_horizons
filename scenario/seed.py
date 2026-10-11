"""Seed: put a freshly deployed chain into the reference state of TASKS.md 2.2 (T2 step 3). Owner: T2.

python -m scenario.seed [--json] [--run-id RUN-...]
Idempotent: on an already seeded chain it sends nothing. Runs under the maintenance flag so the
monitoring engine does not mistake the setup borrows for an attack.
"""
from __future__ import annotations

import argparse
import sys
from contextlib import nullcontext
from typing import Literal, Optional

from backend import chain
from scenario.common import (
    DEPLOYMENTS, Emitter, PreflightError, ScenarioError, asset_address, maintenance, new_run_id,
    preflight, reserve, roles, run_main, treasury_supplied, tx, units,
)

# Human units. bots[0] = lender, bots[1] = historical borrower, bots[2] = active borrower of normal traffic.
SEED_TARGET = {
    "mints": [(0, "WETH", 3_250), (0, "USDC", 5_300_000), (1, "WETH", 1_200), (1, "USDC", 7_500_000), (2, "WETH", 500),
              ("vault", "WETH", 250), ("vault", "USDC", 700_000)],
    "lender_supply": {"lend-eth": {"WETH": 1_850, "USDC": 2_600_000}, "lend-avax": {"WETH": 900, "USDC": 1_700_000}},
    "bridge_deposit": 1_200,
    "rseth_collateral": {"lend-eth": 900, "lend-avax": 300},
    "usdc_collateral": {"lend-eth": 4_500_000, "lend-avax": 3_000_000},
    "borrows": {"lend-eth": {"WETH": 1_200, "USDC": 1_800_000}, "lend-avax": {"WETH": 550, "USDC": 1_100_000}},
    "vault_supply": {"lend-eth": {"WETH": 150, "USDC": 400_000}, "lend-avax": {"WETH": 100, "USDC": 300_000}},
    "prices_e8": {"USDC": 10**8, "WETH": 2_500 * 10**8, "rsETH": 2_500 * 10**8},
}


def expected_reserves() -> dict[tuple[str, str], tuple[int, int, int]]:
    """(deployment, asset) -> (total_supplied, total_borrowed, total_collateral) in base units after the seed."""
    t = SEED_TARGET
    out = {}
    for dep in DEPLOYMENTS:
        for sym in ("USDC", "WETH"):
            supplied = t["lender_supply"][dep][sym] + t["vault_supply"][dep][sym]
            collateral = t["usdc_collateral"][dep] if sym == "USDC" else 0
            out[(dep, sym)] = (units(supplied, sym), units(t["borrows"][dep][sym], sym), units(collateral, sym))
        out[(dep, "rsETH")] = (0, 0, units(t["rseth_collateral"][dep], "rsETH"))
    return out


def allowance_pairs() -> list[tuple[int, str, str]]:
    """(bot index, token, spender) for every approval used by the seed and by normal traffic."""
    d = chain.load_deployment()
    markets = [m["address"] for m in d["lending"]]
    bridge = d["contracts"]["MockBridge"]
    pairs = [(0, sym, m) for sym in ("USDC", "WETH") for m in markets]
    for bot in (1, 2):
        pairs += [(bot, "WETH", bridge)] + [(bot, sym, m) for sym in ("USDC", "WETH", "rsETH") for m in markets]
    return pairs


def detect_seed_state() -> Literal["empty", "seeded", "partial"]:
    rseth_supply = chain.token("rsETH").functions.totalSupply().call()
    actual = {(dep, sym): reserve(dep, sym) for dep in DEPLOYMENTS for sym in ("USDC", "WETH", "rsETH")}
    if rseth_supply == 0 and all(r["total_supplied"] == 0 and r["total_collateral"] == 0 for r in actual.values()):
        return "empty"
    t = SEED_TARGET
    checks = [
        rseth_supply == units(t["bridge_deposit"], "rsETH"),
        chain.bridge().functions.totalBacking().call() == units(t["bridge_deposit"], "WETH"),
        all((actual[k]["total_supplied"], actual[k]["total_borrowed"], actual[k]["total_collateral"]) == v
            for k, v in expected_reserves().items()),
        treasury_supplied() == {f"{dep}:{sym}": str(units(t["vault_supply"][dep][sym], sym))
                                for dep in DEPLOYMENTS for sym in ("USDC", "WETH")},
        chain.vault().functions.guardian().call() == roles()["guardian"],
        all(chain.oracle().functions.getPriceE8(asset_address(sym)).call() == p for sym, p in t["prices_e8"].items()),
    ]
    return "seeded" if all(checks) else "partial"


def run_seed(emit: Optional[Emitter] = None, manage_maintenance: bool = True) -> dict:
    """Seed an empty deployment. reset passes manage_maintenance=False because it already holds the flag."""
    emit = emit or Emitter(new_run_id("seed", 0), json_mode=False)
    preflight(("deployer", "owner"), (0, 1, 2))
    state = detect_seed_state()
    if state == "seeded":
        emit("already_seeded", "chain already in the reference state, nothing sent", status="info")
        return {"status": "already_seeded"}
    if state == "partial":
        raise PreflightError("partial seed state, run make reset")

    count = 0

    def send(fn, sender, step, msg):
        nonlocal count
        receipt = tx(fn, sender, step, emit, msg)
        count += 1
        return receipt

    t = SEED_TARGET
    with maintenance(emit) if manage_maintenance else nullcontext():
        deployer, owner, bots = chain.account("deployer"), chain.account("owner"), chain.bot_accounts()
        vault = chain.vault()
        for who, sym, amount in t["mints"]:
            to = vault.address if who == "vault" else bots[who].address
            send(chain.token(sym).functions.mint(to, units(amount, sym)), deployer, "mint",
                 f"{amount:,} {sym} to {'vault' if who == 'vault' else f'bots[{who}]'}")
        for bot, sym, spender in allowance_pairs():
            token = chain.token(sym)
            if token.functions.allowance(bots[bot].address, spender).call() < 2**255:
                send(token.functions.approve(spender, 2**256 - 1), bots[bot], "approve",
                     f"bots[{bot}] approves {sym} for {spender[:10]}")
        for dep in DEPLOYMENTS:
            market = chain.lending(dep)
            for sym, amount in t["lender_supply"][dep].items():
                send(market.functions.supply(asset_address(sym), units(amount, sym), bots[0].address), bots[0],
                     "supply", f"bots[0] supplies {amount:,} {sym} on {dep}")
        send(chain.bridge().functions.deposit(units(t["bridge_deposit"], "WETH")), bots[1], "bridge_deposit",
             f"bots[1] bridges {t['bridge_deposit']:,} WETH into rsETH (fully backed)")
        for dep in DEPLOYMENTS:
            send(chain.lending(dep).functions.depositCollateral(asset_address("rsETH"), units(t["rseth_collateral"][dep], "rsETH")),
                 bots[1], "collateral", f"bots[1] posts {t['rseth_collateral'][dep]:,} rsETH on {dep}")
        for dep in DEPLOYMENTS:  # USDC collateral before any borrow (TASKS.md T2 3.2)
            send(chain.lending(dep).functions.depositCollateral(asset_address("USDC"), units(t["usdc_collateral"][dep], "USDC")),
                 bots[1], "collateral", f"bots[1] posts {t['usdc_collateral'][dep]:,} USDC on {dep}")
        for dep in DEPLOYMENTS:
            for sym, amount in t["borrows"][dep].items():
                send(chain.lending(dep).functions.borrow(asset_address(sym), units(amount, sym)), bots[1], "borrow",
                     f"bots[1] borrows {amount:,} {sym} on {dep}")
        for dep in DEPLOYMENTS:
            market_address = chain.lending(dep).address
            for sym, amount in t["vault_supply"][dep].items():
                send(vault.functions.supply(market_address, asset_address(sym), units(amount, sym)), owner,
                     "vault_supply", f"vault supplies {amount:,} {sym} on {dep}")
        if detect_seed_state() != "seeded":
            raise ScenarioError("seed finished but the chain does not match the reference state")
        end_block = chain.w3().eth.block_number
        emit("seeded", f"reference state in place ({count} transactions)", block=end_block)
    return {"status": "seeded", "txs": count, "end_block": end_block}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scenario.seed", description="Put the chain in the reference state.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    emit = Emitter(args.run_id or new_run_id("seed", 0), args.json)
    return run_main(lambda: run_seed(emit), emit)


if __name__ == "__main__":
    sys.exit(main())
