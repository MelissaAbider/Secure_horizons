"""Normal traffic: random but harmless activity, used to measure false positives (TASKS.md T2 step 5). Owner: T2.

python -m scenario.normal --minutes M [--seed N] [--json] [--run-id RUN-...] [--tick-s X] [--ticks N]
Blocking: returns after the last tick and always writes a RunRecord labelled "normal".
Never touches the vault, the oracle, the freeze/pause switches or forgedRelease; bots[1] never borrows.
"""
from __future__ import annotations

import argparse
import copy
import random
import sys
import time
from dataclasses import dataclass
from typing import Literal, Optional

from backend import chain, settings
from backend.models import RunRecord
from scenario.common import (
    DECIMALS, DEPLOYMENTS, LENDING_ASSETS, Emitter, PreflightError, asset_address, ensure_allowance, human, new_run_id, preflight,
    reserve, run_main, treasury_supplied, tx, units, write_run_record,
)
from scenario.params import NormalParams, normal_params

MAX_UTILIZATION_BPS = 8_500
MAX_SHARE_OF_AVAILABLE_BPS = 1_000  # one action moves at most 10 % of the available liquidity
LENDER, BORROWER = 0, 2  # bots[0] supplies and withdraws, bots[2] borrows and repays
BRIDGE_DEPOSIT = 200  # WETH, tick 0: 150 rsETH collateral on lend-eth, 50 on lend-avax
RSETH_COLLATERAL = {"lend-eth": 150, "lend-avax": 50}
LARGE_DEPOSIT = 300  # WETH on lend-eth, at tick int(0.4 * ticks)
KINDS = ("supply", "withdraw", "borrow", "repay")
WEIGHTS = (30, 25, 25, 20)


@dataclass
class MarketView:
    supplied: int
    borrowed: int
    available: int


@dataclass
class NormalAction:
    kind: Literal["supply", "withdraw", "borrow", "repay", "large_deposit", "bridge_deposit"]
    actor: int
    deployment_id: str
    asset: str
    amount: int  # base units


# view = {"markets": {"lend-eth:WETH": MarketView}, "positions": {"lend-eth:WETH": lender supplied},
#         "debts": {"lend-eth:WETH": borrower debt}, "balances": {0: {"WETH": n, "USDC": n}, 2: {...}},
#         "collateral": {"lend-eth": {"rsETH": n, ...}}, "prices_e8": {sym: p}, "ltv_bps": {sym: bps}}


def _value_e8(view: dict, sym: str, amount: int) -> int:
    return amount * view["prices_e8"][sym] // 10 ** DECIMALS[sym]


def borrow_room_e8(view: dict, dep: str) -> int:
    """Remaining borrow capacity of bots[2] on a deployment, in USD with 8 decimals (same formula as MiniLend)."""
    capacity = sum(_value_e8(view, sym, n) * view["ltv_bps"][sym] // 10_000 for sym, n in view["collateral"][dep].items())
    debt = sum(_value_e8(view, sym, view["debts"][f"{dep}:{sym}"]) for sym in LENDING_ASSETS)
    return max(0, capacity - debt)


def large_deposit_tick(ticks: int) -> Optional[int]:
    return max(1, int(0.4 * ticks)) if ticks >= 3 else None


def plan_next_action(view: dict, rng: random.Random, p: NormalParams, tick: int) -> Optional[NormalAction]:
    """Pure: the next harmless action, or None when no safe action fits. Same rng draws on every tick."""
    if tick == 0:
        amount = units(BRIDGE_DEPOSIT, "WETH")
        return NormalAction("bridge_deposit", BORROWER, "lend-eth", "WETH", amount) \
            if view["balances"][BORROWER]["WETH"] >= amount else None
    large_tick = large_deposit_tick(p.ticks)
    if tick == large_tick:
        amount = units(LARGE_DEPOSIT, "WETH")
        return NormalAction("large_deposit", LENDER, "lend-eth", "WETH", amount) \
            if view["balances"][LENDER]["WETH"] >= amount else None

    kind = rng.choices(KINDS, weights=WEIGHTS)[0]
    dep, sym = rng.choice(DEPLOYMENTS), rng.choice(LENDING_ASSETS)
    drawn = rng.randint(5, 40) if sym == "WETH" else rng.randint(10, 100) * 1_000
    key, one = f"{dep}:{sym}", 10 ** DECIMALS[sym]
    m = view["markets"][key]
    caps = [m.available * MAX_SHARE_OF_AVAILABLE_BPS // 10_000]
    if kind == "supply":
        reserved = units(LARGE_DEPOSIT, "WETH") if sym == "WETH" and large_tick is not None and tick < large_tick else 0
        caps.append(view["balances"][LENDER][sym] - reserved)
    elif kind == "withdraw":
        min_supplied = -(-m.borrowed * 10_000 // MAX_UTILIZATION_BPS)  # ceil
        caps += [view["positions"][key], m.supplied - min_supplied]
    elif kind == "borrow":
        caps += [m.supplied * MAX_UTILIZATION_BPS // 10_000 - m.borrowed,
                 borrow_room_e8(view, dep) * 8 // 10 * one // view["prices_e8"][sym]]
    else:
        caps += [view["debts"][key], view["balances"][BORROWER][sym]]
    amount = min(drawn, min(caps) // one)
    if amount <= 0:
        return None
    actor = LENDER if kind in ("supply", "withdraw") else BORROWER
    return NormalAction(kind, actor, dep, sym, amount * one)


def apply_action(view: dict, a: NormalAction) -> dict:
    """Pure: the view after the action (used by the planner tests; the live run re-reads the chain)."""
    v = copy.deepcopy(view)
    if a.kind == "bridge_deposit":
        v["balances"][BORROWER]["WETH"] -= a.amount
        for dep, n in RSETH_COLLATERAL.items():
            v["collateral"][dep]["rsETH"] = v["collateral"][dep].get("rsETH", 0) + units(n, "rsETH")
        return v
    key = f"{a.deployment_id}:{a.asset}"
    m = v["markets"][key]
    sign = 1 if a.kind in ("supply", "large_deposit", "repay") else -1
    m.available += sign * a.amount
    if a.kind in ("supply", "large_deposit", "withdraw"):
        m.supplied += sign * a.amount
        v["positions"][key] += sign * a.amount
        v["balances"][LENDER][a.asset] -= sign * a.amount
    else:
        m.borrowed -= sign * a.amount
        v["debts"][key] -= sign * a.amount
        v["balances"][BORROWER][a.asset] += -sign * a.amount
    return v


def read_view() -> dict:
    bots = chain.bot_accounts()
    lender, borrower = bots[LENDER].address, bots[BORROWER].address
    view: dict = {"markets": {}, "positions": {}, "debts": {}, "collateral": {}, "ltv_bps": {},
                  "balances": {LENDER: {}, BORROWER: {}},
                  "prices_e8": {s: chain.oracle().functions.getPriceE8(asset_address(s)).call() for s in DECIMALS}}
    for dep in DEPLOYMENTS:
        market = chain.lending(dep)
        view["collateral"][dep] = {}
        for sym in DECIMALS:
            r = reserve(dep, sym)
            view["ltv_bps"][sym] = r["ltv_bps"]
            view["collateral"][dep][sym] = market.functions.getUserCollateral(borrower, asset_address(sym)).call()
            if sym in LENDING_ASSETS:
                key = f"{dep}:{sym}"
                view["markets"][key] = MarketView(r["total_supplied"], r["total_borrowed"], r["available_liquidity"])
                view["positions"][key] = market.functions.getUserSupplied(lender, asset_address(sym)).call()
                view["debts"][key] = market.functions.getUserBorrowed(borrower, asset_address(sym)).call()
    for who, address in ((LENDER, lender), (BORROWER, borrower)):
        for sym in LENDING_ASSETS:
            view["balances"][who][sym] = chain.token(sym).functions.balanceOf(address).call()
    return view


def execute(a: NormalAction, emit: Emitter) -> None:
    bot = chain.bot_accounts()[a.actor]
    if a.kind == "bridge_deposit":
        bridge = chain.bridge()
        ensure_allowance(bot, "WETH", bridge.address, emit)
        tx(bridge.functions.deposit(a.amount), bot, "bridge_deposit", emit, f"bots[2] bridges {human(a.amount, 'WETH')} (backed)")
        for dep, n in RSETH_COLLATERAL.items():
            market = chain.lending(dep)
            ensure_allowance(bot, "rsETH", market.address, emit)
            tx(market.functions.depositCollateral(asset_address("rsETH"), units(n, "rsETH")), bot, "collateral", emit,
               f"bots[2] posts {n} rsETH on {dep}")
        return
    market, asset = chain.lending(a.deployment_id), asset_address(a.asset)
    msg = f"bots[{a.actor}] {a.kind.replace('_', ' ')} {human(a.amount, a.asset)} on {a.deployment_id}"
    if a.kind in ("supply", "large_deposit", "repay"):
        ensure_allowance(bot, a.asset, market.address, emit)
    if a.kind in ("supply", "large_deposit"):
        fn = market.functions.supply(asset, a.amount, bot.address)
    elif a.kind == "withdraw":
        fn = market.functions.withdraw(asset, a.amount, bot.address)
    elif a.kind == "borrow":
        fn = market.functions.borrow(asset, a.amount)
    else:
        fn = market.functions.repay(asset, a.amount)
    tx(fn, bot, a.kind, emit, msg)


def run_normal(p: NormalParams, run_id: str, emit: Emitter) -> RunRecord:
    preflight((), (LENDER, BORROWER))
    if any(reserve(dep, "rsETH")["frozen"] for dep in DEPLOYMENTS):
        raise PreflightError("rsETH is frozen (an attack was played): run make reset")
    w3 = chain.w3()
    start_block = last_block = w3.eth.block_number
    at_start = treasury_supplied()
    rng = random.Random(p.seed)
    emit("start", f"{p.ticks} ticks every {p.tick_s}s, seed {p.seed}", status="info", block=start_block)
    try:
        for tick in range(p.ticks):
            action = plan_next_action(read_view(), rng, p, tick)
            if action is None:
                emit("skip", f"tick {tick}: no safe action", status="info")
            else:
                execute(action, emit)
            last_block = w3.eth.block_number
            time.sleep(p.tick_s)
    finally:
        try:
            last_block = w3.eth.block_number
        except Exception:  # RPC gone: keep the last block read
            pass
        rec = RunRecord(run_id=run_id, network=settings.NETWORK, label="normal", variant="default", seed=p.seed,
                        params=p.as_params(), start_block=start_block, end_block=last_block, attack_start_block=None,
                        phase_blocks={}, treasury_supplied_at_start=at_start)
        path = write_run_record(rec)
        emit("done", str(path), block=last_block)
    return rec


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scenario.normal", description="Harmless background traffic.")
    parser.add_argument("--minutes", type=float, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--tick-s", type=float)
    parser.add_argument("--ticks", type=int)
    args = parser.parse_args(argv)
    p = normal_params(args.minutes, args.seed, ticks=args.ticks, tick_s=args.tick_s)
    emit = Emitter(args.run_id or new_run_id("normal", args.seed), args.json)
    try:
        return run_main(lambda: run_normal(p, emit.run_id, emit), emit)
    except KeyboardInterrupt:  # the RunRecord is already written by run_normal's finally
        return 130


if __name__ == "__main__":
    sys.exit(main())
