"""Generic incident extractor: for each incident in incidents.json, pull ALL logs of the listed contracts over
an attack window and several normal windows from the SQD Portal (no API key, EVM chains SQD indexes).

Output: data/external/incidents/<id>/{attack,normal_<offset>}.jsonl with one raw log per line
(block, timestamp, tx, log_index, address, topic0, topics, data) plus a manifest.json. Decoding is left to
the feature builder so the same raw file serves rules and ML.

Usage:
  python -m evaluation.data_sources.sqd_incident_logs             # all incidents
  python -m evaluation.data_sources.sqd_incident_logs --only nomad_2022 ronin_2022
  python -m evaluation.data_sources.sqd_incident_logs --resolve   # fill attack_block from attack_tx when 0 (needs public RPC)
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).with_name("incidents.json")
OUT = ROOT / "data" / "external" / "incidents"
PORTAL = "https://portal.sqd.dev/datasets/{chain}/stream"
PUBLIC_RPC = {"ethereum-mainnet": "https://ethereum-rpc.publicnode.com"}


def stream(chain: str, addresses: list[str], from_block: int, to_block: int) -> list[dict]:
    body = {"type": "evm", "fromBlock": from_block, "toBlock": to_block,
            "fields": {"block": {"number": True, "timestamp": True},
                       "log": {"address": True, "topics": True, "data": True, "transactionHash": True, "logIndex": True}},
            "logs": [{"address": [a.lower() for a in addresses]}]}
    rows, cursor, attempts = [], from_block, 0
    while cursor <= to_block:
        body["fromBlock"] = cursor
        r = requests.post(PORTAL.format(chain=chain), json=body, timeout=180)
        if r.status_code in (429, 500, 502, 503, 529):
            attempts += 1
            if attempts > 40:
                raise RuntimeError(f"portal overloaded for {chain}")
            time.sleep(min(90, 5 * attempts))
            continue
        r.raise_for_status()
        attempts = 0
        page = [json.loads(line) for line in r.text.splitlines() if line.strip()]
        if not page:
            break
        for b in page:
            for log in b.get("logs", []):
                rows.append({"block": b["header"]["number"], "timestamp": b["header"]["timestamp"], "tx": log["transactionHash"],
                             "log_index": log["logIndex"], "address": log["address"], "topic0": log["topics"][0] if log["topics"] else None,
                             "topics": log["topics"], "data": log["data"]})
        last = page[-1]["header"]["number"]
        if last >= to_block:
            break
        cursor = last + 1
    return rows


def resolve_block(chain: str, tx: str) -> int | None:
    rpc = PUBLIC_RPC.get(chain)
    if not rpc or not tx or tx == "0x":
        return None
    r = requests.post(rpc, json={"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionReceipt", "params": [tx]}, timeout=30)
    result = r.json().get("result") or {}
    return int(result["blockNumber"], 16) if result.get("blockNumber") else None


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--resolve", action="store_true")
    parser.add_argument("--skip-normal", action="store_true")
    args = parser.parse_args()
    incidents = json.loads(SPEC.read_text(encoding="utf-8"))
    manifest = []
    for inc in incidents:
        if args.only and inc["id"] not in args.only:
            continue
        if args.resolve and not inc["attack_block"]:
            inc["attack_block"] = resolve_block(inc["chain"], inc["attack_tx"]) or 0
        if not inc["attack_block"]:
            print(f"skip {inc['id']}: no attack block")
            continue
        folder = OUT / inc["id"]
        addresses = list(inc["contracts"].values())
        a0, a1 = inc["attack_block"] - inc["window_before"], inc["attack_block"] + inc["window_after"]
        t = time.time()
        attack = stream(inc["chain"], addresses, a0, a1)
        write(folder / "attack.jsonl", attack)
        entry = {"id": inc["id"], "category": inc["category"], "chain": inc["chain"], "attack_block": inc["attack_block"],
                 "attack_window": [a0, a1], "attack_logs": len(attack), "normal": []}
        print(f"{inc['id']}: attack window {a0}-{a1} -> {len(attack)} logs ({time.time() - t:.0f}s)")
        if not args.skip_normal:
            for off in inc["normal_offsets"]:
                n0 = inc["attack_block"] + off
                n1 = n0 + inc["window_before"] + inc["window_after"]
                rows = stream(inc["chain"], addresses, n0, n1)
                write(folder / f"normal_{abs(off)}.jsonl", rows)
                entry["normal"].append({"window": [n0, n1], "logs": len(rows)})
                print(f"  normal offset {off}: {len(rows)} logs")
        manifest.append(entry)
        (folder / "manifest.json").write_text(json.dumps({**inc, **entry}, indent=2), encoding="utf-8")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
