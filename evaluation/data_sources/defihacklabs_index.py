"""Build an index of bridge-related incidents from DeFiHackLabs READMEs with fork blocks and tx hashes.

Reads data/external/defihacklabs/readme_*.md (downloaded from GitHub) and writes
data/external/defihacklabs/bridge_incidents.json. Read-only; no RPC needed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "external" / "defihacklabs"
KEYWORDS = re.compile(r"bridge|layerzero|\boft\b|cross-chain|allbridge|multichain|anyswap|wormhole|nomad|ronin|poly network|orbit|harmony|rseth|cctp|chainswap", re.I)
HEADER = re.compile(r"^### (\d{8}) (.+?) - (.+)$")
TX = re.compile(r"(?:etherscan|bscscan|snowtrace|arbiscan|polygonscan|basescan|phalcon|blocksec)[^\s)]*?/tx/(0x[0-9a-fA-F]{64})", re.I)
RAW_TX = re.compile(r"\b(0x[0-9a-fA-F]{64})\b")
BLOCK = re.compile(r"(?:block|fork)[^0-9]{0,40}?(\d{7,9})", re.I)
LOST = re.compile(r"Lost:?\s*([^\n]+)")
POC = re.compile(r"\((src/test/[^)]+\.sol)\)")


def parse(text: str) -> list[dict]:
    incidents, current = [], None
    for line in text.splitlines():
        header = HEADER.match(line.strip())
        if header:
            date, name, title = header.groups()
            current = {"date": date, "name": name.strip(), "title": title.strip(), "bridge_related": bool(KEYWORDS.search(line)),
                       "tx_hashes": [], "blocks": [], "lost": None, "poc": None}
            incidents.append(current)
            continue
        if current is None:
            continue
        current["tx_hashes"] += [h.lower() for h in TX.findall(line)] or [h.lower() for h in RAW_TX.findall(line) if "tx" in line.lower()]
        current["blocks"] += [int(b) for b in BLOCK.findall(line)]
        if (m := LOST.search(line)) and current["lost"] is None:
            current["lost"] = m.group(1).strip()
        if (m := POC.search(line)) and current["poc"] is None:
            current["poc"] = m.group(1)
    for item in incidents:
        item["tx_hashes"] = sorted(set(item["tx_hashes"]))
        item["blocks"] = sorted(set(item["blocks"]))
    return incidents


def main() -> None:
    incidents = []
    for path in sorted(SRC.glob("readme_*.md")):
        incidents += parse(path.read_text(encoding="utf-8", errors="replace"))
    unique = {(i["date"], i["name"]): i for i in incidents}
    bridge = sorted((i for i in unique.values() if i["bridge_related"]), key=lambda i: i["date"])
    out = SRC / "bridge_incidents.json"
    out.write_text(json.dumps(bridge, indent=2, ensure_ascii=False), encoding="utf-8")
    with_tx = sum(1 for i in bridge if i["tx_hashes"])
    print(f"{len(unique)} incidents parsed, {len(bridge)} bridge-related, {with_tx} with tx hashes -> {out}")
    for i in bridge:
        print(f"  {i['date']} {i['name'][:34]:34} tx={len(i['tx_hashes'])} poc={'y' if i['poc'] else '-'}")


if __name__ == "__main__":
    main()
