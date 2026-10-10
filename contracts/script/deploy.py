"""Deploys the scenario contracts on $NETWORK and writes deployments/<network>.json + abi/ (TASKS.md 2.3). Owner: T1.

Run from the repo root: make deploy            (NETWORK from .env or the command line)
                         make deploy FORCE=1    (fuji: overwrite an existing deployment; tell the team, addresses change)
                         make abi               (export the ABIs only)
Keys come from backend/settings.py: on local, anvil's public test accounts; on fuji, the *_PK variables of .env.
No key is ever printed or written to disk.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eth_account import Account  # noqa: E402

from backend import settings  # noqa: E402

CONTRACTS = ROOT / "contracts"
ABI_NAMES = ["MockERC20", "RsETH", "MockBridge", "MockOracle", "MiniLend", "TreasuryVault", "EvidenceRegistry"]
LABELS = {"lend-eth": "Lending protocol, Ethereum deployment (simulated)",
          "lend-avax": "Lending protocol, Avalanche deployment (simulated)"}


def forge() -> str:
    return shutil.which("forge") or str(Path.home() / ".foundry" / "bin" / "forge")


def hex_key(role: str) -> str:
    key = settings.private_key(role)
    return key if key.startswith("0x") else "0x" + key


def address(role: str) -> str:
    return Account.from_key(settings.private_key(role)).address


def export_abis() -> None:
    (ROOT / "abi").mkdir(exist_ok=True)
    for name in ABI_NAMES:
        artifact = json.loads((CONTRACTS / "out" / f"{name}.sol" / f"{name}.json").read_text())
        (ROOT / "abi" / f"{name}.json").write_text(json.dumps(artifact["abi"], indent=2) + "\n")
    print(f"ABIs exported to abi/ ({len(ABI_NAMES)} files)")


def deploy() -> None:
    target = ROOT / "deployments" / f"{settings.NETWORK}.json"
    if settings.NETWORK == "fuji" and target.exists() and os.environ.get("FORCE") != "1":
        sys.exit("deployments/fuji.json already exists: run `make deploy FORCE=1` and tell the team (addresses change)")
    target.parent.mkdir(exist_ok=True)
    raw = target.with_suffix(".raw.json")
    env = {**os.environ,
           "T1_DEPLOYER_PK": hex_key("deployer"),
           "T1_OWNER": address("owner"),
           "T1_GUARDIAN": address("guardian"),
           "T1_PROTOCOL_GUARDIAN": address("protocol_guardian"),
           "T1_OUT": str(raw)}
    cmd = [forge(), "script", "script/Deploy.s.sol:Deploy", "--rpc-url", settings.RPC_URL, "--broadcast"]
    if settings.NETWORK != "local":
        cmd.append("--slow")  # one transaction at a time on a public network
    print(f"deploying on {settings.NETWORK} ({settings.RPC_URL}) from {address('deployer')} ...")
    subprocess.run(cmd, cwd=CONTRACTS, env=env, check=True, stdout=subprocess.DEVNULL)

    a = json.loads(raw.read_text())
    raw.unlink()
    bots = [Account.from_key(k).address for k in settings.bot_pks()]
    deployment = {
        "network": settings.NETWORK,
        "chain_id": settings.CHAIN_ID,
        "deployed_at_block": a["deployed_at_block"],
        "explorer": settings.EXPLORER_URL,
        "assets": {s: a[s] for s in ("USDC", "WETH", "rsETH")},
        "contracts": {k: a[k] for k in ("MockBridge", "MockOracle", "TreasuryVault", "EvidenceRegistry")},
        "lending": [{"id": i, "label": LABELS[i], "address": a[i]} for i in ("lend-eth", "lend-avax")],
        "roles": {r: address(r) for r in ("deployer", "owner", "guardian", "protocol_guardian", "attacker", "evidence")}
        | {"bots": bots},
    }
    if target.exists():  # keep the previous deployment
        history = target.parent / "history"
        history.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target.rename(history / f"{settings.NETWORK}-{stamp}.json")
    target.write_text(json.dumps(deployment, indent=2) + "\n")
    export_abis()
    print(f"wrote deployments/{settings.NETWORK}.json")
    for name, addr in list(deployment["assets"].items()) + list(deployment["contracts"].items()) + [(x["id"], x["address"]) for x in deployment["lending"]]:
        link = f"  {settings.EXPLORER_URL}/address/{addr}" if settings.NETWORK == "fuji" else ""
        print(f"  {name:17s} {addr}{link}")


if __name__ == "__main__":
    export_abis() if "--abi-only" in sys.argv else deploy()
