"""Extract the rsETH LayerZero OFT bridge events on both chains from the SQD Portal (no API key).

Destination (Ethereum): OFTReceived on the Kelp bridge adapter 0x85d4...8ef3.
Source (Unichain):      OFTSent on the rsETH OApp 0xc3ea...9f58.
Both carry the LayerZero GUID, which lets us reconcile deliveries against sends: a delivery whose GUID has no
earlier OFTSent is the R1 signal. Writes data/external/kelpdao/bridge_<chain>_<from>_<to>.jsonl.
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
CHAINS = {
    "ethereum": ("https://portal.sqd.dev/datasets/ethereum-mainnet/stream", "0x85d456b2dff1fd8245387c0bfb64dfb700e98ef3"),
    "unichain": ("https://portal.sqd.dev/datasets/unichain-mainnet/stream", "0xc3eacf0612346366db554c991d7858716db09f58"),
}
# OFTSent(bytes32 indexed guid, uint32 dstEid, address indexed fromAddress, uint256 amountSentLD, uint256 amountReceivedLD)
# OFTReceived(bytes32 indexed guid, uint32 srcEid, address indexed toAddress, uint256 amountReceivedLD)
SIGS = {
    "0x" + keccak(text="OFTSent(bytes32,uint32,address,uint256,uint256)").hex(): ("sent", ["uint32", "uint256", "uint256"]),
    "0x" + keccak(text="OFTReceived(bytes32,uint32,address,uint256)").hex(): ("received", ["uint32", "uint256"]),
}


def stream(url: str, address: str, from_block: int, to_block: int) -> list[dict]:
    body = {"type": "evm", "fromBlock": from_block, "toBlock": to_block,
            "fields": {"block": {"number": True, "timestamp": True},
                       "log": {"address": True, "topics": True, "data": True, "transactionHash": True, "logIndex": True}},
            "logs": [{"address": [address], "topic0": list(SIGS)}]}
    blocks, cursor, attempts = [], from_block, 0
    while cursor <= to_block:
        body["fromBlock"] = cursor
        r = requests.post(url, json=body, timeout=120)
        if r.status_code in (429, 500, 502, 503, 529):
            attempts += 1
            if attempts > 30:
                raise RuntimeError("portal overloaded")
            time.sleep(min(90, 5 * attempts))
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chain", choices=CHAINS, required=True)
    parser.add_argument("--from", dest="from_block", type=int, required=True)
    parser.add_argument("--to", dest="to_block", type=int, required=True)
    args = parser.parse_args()
    url, address = CHAINS[args.chain]
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for b in stream(url, address, args.from_block, args.to_block):
        for log in b.get("logs", []):
            kind, types = SIGS[log["topics"][0]]
            values = decode(types, bytes.fromhex(log["data"][2:]))
            row = {"chain": args.chain, "block": b["header"]["number"], "timestamp": b["header"]["timestamp"],
                   "tx": log["transactionHash"], "event": kind, "guid": log["topics"][1],
                   "counterparty": "0x" + log["topics"][2][-40:], "eid": values[0]}
            if kind == "sent":
                row.update(amount_sent=str(values[1]), amount_received=str(values[2]))
            else:
                row.update(amount_received=str(values[1]))
            rows.append(row)
    path = OUT / f"bridge_{args.chain}_{args.from_block}_{args.to_block}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""), encoding="utf-8")
    print(f"{len(rows)} OFT events -> {path}")
    if rows:
        amounts = sorted((int(r["amount_received"]) for r in rows), reverse=True)
        print(f"  largest {amounts[0] / 1e18:,.3f}  second {amounts[1] / 1e18 if len(amounts) > 1 else 0:,.3f}  count {len(amounts)}")


if __name__ == "__main__":
    main()
