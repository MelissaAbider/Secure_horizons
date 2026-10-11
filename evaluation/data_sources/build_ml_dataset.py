"""Turn raw incident logs into a labeled, windowed feature table for ML.

For every incident folder in data/external/incidents/<id>/ (attack.jsonl + normal_*.jsonl):
  1. decode the common lending/bridge events we know (Aave V3, Compound-style cTokens, ERC20 Transfer, OFT, generic);
  2. aggregate per block: inflow/outflow counts and amounts, distinct actors, max single amount, top-actor share;
  3. slide a window of W blocks (default 20 samples of block_step blocks) and compute per-window features
     (sums, slopes, ratios to the pre-window baseline, concentration, time since first large event);
  4. label each window: 1 if it overlaps [attack_block, attack_block + horizon], else 0. Windows that end before the
     attack block in the attack file are labeled 0 (pre-attack normal) so the model sees the transition.

Output: data/external/ml/windows.parquet (if pyarrow available) and windows.csv, plus dataset_card.json.
Amount features are log10 of base-unit values to be comparable across tokens and chains; the model should
never see raw USD (prices are not needed and would add a dependency on oracles).
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from eth_utils import keccak

ROOT = Path(__file__).resolve().parents[2]
INC = ROOT / "data" / "external" / "incidents"
OUT = ROOT / "data" / "external" / "ml"

T = lambda sig: "0x" + keccak(text=sig).hex()
# direction: +1 money entering the protocol (supply/mint/repay), -1 leaving (withdraw/redeem/borrow), 0 neutral
SIGNATURES = {
    T("Supply(address,address,address,uint256,uint16)"): ("supply", +1),
    T("Deposit(address,address,uint256,uint16)"): ("supply", +1),  # Aave V2 style
    T("Withdraw(address,address,address,uint256)"): ("withdraw", -1),
    T("Borrow(address,address,address,uint256,uint8,uint256,uint16)"): ("borrow", -1),
    T("Borrow(address,address,address,uint256,uint256,uint256,uint16)"): ("borrow", -1),  # Aave V2
    T("Repay(address,address,address,uint256,bool)"): ("repay", +1),
    T("Repay(address,address,address,uint256)"): ("repay", +1),
    T("Mint(address,uint256,uint256)"): ("supply", +1),  # Compound cToken
    T("Redeem(address,uint256,uint256)"): ("withdraw", -1),
    T("Borrow(address,uint256,uint256,uint256)"): ("borrow", -1),
    T("RepayBorrow(address,address,uint256,uint256,uint256)"): ("repay", +1),
    T("LiquidationCall(address,address,address,uint256,uint256,address,bool)"): ("liquidation", 0),
    T("LiquidateBorrow(address,address,uint256,address,uint256)"): ("liquidation", 0),
    T("ReserveDataUpdated(address,uint256,uint256,uint256,uint256,uint256)"): ("rate_update", 0),
    T("Transfer(address,address,uint256)"): ("transfer", 0),
    T("OFTReceived(bytes32,uint32,address,uint256)"): ("bridge_in", +1),
    T("OFTSent(bytes32,uint32,address,uint256,uint256)"): ("bridge_out", -1),
    T("Process(bytes32,bool,bytes)"): ("bridge_process", 0),  # Nomad Replica
    T("Send(address,address,uint32,uint32,bytes32,bytes)"): ("bridge_out", -1),  # Nomad BridgeRouter
    T("TokenWithdrew(uint256,address,address,uint256)"): ("bridge_in", +1),  # Ronin
    T("TokenDeposited(uint256,address,address,address,uint256)"): ("bridge_out", -1),
    T("UnlockEvent(address,address,address,uint256)"): ("bridge_in", +1),  # Poly
    T("LockEvent(address,address,uint64,address,bytes,uint256)"): ("bridge_out", -1),
    T("LogAnySwapIn(bytes32,address,address,uint256,uint256,uint256)"): ("bridge_in", +1),  # Multichain
    T("LogAnySwapOut(address,address,address,uint256,uint256,uint256)"): ("bridge_out", -1),
    T("Unlocked(address,uint256,address,bytes32)"): ("bridge_in", +1),  # Harmony
    T("Locked(address,address,uint256,address)"): ("bridge_out", -1),
    T("Receive(uint64,address,address,address,uint256)"): ("bridge_in", +1),  # Nomad BridgeRouter
    T("UnlockEvent(address,address,uint256)"): ("bridge_in", +1),  # Poly LockProxy
    T("LockEvent(address,address,uint64,bytes,bytes,uint256)"): ("bridge_out", -1),
    T("VerifyHeaderAndExecuteTxEvent(uint64,bytes,bytes,bytes)"): ("bridge_process", 0),  # Poly manager
    T("CrossChainEvent(address,bytes,address,uint64,bytes,bytes)"): ("bridge_out", -1),
    T("Deposit(address,address,uint256)"): ("supply", +1),  # Euler
    T("Withdraw(address,address,uint256)"): ("withdraw", -1),
    T("Borrow(address,address,uint256)"): ("borrow", -1),
    T("Repay(address,address,uint256)"): ("repay", +1),
    T("Liquidation(address,address,address,address,uint256,uint256,uint256,uint256,uint256)"): ("liquidation", 0),
    T("AssetStatus(address,uint256,uint256,uint96,uint256,uint256,int96,uint256)"): ("rate_update", 0),
    T("MarketEntered(address,address)"): ("enter_market", 0),  # Compound/Cream comptroller
}


def first_uint(data: str) -> int | None:
    body = data[2:] if data.startswith("0x") else data
    return int(body[:64], 16) if len(body) >= 64 else None


def amount_of(kind: str, topics: list[str], data: str) -> int | None:
    body = data[2:] if data.startswith("0x") else data
    words = [int(body[i:i + 64], 16) for i in range(0, len(body) - len(body) % 64, 64)]
    if not words:
        return None
    if kind in ("supply", "borrow") and len(words) >= 2 and words[0] < 2**160:
        return words[1]  # Aave V3: data = user, amount, ...
    if kind == "liquidation":
        return words[0]
    if kind == "bridge_out" and len(words) >= 2:
        return words[1] if len(topics) > 2 else words[0]
    return words[0]


def actor_of(topics: list[str]) -> str | None:
    for t in topics[1:]:
        if t and t.startswith("0x") and len(t) == 66 and t[:26] == "0x000000000000000000000000":
            return "0x" + t[-40:]
    return None


def decode_row(row: dict) -> dict | None:
    meta = SIGNATURES.get(row.get("topic0") or "")
    if not meta:
        return None
    kind, direction = meta
    amount = amount_of(kind, row["topics"], row["data"]) if kind != "rate_update" else None
    if kind == "transfer" and (amount is None or len(row["topics"]) < 3):
        return None
    return {"block": row["block"], "ts": row["timestamp"], "kind": kind, "direction": direction, "amount": amount,
            "actor": actor_of(row["topics"]), "tx": row["tx"], "address": row["address"]}


def per_block(events: list[dict]) -> dict[int, dict]:
    blocks: dict[int, dict] = defaultdict(lambda: {"in": 0, "out": 0, "n_in": 0, "n_out": 0, "n_borrow": 0, "borrow": 0,
                                                   "n_liq": 0, "n_rate": 0, "n_bridge_in": 0, "bridge_in": 0, "max_amount": 0,
                                                   "actors": set(), "by_actor": defaultdict(int), "n_events": 0, "ts": 0})
    for e in events:
        b = blocks[e["block"]]
        b["n_events"] += 1
        b["ts"] = e["ts"]
        a = e["amount"] or 0
        if e["direction"] > 0:
            b["in"] += a
            b["n_in"] += 1
        elif e["direction"] < 0:
            b["out"] += a
            b["n_out"] += 1
        if e["kind"] == "borrow":
            b["n_borrow"] += 1
            b["borrow"] += a
        if e["kind"] == "liquidation":
            b["n_liq"] += 1
        if e["kind"] == "rate_update":
            b["n_rate"] += 1
        if e["kind"] == "bridge_in":
            b["n_bridge_in"] += 1
            b["bridge_in"] += a
        b["max_amount"] = max(b["max_amount"], a)
        if e["actor"]:
            b["actors"].add(e["actor"])
            b["by_actor"][e["actor"]] += a
    return blocks


def log10(x: float) -> float:
    return math.log10(x) if x > 0 else 0.0


def windows(blocks: dict[int, dict], start: int, end: int, step: int, size: int, attack_block: int | None, horizon: int,
            baseline_max_single: float) -> list[dict]:
    rows = []
    grid = list(range(start, end + 1, step))
    for i in range(size, len(grid) + 1):
        lo, hi = grid[i - size], grid[i - 1] + step - 1
        sel = [blocks[b] for b in range(lo, hi + 1) if b in blocks]
        if not sel:
            continue
        inflow = sum(b["in"] for b in sel)
        outflow = sum(b["out"] for b in sel)
        borrow = sum(b["borrow"] for b in sel)
        bridge_in = sum(b["bridge_in"] for b in sel)
        max_single = max(b["max_amount"] for b in sel)
        actors = set().union(*(b["actors"] for b in sel))
        by_actor: dict[str, int] = defaultdict(int)
        for b in sel:
            for k, v in b["by_actor"].items():
                by_actor[k] += v
        total_actor = sum(by_actor.values()) or 1
        top_share = max(by_actor.values(), default=0) / total_actor
        half = len(sel) // 2 or 1
        early_out = sum(b["out"] for b in sel[:half])
        late_out = sum(b["out"] for b in sel[half:])
        label = int(attack_block is not None and hi >= attack_block and lo <= attack_block + horizon)
        rows.append({
            "window_start": lo, "window_end": hi, "label": label,
            "blocks_with_activity": len(sel), "n_events": sum(b["n_events"] for b in sel),
            "n_in": sum(b["n_in"] for b in sel), "n_out": sum(b["n_out"] for b in sel), "n_borrow": sum(b["n_borrow"] for b in sel),
            "n_liq": sum(b["n_liq"] for b in sel), "n_rate_updates": sum(b["n_rate"] for b in sel), "n_bridge_in": sum(b["n_bridge_in"] for b in sel),
            "log_inflow": log10(inflow), "log_outflow": log10(outflow), "log_borrow": log10(borrow), "log_bridge_in": log10(bridge_in),
            "log_max_single": log10(max_single), "max_single_vs_baseline": (max_single / baseline_max_single) if baseline_max_single else 0.0,
            "out_in_log_ratio": max(-12.0, min(12.0, log10(outflow) - log10(inflow))) if (inflow and outflow) else (12.0 if outflow else (-12.0 if inflow else 0.0)),
            "outflow_acceleration": (late_out - early_out) / (early_out + late_out) if (early_out + late_out) else 0.0,
            "distinct_actors": len(actors), "top_actor_share": top_share,
            "events_per_block": sum(b["n_events"] for b in sel) / max(1, hi - lo + 1),
        })
    return rows


def main(step: int = 10, size: int = 20, horizon: int = 600) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((INC / "manifest.json").read_text()) if (INC / "manifest.json").exists() else []
    all_rows, card = [], []
    for folder in sorted(p for p in INC.iterdir() if p.is_dir()):
        spec_path = folder / "manifest.json"
        spec = json.loads(spec_path.read_text()) if spec_path.exists() else {}
        attack_block = spec.get("attack_block")
        files = sorted(folder.glob("*.jsonl"))
        normal_max = 0.0
        decoded = {}
        for f in files:
            events = [d for line in f.read_text(encoding="utf-8").splitlines() if line.strip() for d in [decode_row(json.loads(line))] if d]
            decoded[f.name] = events
            if f.name.startswith("normal") and events:
                normal_max = max(normal_max, max((e["amount"] or 0) for e in events))
        for name, events in decoded.items():
            if not events:
                continue
            blocks = per_block(events)
            lo, hi = min(blocks), max(blocks)
            is_attack_file = name == "attack.jsonl"
            rows = windows(blocks, lo, hi, step, size, attack_block if is_attack_file else None, horizon, normal_max)
            for r in rows:
                r.update(incident=folder.name, category=spec.get("category", ""), chain=spec.get("chain", ""), file=name)
            all_rows += rows
            card.append({"incident": folder.name, "file": name, "events_decoded": len(events), "windows": len(rows),
                         "positive_windows": sum(r["label"] for r in rows)})
    if not all_rows:
        print("no data")
        return
    fields = list(all_rows[0].keys())
    with open(OUT / "windows.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    try:
        import pandas as pd
        pd.DataFrame(all_rows).to_parquet(OUT / "windows.parquet", index=False)
    except Exception:
        pass
    pos = sum(r["label"] for r in all_rows)
    (OUT / "dataset_card.json").write_text(json.dumps({"windows": len(all_rows), "positive": pos, "negative": len(all_rows) - pos,
                                                       "step_blocks": step, "window_samples": size, "label_horizon_blocks": horizon,
                                                       "features": [c for c in fields if c not in ("incident", "category", "chain", "file", "label", "window_start", "window_end")],
                                                       "files": card}, indent=2), encoding="utf-8")
    print(f"{len(all_rows)} windows ({pos} positive) from {len({r['incident'] for r in all_rows})} incidents -> {OUT}")
    for c in card:
        print(f"  {c['incident']:22} {c['file']:22} events={c['events_decoded']:6} windows={c['windows']:4} pos={c['positive_windows']}")


if __name__ == "__main__":
    main()
