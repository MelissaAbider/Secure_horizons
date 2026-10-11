"""Deploys the scenario contracts on $NETWORK and writes deployments/<network>.json + abi/ (TASKS.md 2.3). Owner: T1.

Run from the repo root: make deploy            (NETWORK from .env or the command line)
                         make deploy RESUME=1   (finish a deployment the public RPC interrupted; idempotent)
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
import time
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


def _send_until(done, build, label: str) -> None:
    """Send build() with the deployer until done() is true. Re-checks the chain before every attempt,
    so a transaction the public RPC lost is resent and one that went through is never sent twice."""
    from backend import chain

    for attempt in range(6):
        if done():
            return
        try:
            receipt = chain.send(build(), chain.account("deployer"))
            print(f"  {label}: {chain.explorer_tx(receipt['tx_hash']) if settings.NETWORK == 'fuji' else receipt['tx_hash']}")
        except Exception as exc:  # stale public RPC: wait and look again
            print(f"  {label}: retry ({str(exc)[:70]})")
            time.sleep(4)
    if not done():
        sys.exit(f"could not complete: {label}")


def configure(a: dict) -> None:
    """Idempotent configuration: prices, reserves, guardian hand-over. Finishes what an interrupted forge run left."""
    from backend import chain

    w3 = chain.w3()
    load = lambda name: json.loads((CONTRACTS / "out" / f"{name}.sol" / f"{name}.json").read_text())["abi"]
    oracle = w3.eth.contract(address=a["MockOracle"], abi=load("MockOracle"))

    def price(sym: str) -> int:
        try:
            return oracle.functions.getPriceE8(a[sym]).call()
        except Exception:
            return 0

    for sym, value in (("USDC", 10**8), ("WETH", 2500 * 10**8), ("rsETH", 2500 * 10**8)):
        _send_until(lambda: price(sym) == value, lambda: oracle.functions.setPriceE8(a[sym], value), f"price {sym}")
    guardian = address("protocol_guardian")
    for market_id in ("lend-eth", "lend-avax"):
        market = w3.eth.contract(address=a[market_id], abi=load("MiniLend"))
        for sym, borrowable, ltv in (("USDC", True, 8000), ("WETH", True, 8000), ("rsETH", False, 7500)):
            _send_until(lambda: a[sym] in market.functions.getAssets().call(),
                        lambda: market.functions.listReserve(a[sym], borrowable, ltv), f"{market_id} list {sym}")
        _send_until(lambda: market.functions.protocolGuardian().call() == guardian,
                    lambda: market.functions.transferGuardian(guardian), f"{market_id} guardian")


def deploy() -> None:
    target = ROOT / "deployments" / f"{settings.NETWORK}.json"
    resume = os.environ.get("RESUME") == "1"
    if settings.NETWORK == "fuji" and target.exists() and os.environ.get("FORCE") != "1" and not resume:
        sys.exit("deployments/fuji.json already exists: run `make deploy FORCE=1` and tell the team (addresses change)")
    target.parent.mkdir(exist_ok=True)
    raw = target.with_suffix(".raw.json")
    if resume:
        if not raw.exists():
            sys.exit(f"nothing to resume: {raw.name} not found")
        print(f"resuming the {settings.NETWORK} deployment from {raw.name} ...")
        configure(json.loads(raw.read_text()))
        _write(target, raw)
        return
    env = {**os.environ,
           "T1_DEPLOYER_PK": hex_key("deployer"),
           "T1_OWNER": address("owner"),
           "T1_GUARDIAN": address("guardian"),
           "T1_PROTOCOL_GUARDIAN": address("protocol_guardian"),
           "T1_OUT": str(raw)}
    cmd = [forge(), "script", "script/Deploy.s.sol:Deploy", "--rpc-url", settings.RPC_URL, "--broadcast"]
    if settings.NETWORK != "local":
        cmd.append("--slow")  # one transaction at a time on a public network
    print(f"deploying on {settings.NETWORK} ({settings.RPC_URL.split('/')[2]}) from {address('deployer')} ...")
    if subprocess.run(cmd, cwd=CONTRACTS, env=env, stdout=subprocess.DEVNULL).returncode != 0:
        sys.exit("forge stopped before the end (often the public RPC losing a transaction): run `make deploy RESUME=1`")
    configure(json.loads(raw.read_text()))  # no-op when forge finished everything
    _write(target, raw)


def _write(target: Path, raw: Path) -> None:
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
