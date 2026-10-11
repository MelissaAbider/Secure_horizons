"""Attack: replay of the April 2026 rsETH incident on our test contracts (TASKS.md T2 step 4). Owner: T2.

python -m scenario.attack [--seed N] [--variant default|slow|usdc] [--json] [--run-id RUN-...]
                          [--interval-s X] [--warmup-s X] [--freeze-delay-s X] [--skip-seed-check]
1. the attacker mints rsETH with no backing, 2. posts it as collateral, 3. borrows the real asset in tranches until
the market is empty, while a lender tries to get out, 4. the protocol guardian freezes rsETH at the end.
Writes the ground truth (RunRecord) to data/runs/<run_id>.json.
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

from backend import chain, settings
from backend.models import RunRecord
from scenario.common import (
    Emitter, PreflightError, ScenarioError, asset_address, ensure_allowance, human, new_run_id, preflight, reserve,
    run_main, treasury_supplied, tx, units, write_run_record,
)
from scenario.params import VARIANTS, AttackParams, attack_params


def run_attack(p: AttackParams, run_id: str, emit: Emitter, skip_seed_check: bool = False) -> RunRecord:
    from scenario.seed import detect_seed_state

    preflight(("attacker", "protocol_guardian"), (0,))
    if not skip_seed_check and detect_seed_state() != "seeded":
        raise PreflightError("chain not in the reference state: run make reset (or make seed on a fresh deployment)")
    w3 = chain.w3()
    attacker, protocol_guardian, lender = chain.account("attacker"), chain.account("protocol_guardian"), chain.bot_accounts()[0]
    market, A = chain.lending(p.market), p.drain_asset
    asset, rseth = asset_address(A), asset_address("rsETH")
    start_block = w3.eth.block_number
    at_start = treasury_supplied()
    phases: dict[str, int] = {}

    def record(end_block: int) -> RunRecord:
        rec = RunRecord(run_id=run_id, network=settings.NETWORK, label="attack", variant=p.variant, seed=p.seed,
                        params=p.as_params(), start_block=start_block, end_block=end_block,
                        attack_start_block=phases.get("forged_mint"), phase_blocks=phases,
                        treasury_supplied_at_start=at_start)
        write_run_record(rec)
        return rec

    emit("start", f"variant {p.variant}, seed {p.seed}, {p.forged_amount:,} rsETH, {p.chunk:,} {A} per borrow "
                  f"every {p.interval_s}s on {p.market}", status="info", block=start_block)
    time.sleep(p.warmup_s)

    r = tx(chain.bridge().functions.forgedRelease(attacker.address, units(p.forged_amount, "rsETH")), attacker,
           "forged_mint", emit, f"{p.forged_amount:,} rsETH minted with no backing")
    phases["forged_mint"] = r["block_number"]
    emit("backing", f"rsETH backing now {chain.bridge().functions.backingRatioBps().call()} bps", status="info")

    time.sleep(p.gap_s)
    ensure_allowance(attacker, "rsETH", market.address, emit)
    r = tx(market.functions.depositCollateral(rseth, units(p.forged_amount, "rsETH")), attacker, "collateral_deposit",
           emit, f"{p.forged_amount:,} unbacked rsETH posted as collateral on {p.market}")
    phases["collateral_deposit"] = r["block_number"]

    time.sleep(p.gap_s / 2)
    last_block = r["block_number"]
    borrows = 0
    for i in range(1, p.max_chunks + 1):
        available = reserve(p.market, A)["available_liquidity"]
        if available == 0:
            phases.setdefault("liquidity_zero", last_block)
            break
        amount = min(units(p.chunk, A), available)
        try:
            r = tx(market.functions.borrow(asset, amount), attacker, "borrow", emit,
                   f"borrow {i}: {human(amount, A)}", expect_revert="insufficient liquidity")
        except ScenarioError as exc:
            if "insufficient collateral" in str(exc):
                record(w3.eth.block_number)
            raise
        if r is not None:  # None: a stale read raced a withdrawal, re-read next iteration
            borrows += 1
            last_block = r["block_number"]
            phases.setdefault("first_borrow", last_block)
            if reserve(p.market, A)["available_liquidity"] == 0:
                phases["liquidity_zero"] = last_block
                emit("liquidity_zero", f"{p.market} {A} fully drained after {borrows} borrows", status="info", block=last_block)
                break
        if i in p.withdraw_after:
            r = tx(market.functions.withdraw(asset, units(p.bot_withdraw_amount, A), lender.address), lender,
                   "bot_withdraw", emit, f"lender withdraws {p.bot_withdraw_amount:,} {A}",
                   expect_revert="insufficient liquidity")
            if r is not None:
                last_block = r["block_number"]
        time.sleep(p.interval_s)

    tx(market.functions.withdraw(asset, units(p.bot_withdraw_amount, A), lender.address), lender, "bot_withdraw", emit,
       f"lender tries to withdraw {p.bot_withdraw_amount:,} {A} (stuck supplier)", expect_revert="insufficient liquidity")

    time.sleep(p.freeze_delay_s)
    r = tx(market.functions.setReserveFrozen(rseth, True), protocol_guardian, "protocol_freeze", emit,
           f"protocol guardian freezes rsETH on {p.market}")
    phases["protocol_freeze"] = r["block_number"]

    time.sleep(p.cooldown_s)
    rec = record(w3.eth.block_number)
    emit("done", str(settings.DATA_DIR / "runs" / f"{run_id}.json"), block=rec.end_block)
    return rec


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scenario.attack", description="Replay the rsETH attack.")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--variant", default="default", choices=VARIANTS)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--interval-s", type=float)
    parser.add_argument("--warmup-s", type=float)
    parser.add_argument("--freeze-delay-s", type=float)
    parser.add_argument("--skip-seed-check", action="store_true")
    args = parser.parse_args(argv)
    p = attack_params(args.variant, args.seed).with_timing(args.interval_s, args.warmup_s, args.freeze_delay_s)
    emit = Emitter(args.run_id or new_run_id("attack", args.seed), args.json)
    return run_main(lambda: run_attack(p, emit.run_id, emit, args.skip_seed_check), emit)


if __name__ == "__main__":
    sys.exit(main())
