"""T2 normal-traffic planner (TASKS.md T2, tests T2-10 and T2-11). Pure, no chain."""
import random

from scenario.common import DECIMALS, DEPLOYMENTS, LENDING_ASSETS, units
from scenario.normal import BORROWER, LENDER, MarketView, apply_action, plan_next_action
from scenario.params import normal_params
from scenario.seed import SEED_TARGET


def initial_view() -> dict:
    """The reference state of TASKS.md 2.2, as read by scenario.normal.read_view() right after the seed."""
    t = SEED_TARGET
    view = {"markets": {}, "positions": {}, "debts": {}, "ltv_bps": {"USDC": 8000, "WETH": 8000, "rsETH": 7500},
            "prices_e8": dict(t["prices_e8"]), "collateral": {dep: {s: 0 for s in DECIMALS} for dep in DEPLOYMENTS},
            "balances": {LENDER: {"WETH": units(500, "WETH"), "USDC": units(1_000_000, "USDC")},
                         BORROWER: {"WETH": units(500, "WETH"), "USDC": 0}}}
    for dep in DEPLOYMENTS:
        for sym in LENDING_ASSETS:
            supplied = units(t["lender_supply"][dep][sym] + t["vault_supply"][dep][sym], sym)
            borrowed = units(t["borrows"][dep][sym], sym)
            view["markets"][f"{dep}:{sym}"] = MarketView(supplied, borrowed, supplied - borrowed)
            view["positions"][f"{dep}:{sym}"] = units(t["lender_supply"][dep][sym], sym)
            view["debts"][f"{dep}:{sym}"] = 0
    return view


def test_guards_hold_over_2000_steps():
    p = normal_params(minutes=0, seed=7, ticks=2000)
    rng, view, done = random.Random(7), initial_view(), 0
    for tick in range(p.ticks):
        a = plan_next_action(view, rng, p, tick)
        if a is None:
            continue
        assert a.kind in ("supply", "withdraw", "borrow", "repay", "large_deposit", "bridge_deposit")
        if a.kind in ("supply", "withdraw", "borrow", "repay"):
            assert a.amount <= view["markets"][f"{a.deployment_id}:{a.asset}"].available // 10
            assert a.actor == (LENDER if a.kind in ("supply", "withdraw") else BORROWER)
        view = apply_action(view, a)
        done += 1
        for m in view["markets"].values():
            assert m.borrowed * 10_000 <= 8_500 * m.supplied
            assert m.available == m.supplied - m.borrowed >= 0
        assert all(v >= 0 for v in view["positions"].values()) and all(v >= 0 for v in view["debts"].values())
        assert all(n >= 0 for b in view["balances"].values() for n in b.values())
    assert done > 1000  # the guards leave room for real traffic


def test_scheduled_actions():
    p = normal_params(minutes=0, seed=1, ticks=50)
    rng, view = random.Random(1), initial_view()
    first = plan_next_action(view, rng, p, 0)
    assert first.kind == "bridge_deposit"
    large = plan_next_action(apply_action(view, first), rng, p, 20)
    assert (large.kind, large.deployment_id, large.asset, large.amount) == ("large_deposit", "lend-eth", "WETH", units(300, "WETH"))
