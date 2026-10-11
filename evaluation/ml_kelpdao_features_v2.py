"""Feature set v2 for the KelpDAO pattern. Builds on v1 (ml_kelpdao_features.py) and adds:

  - multi-scale windows: a short window (span) and a long context (3x span) for the same end block;
  - memory of the collateral surge: blocks since the last abnormal rsETH collateral inflow (pattern: collateral first,
    then borrowing for the next hundreds of blocks);
  - cumulative collateral and borrowing since that surge;
  - borrow-to-collateral ratio (WETH borrowed vs rsETH deposited, both log10) and borrow-per-borrower;
  - withdrawal herd features: withdrawers per block, mean withdrawal size vs baseline;
  - rate dynamics: borrow-rate slope over the long context and rate level vs baseline p99.

Everything is computed from the same decoded Aave events; nothing uses the attack label. The baseline (p99 of normal
windows) is computed from normal files only. Output: data/external/ml/kelpdao/windows_v2.csv
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from evaluation.ml_kelpdao_features import SRC, COLLATERAL, BORROWABLE, load_events, per_block, log10

OUT = Path(__file__).resolve().parents[1] / "data" / "external" / "ml" / "kelpdao"


def prefix_sums(blocks: dict[int, dict], lo: int, hi: int):
    keys = ["coll_in", "coll_in_n", "bor_borrow", "bor_borrow_n", "bor_withdraw", "bor_withdraw_n", "bor_supply", "bor_repay", "n_events", "n_liq"]
    acc = {k: [0] for k in keys}
    for b in range(lo, hi + 1):
        v = blocks.get(b)
        for k in keys:
            acc[k].append(acc[k][-1] + (v[k] if v else 0))
    return acc, lo


def rng(acc, lo, k, a, b):
    a, b = max(a, lo), min(b, lo + len(acc[k]) - 2)
    return acc[k][b - lo + 1] - acc[k][a - lo] if b >= a else 0


def actors_in(blocks, a, b, key):
    s = set()
    for bb in range(a, b + 1):
        v = blocks.get(bb)
        if v:
            s |= set(v[key]) if isinstance(v[key], set) else set(v[key].keys())
    return s


def rate_at(last_rate, b):
    return last_rate.get(b)


def build(blocks: dict[int, dict], lo: int, hi: int, span: int, step: int, attack_block, horizon: int, base: dict) -> list[dict]:
    acc, lo0 = prefix_sums(blocks, lo, hi)
    last_rate, cur = {}, None
    for b in range(lo, hi + 1):
        v = blocks.get(b)
        if v and v["bor_rate"] is not None:
            cur = v["bor_rate"]
        last_rate[b] = cur
    surge_blocks = [b for b, v in blocks.items() if v["coll_in"] > base["coll_block_p99"]]
    rows = []
    long = span * 3
    for end in range(lo + span - 1, hi + 1, step):
        s0, l0 = end - span + 1, max(lo, end - long + 1)
        R = lambda k, a=s0, b=end: rng(acc, lo0, k, a, b)
        coll_s, coll_l = R("coll_in"), R("coll_in", l0)
        bor_s, bor_l = R("bor_borrow"), R("bor_borrow", l0)
        wd_s, wd_l = R("bor_withdraw"), R("bor_withdraw", l0)
        sup_s, rep_s = R("bor_supply"), R("bor_repay")
        n_bor_s, n_wd_s = R("bor_borrow_n"), R("bor_withdraw_n")
        last_surge = max((b for b in surge_blocks if b <= end), default=None)
        since_surge = (end - last_surge) if last_surge is not None else -1
        bor_since_surge = rng(acc, lo0, "bor_borrow", last_surge, end) if last_surge is not None else 0
        coll_since_surge = rng(acc, lo0, "coll_in", last_surge, end) if last_surge is not None else 0
        borrowers = actors_in(blocks, s0, end, "bor_borrow_actors")
        by_actor = defaultdict(int)
        for bb in range(s0, end + 1):
            v = blocks.get(bb)
            if v:
                for k, amt in v["bor_borrow_actors"].items():
                    by_actor[k] += amt
        withdrawers = actors_in(blocks, s0, end, "bor_withdraw_actors")
        r_end, r_start, r_long = rate_at(last_rate, end), rate_at(last_rate, s0), rate_at(last_rate, l0)
        rows.append({
            "window_start": s0, "window_end": end,
            "label": int(attack_block is not None and end >= attack_block and s0 <= attack_block + horizon),
            "coll_log_in_s": log10(coll_s), "coll_log_in_l": log10(coll_l),
            "coll_in_vs_p99_s": coll_s / base["coll_in_p99"] if base["coll_in_p99"] else 0.0,
            "coll_in_vs_p99_l": coll_l / base["coll_in_p99_l"] if base["coll_in_p99_l"] else 0.0,
            "coll_in_n_s": R("coll_in_n"), "coll_actors_s": len(actors_in(blocks, s0, end, "coll_actors")),
            "blocks_since_coll_surge": since_surge if since_surge >= 0 else 10**6,
            "surge_recent": int(0 <= since_surge <= long),
            "log_borrow_since_surge": log10(bor_since_surge), "log_coll_since_surge": log10(coll_since_surge),
            "bor_log_borrow_s": log10(bor_s), "bor_log_borrow_l": log10(bor_l),
            "bor_borrow_vs_p99_s": bor_s / base["borrow_p99"] if base["borrow_p99"] else 0.0,
            "bor_borrow_vs_p99_l": bor_l / base["borrow_p99_l"] if base["borrow_p99_l"] else 0.0,
            "bor_borrow_n_s": n_bor_s, "bor_borrowers_s": len(borrowers),
            "bor_borrow_per_borrower_log": log10(bor_s / len(borrowers)) if borrowers else 0.0,
            "bor_borrow_top_share": (max(by_actor.values()) / bor_s) if bor_s else 0.0,
            "borrow_to_coll_log_ratio": (log10(bor_l) - log10(coll_l)) if (bor_l and coll_l) else 0.0,
            "bor_log_withdraw_s": log10(wd_s), "bor_log_withdraw_l": log10(wd_l),
            "bor_withdraw_vs_p99_s": wd_s / base["withdraw_p99"] if base["withdraw_p99"] else 0.0,
            "bor_withdraw_n_s": n_wd_s, "bor_withdrawers_s": len(withdrawers),
            "bor_withdraw_mean_log": log10(wd_s / n_wd_s) if n_wd_s else 0.0,
            "bor_net_log_outflow_s": log10(max(bor_s + wd_s - sup_s - rep_s, 0)),
            "bor_out_in_log_ratio": (log10(bor_s + wd_s) - log10(sup_s + rep_s)) if (sup_s + rep_s) and (bor_s + wd_s) else (6.0 if (bor_s + wd_s) else -6.0),
            "rate_end": r_end if r_end is not None else -1.0,
            "rate_vs_p99": (r_end / base["rate_p99"]) if (r_end is not None and base["rate_p99"]) else 0.0,
            "rate_delta_s": (r_end - r_start) if (r_end is not None and r_start is not None) else 0.0,
            "rate_slope_l": ((r_end - r_long) / long) if (r_end is not None and r_long is not None) else 0.0,
            "n_liq_s": R("n_liq"), "n_events_s": R("n_events"), "n_events_l": R("n_events", l0),
        })
    return rows


def baseline(normal_blocks, span):
    long = span * 3
    cs, cl, bs, bl, ws, rates, cb = [], [], [], [], [], [], []
    for blocks in normal_blocks:
        if not blocks:
            continue
        lo, hi = min(blocks), max(blocks)
        acc, lo0 = prefix_sums(blocks, lo, hi)
        for end in range(lo + span - 1, hi + 1, max(1, span // 3)):
            cs.append(float(rng(acc, lo0, "coll_in", end - span + 1, end)))
            cl.append(float(rng(acc, lo0, "coll_in", max(lo, end - long + 1), end)))
            bs.append(float(rng(acc, lo0, "bor_borrow", end - span + 1, end)))
            bl.append(float(rng(acc, lo0, "bor_borrow", max(lo, end - long + 1), end)))
            ws.append(float(rng(acc, lo0, "bor_withdraw", end - span + 1, end)))
        rates += [v["bor_rate"] for v in blocks.values() if v["bor_rate"] is not None]
        cb += [float(v["coll_in"]) for v in blocks.values()]
    q = lambda a: float(np.quantile(a, 0.99)) if a else 0.0
    return {"coll_in_p99": q(cs), "coll_in_p99_l": q(cl), "borrow_p99": q(bs), "borrow_p99_l": q(bl),
            "withdraw_p99": q(ws), "rate_p99": q(rates), "coll_block_p99": q(cb) if any(cb) else 0.0}


def main(span: int = 60, step: int = 5, horizon: int = 1000, attack_block: int = 24908285):
    normal_files = sorted(SRC.glob("aave_events_normal_*.jsonl"))
    attack_file = next(SRC.glob("aave_events_kelpdao_attack_*.jsonl"))
    nb = [per_block(load_events(f)) for f in normal_files]
    base = baseline(nb, span)
    rows = []
    for f, blocks in zip(normal_files, nb):
        r = build(blocks, min(blocks), max(blocks), span, step, None, horizon, base)
        for x in r:
            x["file"] = f.stem.replace("aave_events_", "")
        rows += r
    ab = per_block(load_events(attack_file))
    r = build(ab, min(ab), max(ab), span, step, attack_block, horizon, base)
    for x in r:
        x["file"] = "attack"
    rows += r
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "windows_v2.csv", index=False)
    (OUT / "baseline_v2.json").write_text(json.dumps({**base, "span": span, "step": step, "horizon": horizon}, indent=2))
    print(f"v2: {len(df)} windows, {int(df.label.sum())} positive, {len(df.columns) - 4} features")


if __name__ == "__main__":
    main()
