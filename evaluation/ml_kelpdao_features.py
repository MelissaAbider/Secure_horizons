"""Scenario-specific features for the KelpDAO pattern on an Aave-like market.

Per sliding window over the decoded Aave event stream (data/external/kelpdao/aave_events_*.jsonl), we compute,
SEPARATELY for the collateral asset (rsETH) and the borrowable asset (WETH), the quantities that encode the causal chain:
  collateral inflow  -> borrow against it -> liquidity exits (withdrawals / rate spike) -> concentration of actors.
Amounts are log10 of base units; rates come from ReserveDataUpdated (ray, 1e27) and are expressed as APR percentages.

Labels: 1 if the window end is within [attack_block, attack_block + horizon]; 0 otherwise. Windows ending before the attack
block in the attack file are negatives (pre-attack normal), which is the hardest and most honest negative class.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "external" / "kelpdao"
OUT = ROOT / "data" / "external" / "ml" / "kelpdao"
COLLATERAL, BORROWABLE = "rsETH", "WETH"
RAY = 10**27


def log10(x: float) -> float:
    return math.log10(x) if x > 0 else 0.0


def load_events(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def per_block(events: list[dict]) -> dict[int, dict]:
    blocks: dict[int, dict] = defaultdict(lambda: {
        "coll_in": 0, "coll_in_n": 0, "coll_actors": set(), "coll_enabled_n": 0,
        "bor_borrow": 0, "bor_borrow_n": 0, "bor_borrow_actors": defaultdict(int),
        "bor_withdraw": 0, "bor_withdraw_n": 0, "bor_withdraw_actors": set(),
        "bor_supply": 0, "bor_supply_n": 0, "bor_repay": 0,
        "bor_rate": None, "bor_liq_rate": None, "n_events": 0, "n_liq": 0, "ts": 0,
    })
    for e in events:
        b = blocks[e["block"]]
        b["n_events"] += 1
        b["ts"] = e["timestamp"]
        kind, asset = e["event"], e["asset"]
        amt = int(e["amount"]) if e.get("amount") else 0
        actor = e.get("user") or e.get("on_behalf_of")
        if asset == COLLATERAL:
            if kind == "supply":
                b["coll_in"] += amt
                b["coll_in_n"] += 1
                if actor:
                    b["coll_actors"].add(actor)
            elif kind == "collateral_enabled":
                b["coll_enabled_n"] += 1
        elif asset == BORROWABLE:
            if kind == "borrow":
                b["bor_borrow"] += amt
                b["bor_borrow_n"] += 1
                if actor:
                    b["bor_borrow_actors"][actor] += amt
            elif kind == "withdraw":
                b["bor_withdraw"] += amt
                b["bor_withdraw_n"] += 1
                if actor:
                    b["bor_withdraw_actors"].add(actor)
            elif kind == "supply":
                b["bor_supply"] += amt
                b["bor_supply_n"] += 1
            elif kind == "repay":
                b["bor_repay"] += amt
            elif kind == "reserve_update":
                b["bor_rate"] = int(e["variable_borrow_rate"]) / RAY * 100
                b["bor_liq_rate"] = int(e["liquidity_rate"]) / RAY * 100
        if kind == "liquidation":
            b["n_liq"] += 1
    return blocks


def windows(blocks: dict[int, dict], lo_block: int, hi_block: int, span: int, step: int, attack_block: int | None, horizon: int,
            baseline: dict) -> list[dict]:
    rows = []
    last_rate = {}
    cur = None
    for b in range(lo_block, hi_block + 1):
        if b in blocks and blocks[b]["bor_rate"] is not None:
            cur = blocks[b]["bor_rate"]
        last_rate[b] = cur
    for end in range(lo_block + span - 1, hi_block + 1, step):
        start = end - span + 1
        sel = [blocks[b] for b in range(start, end + 1) if b in blocks]
        if not sel:
            continue
        coll_in = sum(b["coll_in"] for b in sel)
        coll_actors = set().union(*(b["coll_actors"] for b in sel))
        borrow = sum(b["bor_borrow"] for b in sel)
        borrow_by_actor: dict[str, int] = defaultdict(int)
        for b in sel:
            for k, v in b["bor_borrow_actors"].items():
                borrow_by_actor[k] += v
        withdraw = sum(b["bor_withdraw"] for b in sel)
        supply = sum(b["bor_supply"] for b in sel)
        repay = sum(b["bor_repay"] for b in sel)
        wd_actors = set().union(*(b["bor_withdraw_actors"] for b in sel))
        first_coll = next((b for b in range(start, end + 1) if b in blocks and blocks[b]["coll_in"] > 0), None)
        first_borrow = next((b for b in range(start, end + 1) if b in blocks and blocks[b]["bor_borrow"] > 0), None)
        lag = (first_borrow - first_coll) if (first_coll is not None and first_borrow is not None and first_borrow >= first_coll) else -1
        rate_end = last_rate.get(end)
        rate_start = last_rate.get(start)
        half = (start + end) // 2
        wd_early = sum(b["bor_withdraw"] for bb, b in blocks.items() if start <= bb <= half)
        wd_late = sum(b["bor_withdraw"] for bb, b in blocks.items() if half < bb <= end)
        rows.append({
            "window_start": start, "window_end": end,
            "label": int(attack_block is not None and end >= attack_block and start <= attack_block + horizon),
            # collateral side
            "coll_log_in": log10(coll_in), "coll_in_n": sum(b["coll_in_n"] for b in sel),
            "coll_in_vs_baseline": coll_in / baseline["coll_in_p99"] if baseline["coll_in_p99"] else 0.0,
            "coll_actors": len(coll_actors), "coll_enabled_n": sum(b["coll_enabled_n"] for b in sel),
            # borrow side
            "bor_log_borrow": log10(borrow), "bor_borrow_n": sum(b["bor_borrow_n"] for b in sel),
            "bor_borrow_vs_baseline": borrow / baseline["borrow_p99"] if baseline["borrow_p99"] else 0.0,
            "bor_borrow_top_share": (max(borrow_by_actor.values()) / borrow) if borrow else 0.0,
            "bor_log_withdraw": log10(withdraw), "bor_withdraw_n": sum(b["bor_withdraw_n"] for b in sel),
            "bor_withdraw_vs_baseline": withdraw / baseline["withdraw_p99"] if baseline["withdraw_p99"] else 0.0,
            "bor_withdraw_actors": len(wd_actors),
            "bor_net_log_outflow": log10(max(borrow + withdraw - supply - repay, 0)),
            "bor_outflow_acceleration": (wd_late - wd_early) / (wd_late + wd_early) if (wd_late + wd_early) else 0.0,
            # rates (state proxies)
            "bor_rate_end": rate_end if rate_end is not None else -1.0,
            "bor_rate_delta": (rate_end - rate_start) if (rate_end is not None and rate_start is not None) else 0.0,
            "bor_rate_vs_baseline": (rate_end / baseline["rate_p99"]) if (rate_end is not None and baseline["rate_p99"]) else 0.0,
            # causal chain
            "coll_then_borrow_lag": lag, "coll_and_borrow": int(coll_in > 0 and borrow > 0),
            "n_liq": sum(b["n_liq"] for b in sel), "n_events": sum(b["n_events"] for b in sel),
        })
    return rows


def baseline_from(normal_blocks: list[dict[int, dict]], span: int) -> dict:
    """p99 of per-window sums on normal data, so 'vs_baseline' features are ratios to a normal extreme, not to a mean."""
    import numpy as np
    coll, bor, wd, rates = [], [], [], []
    for blocks in normal_blocks:
        if not blocks:
            continue
        lo, hi = min(blocks), max(blocks)
        for end in range(lo + span - 1, hi + 1, span // 2 or 1):
            sel = [blocks[b] for b in range(end - span + 1, end + 1) if b in blocks]
            coll.append(sum(b["coll_in"] for b in sel))
            bor.append(sum(b["bor_borrow"] for b in sel))
            wd.append(sum(b["bor_withdraw"] for b in sel))
        rates += [v["bor_rate"] for v in blocks.values() if v["bor_rate"] is not None]
    q = lambda a: float(np.quantile([float(x) for x in a], 0.99)) if a else 0.0
    return {"coll_in_p99": q(coll), "borrow_p99": q(bor), "withdraw_p99": q(wd), "rate_p99": q(rates)}


def main(span: int = 60, step: int = 5, horizon: int = 1000, attack_block: int = 24908285) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    normal_files = sorted(SRC.glob("aave_events_normal_*.jsonl"))
    attack_file = next(SRC.glob("aave_events_kelpdao_attack_*.jsonl"))
    normal_blocks = [per_block(load_events(f)) for f in normal_files]
    baseline = baseline_from(normal_blocks, span)
    frames = []
    for f, blocks in zip(normal_files, normal_blocks):
        rows = windows(blocks, min(blocks), max(blocks), span, step, None, horizon, baseline)
        for r in rows:
            r["file"] = f.stem.replace("aave_events_", "")
        frames += rows
    ab = per_block(load_events(attack_file))
    rows = windows(ab, min(ab), max(ab), span, step, attack_block, horizon, baseline)
    for r in rows:
        r["file"] = "attack"
    frames += rows
    df = pd.DataFrame(frames)
    df.to_csv(OUT / "windows.csv", index=False)
    (OUT / "baseline.json").write_text(json.dumps({**baseline, "span": span, "step": step, "horizon": horizon}, indent=2))
    pos = int(df.label.sum())
    print(f"{len(df)} windows, {pos} positive, {len(normal_files)} normal files; baseline p99: "
          f"coll_in={baseline['coll_in_p99'] / 1e18:,.1f} rsETH, borrow={baseline['borrow_p99'] / 1e18:,.1f} WETH, "
          f"withdraw={baseline['withdraw_p99'] / 1e18:,.1f} WETH, rate={baseline['rate_p99']:.2f}%")
    att = df[df.file == "attack"]
    for c in ["coll_in_vs_baseline", "bor_borrow_vs_baseline", "bor_withdraw_vs_baseline", "bor_rate_end", "bor_borrow_top_share", "coll_then_borrow_lag"]:
        print(f"  {c:26} pre-attack median={att[att.label == 0][c].median():8.2f}   attack median={att[att.label == 1][c].median():8.2f}   attack max={att[att.label == 1][c].max():8.2f}")


if __name__ == "__main__":
    main()
