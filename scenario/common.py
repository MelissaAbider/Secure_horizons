"""Shared scenario helpers (TASKS.md T2 step 1). Owner: T2.

Every transaction goes through tx(), which prints one step line (JSON with --json) so the demo API can follow the run.
"""
from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterator, Optional, Union

from backend import chain, settings
from backend.models import RunRecord

DECIMALS = {"USDC": 6, "WETH": 18, "rsETH": 18}
DEPLOYMENTS = ("lend-eth", "lend-avax")
LENDING_ASSETS = ("USDC", "WETH")
MAX_UINT = 2**256 - 1
MIN_ROLE_BALANCE_WEI = 5 * 10**15  # 0.005 AVAX on fuji, below the 0.01 AVAX that make fund-roles sends


class ScenarioError(Exception):
    """Scenario failure: exit code 1."""


class PreflightError(Exception):
    """Chain not in the expected state before starting: exit code 2."""


def now() -> datetime:
    return datetime.now(timezone.utc)


def units(amount: Union[int, str, Decimal], symbol: str) -> int:
    """Human units to base units: units(150, "WETH") == 150 * 10**18."""
    return int(Decimal(str(amount)) * 10 ** DECIMALS[symbol])


def human(amount: int, symbol: str) -> str:
    value = Decimal(amount) / 10 ** DECIMALS[symbol]
    return f"{value.normalize():,f} {symbol}"


def new_run_id(kind: str, seed: int, at: Optional[datetime] = None) -> str:
    return f"RUN-{(at or now()).strftime('%Y%m%d%H%M%S')}-{kind}-{seed}"


def asset_address(symbol: str) -> str:
    return chain.load_deployment()["assets"][symbol]


def roles() -> dict:
    return chain.load_deployment()["roles"]


def reserve(deployment_id: str, symbol: str, block: Union[int, str] = "latest") -> dict:
    """One reserve of getReservesData(), snake_case keys, ints and bools."""
    market = chain.lending(deployment_id)
    assets = market.functions.getAssets().call(block_identifier=block)
    data = market.functions.getReservesData().call(block_identifier=block)
    r = data[[a.lower() for a in assets].index(asset_address(symbol).lower())]
    return {
        "total_supplied": r[1], "total_borrowed": r[2], "available_liquidity": r[3], "utilization_bps": r[4],
        "total_collateral": r[7], "ltv_bps": r[8], "borrowable": r[9], "frozen": r[10], "paused": r[11],
    }


class Emitter:
    """Prints one line per step: JSON with --json (read by backend/api/demo.py and T7), readable text otherwise."""

    def __init__(self, run_id: str, json_mode: bool, stream=None):
        self.run_id = run_id
        self.json_mode = json_mode
        self.stream = stream or sys.stdout

    def __call__(self, step: str, msg: str, status: str = "ok", block: Optional[int] = None,
                 tx_hash: Optional[str] = None) -> None:
        if self.json_mode:
            line = json.dumps({"run_id": self.run_id, "step": step, "status": status, "block": block,
                               "tx_hash": tx_hash, "msg": msg, "at": now().isoformat()})
        else:
            extra = ", ".join(f"{k}={v}" for k, v in (("block", block), ("tx", tx_hash)) if v is not None)
            line = f"[{step}] {msg}" + (f" ({extra})" if extra else "") + ("" if status == "ok" else f" [{status}]")
        print(line, file=self.stream, flush=True)


def tx(fn, sender, step: str, emit: Emitter, msg: str = "", expect_revert: Union[bool, str] = False) -> Optional[dict]:
    """Send a transaction and emit its step.

    A revert is detected by estimate_gas before anything is sent. expect_revert=True (or a substring of the expected
    revert reason) turns it into a "blocked" step and returns None; any other revert raises ScenarioError.
    """
    from web3.exceptions import ContractLogicError

    try:
        receipt = chain.send(fn, sender)
    except ContractLogicError as exc:
        reason = getattr(exc, "message", None) or str(exc)
        if expect_revert is True or (isinstance(expect_revert, str) and expect_revert in reason):
            emit(step, f"{msg}: reverted ({reason})", status="blocked")
            return None
        emit(step, f"{msg}: reverted ({reason})", status="failed")
        raise ScenarioError(f"{step}: {reason}") from exc
    if receipt["status"] != 1:
        emit(step, f"{msg}: transaction failed", status="failed", block=receipt["block_number"], tx_hash=receipt["tx_hash"])
        raise ScenarioError(f"{step}: transaction {receipt['tx_hash']} failed")
    emit(step, msg, block=receipt["block_number"], tx_hash=receipt["tx_hash"])
    return receipt


def ensure_allowance(acct, symbol: str, spender: str, emit: Optional[Emitter] = None) -> None:
    """approve(max) once; later calls only read the allowance."""
    token = chain.token(symbol)
    if token.functions.allowance(acct.address, spender).call() >= 2**255:
        return
    fn = token.functions.approve(spender, MAX_UINT)
    if emit is None:
        receipt = chain.send(fn, acct)
        if receipt["status"] != 1:
            raise ScenarioError(f"approve {symbol} failed")
    else:
        tx(fn, acct, "approve", emit, f"{acct.address[:8]} approves {symbol} for {spender[:8]}")


def treasury_supplied() -> dict[str, str]:
    """The vault's 4 lending positions, "<deployment>:<asset>" -> base units (always the 4 keys)."""
    vault = chain.vault().address
    return {
        f"{dep}:{sym}": str(chain.lending(dep).functions.getUserSupplied(vault, asset_address(sym)).call())
        for dep in DEPLOYMENTS for sym in LENDING_ASSETS
    }


def write_run_record(rec: RunRecord) -> Path:
    path = settings.DATA_DIR / "runs" / f"{rec.run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(rec.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def maintenance_flag_path() -> Path:
    return settings.DATA_DIR / "runtime" / settings.NETWORK / "maintenance.flag"


@contextmanager
def maintenance(emit: Emitter) -> Iterator[None]:
    """While the flag exists, the monitoring engine evaluates no rule (TASKS.md 2.10). Always removed on exit."""
    flag = maintenance_flag_path()
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text(f"{emit.run_id} {now().isoformat()}\n", encoding="utf-8")
    emit("maintenance_on", f"monitoring paused ({flag})", status="info")
    try:
        yield
    finally:
        flag.unlink(missing_ok=True)
        emit("maintenance_off", "monitoring resumed", status="info")


def preflight(role_names: tuple[str, ...] = (), bot_indexes: tuple[int, ...] = ()) -> None:
    """Deployment present, right chain, 3 bots, and on fuji enough test AVAX for the roles used (PreflightError)."""
    if not settings.DEPLOYMENTS_FILE.exists():
        raise PreflightError(f"{settings.DEPLOYMENTS_FILE} not found: run make deploy (NETWORK={settings.NETWORK})")
    w3 = chain.w3()
    if w3.eth.chain_id != settings.CHAIN_ID:
        raise PreflightError(f"RPC chain id {w3.eth.chain_id} != CHAIN_ID {settings.CHAIN_ID} (RPC host {settings.RPC_URL.split('/')[2]})")
    bots = chain.bot_accounts()
    if len(bots) < 3:
        raise PreflightError("3 bot keys required (BOT_PKS in .env)")
    if settings.NETWORK != "fuji":
        return
    addresses = [chain.account(r).address for r in role_names] + [bots[i].address for i in bot_indexes]
    low = [a for a in addresses if w3.eth.get_balance(a) < MIN_ROLE_BALANCE_WEI]
    if low:
        raise PreflightError(f"not enough test AVAX on {', '.join(low)}: run make fund-roles")



def run_main(fn, emit: Emitter) -> int:
    """Shared CLI wrapper: exit 0 on success, 1 on ScenarioError, 2 on PreflightError."""
    try:
        fn()
        return 0
    except PreflightError as exc:
        emit("preflight", str(exc), status="failed")
        return 2
    except ScenarioError as exc:
        emit("error", str(exc), status="failed")
        return 1
