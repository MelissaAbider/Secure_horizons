"""Extract Aave V3 (Ethereum) reserve events around an incident from the SQD Portal (no API key).

Writes data/external/kelpdao/aave_events_<from>_<to>.jsonl with one decoded event per line, then a
block-level reserve series (supplied / borrowed / rates per asset) rebuilt by cumulating flows.

Usage:
  python -m evaluation.data_sources.sqd_aave_events --from 24907000 --to 24912000 --label kelpdao_attack
  python -m evaluation.data_sources.sqd_aave_events --from 24850000 --to 24860000 --label normal_w1
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests
from eth_abi import decode
from eth_utils import keccak

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "external" / "kelpdao"
PORTAL = "https://portal.sqd.dev/datasets/ethereum-mainnet/stream"
POOL = "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"  # Aave V3 Ethereum Pool
ASSETS = {
    "0xa1290d69c65a6fe4df752f95823fae25cb99e5a7": "rsETH",
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH",
    "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": "wstETH",
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
}
# Aave V3 Pool events. Indexed params become topics; the remaining params are ABI-encoded in `data`.
# Supply(reserve idx, user, onBehalfOf idx, amount, referralCode idx) -> data: user, amount
# Withdraw(reserve idx, user idx, to idx, amount) -> data: amount
# Borrow(reserve idx, user, onBehalfOf idx, amount, interestRateMode, borrowRate, referralCode idx) -> data: user, amount, mode, rate
# Repay(reserve idx, user idx, repayer idx, amount, useATokens) -> data: amount, useATokens
# ReserveDataUpdated(reserve idx, 5 x uint256) -> data: 5 values
# LiquidationCall(collateralAsset idx, debtAsset idx, user idx, debtToCover, liquidatedCollateralAmount, liquidator, receiveAToken)
EVENTS = {
    "Supply(address,address,address,uint256,uint16)": ("supply", ["address", "uint256"]),
    "Withdraw(address,address,address,uint256)": ("withdraw", ["uint256"]),
    "Borrow(address,address,address,uint256,uint8,uint256,uint16)": ("borrow", ["address", "uint256", "uint8", "uint256"]),
    "Repay(address,address,address,uint256,bool)": ("repay", ["uint256", "bool"]),
    "ReserveDataUpdated(address,uint256,uint256,uint256,uint256,uint256)": ("reserve_update", ["uint256"] * 5),
    "ReserveUsedAsCollateralEnabled(address,address)": ("collateral_enabled", []),
    "LiquidationCall(address,address,address,uint256,uint256,address,bool)": ("liquidation", ["uint256", "uint256", "address", "bool"]),
}
TOPICS = {"0x" + keccak(text=sig).hex(): meta for sig, meta in EVENTS.items()}


def stream(from_block: int, to_block: int) -> list[dict]:
    body = {"type": "evm", "fromBlock": from_block, "toBlock": to_block,
            "fields": {"block": {"number": True, "timestamp": True},
                       "log": {"address": True, "topics": True, "data": True, "transactionHash": True, "logIndex": True}},
            "logs": [{"address": [POOL], "topic0": list(TOPICS)}]}
    blocks, cursor, attempts = [], from_block, 0
    while cursor <= to_block:
        body["fromBlock"] = cursor
        r = requests.post(PORTAL, json=body, timeout=120)
        if r.status_code in (429, 500, 502, 503, 529) or (r.status_code == 200 and b'"overloaded"' in r.content[:300]):
            attempts += 1
            if attempts > 30:
                raise RuntimeError("SQD portal overloaded; retry later")
            wait = min(90, 5 * attempts)
            print(f"portal busy ({r.status_code}); retry {attempts} in {wait}s", flush=True)
            time.sleep(wait)
            continue
        r.raise_for_status()
        attempts = 0
        page = [json.loads(line) for line in r.text.splitlines() if line.strip()]
        if not page:
            break
        blocks += page
        last = page[-1]["header"]["number"]
        if last >= to_block:
            break
        cursor = last + 1
    return blocks


def decode_log(log: dict, header: dict) -> dict | None:
    meta = TOPICS.get(log["topics"][0])
    if not meta:
        return None
    kind, data_types = meta
    reserve = "0x" + log["topics"][1][-40:] if len(log["topics"]) > 1 else None
    payload = bytes.fromhex(log["data"][2:])
    try:
        values = decode(data_types, payload) if data_types and payload else ()
    except Exception:
        return {"block": header["number"], "timestamp": header["timestamp"], "tx": log["transactionHash"],
                "log_index": log["logIndex"], "event": kind + "_undecoded", "reserve": reserve,
                "asset": ASSETS.get(reserve or "", reserve), "raw_data": log["data"]}
    row = {"block": header["number"], "timestamp": header["timestamp"], "tx": log["transactionHash"],
           "log_index": log["logIndex"], "event": kind, "reserve": reserve, "asset": ASSETS.get(reserve or "", reserve)}
    if kind == "supply":
        row.update(user=values[0], on_behalf_of="0x" + log["topics"][2][-40:], amount=str(values[1]))
    elif kind == "withdraw":
        row.update(user="0x" + log["topics"][2][-40:], amount=str(values[0]))
    elif kind == "borrow":
        row.update(user=values[0], on_behalf_of="0x" + log["topics"][2][-40:], amount=str(values[1]), rate=str(values[3]))
    elif kind == "repay":
        row.update(user="0x" + log["topics"][2][-40:], amount=str(values[0]))
    elif kind == "reserve_update":
        row.update(liquidity_rate=str(values[0]), stable_borrow_rate=str(values[1]), variable_borrow_rate=str(values[2]),
                   liquidity_index=str(values[3]), variable_borrow_index=str(values[4]))
    elif kind == "liquidation":
        row.update(debt_covered=str(values[0]), collateral_liquidated=str(values[1]))
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="from_block", type=int, required=True)
    parser.add_argument("--to", dest="to_block", type=int, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    blocks = stream(args.from_block, args.to_block)
    rows = [row for b in blocks for log in b.get("logs", []) if (row := decode_log(log, b["header"]))]
    path = OUT / f"aave_events_{args.label}_{args.from_block}_{args.to_block}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""), encoding="utf-8")
    by_event = {}
    for r in rows:
        by_event[(r["event"], r["asset"])] = by_event.get((r["event"], r["asset"]), 0) + 1
    print(f"{len(blocks)} blocks with pool activity, {len(rows)} decoded events -> {path}")
    for (event, asset), n in sorted(by_event.items(), key=lambda kv: -kv[1])[:20]:
        print(f"  {event:18} {str(asset)[:12]:12} {n}")


if __name__ == "__main__":
    main()
