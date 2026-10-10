"""Executors: dry-run (no transaction) or web3 with the guardian, owner and evidence keys (TASKS.md T4 3.3).

No method raises: any exception becomes {"status": "failed", "note": "<Type>: <message>"}.
web3 and backend.chain are imported inside Web3Executor methods so dry-run works without them.
"""
from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from typing import Literal, Optional, Protocol, TypedDict

from backend import settings

logger = logging.getLogger("t4.executor")


class ExecResult(TypedDict):
    status: Literal["executed", "failed", "skipped"]
    tx_hash: Optional[str]
    block_number: Optional[int]
    amount: Optional[str]
    note: Optional[str]


def _result(status, tx_hash=None, block_number=None, amount=None, note=None) -> ExecResult:
    return {"status": status, "tx_hash": tx_hash, "block_number": block_number, "amount": amount, "note": note}


def _failed(e: Exception) -> ExecResult:
    logger.exception("executor call failed")
    return _result("failed", note=f"{type(e).__name__}: {e}"[:200])


class Executor(Protocol):
    def pause_deposits(self) -> ExecResult: ...
    def unpause_deposits(self) -> ExecResult: ...
    def emergency_withdraw(self, deployment_id: str, asset: str) -> ExecResult: ...
    def anchor(self, record_hash: str, kind: str, uri: str) -> ExecResult: ...


class DryRunExecutor:
    """No transaction. Small state for idempotence; fake 0xdry hashes, deterministic for a fresh instance."""

    def __init__(self) -> None:
        self.paused = False
        self.withdrawn: set[tuple[str, str]] = set()
        self.seq = 0

    def _tx(self, method: str, args: list) -> tuple[str, int]:
        self.seq += 1
        digest = hashlib.sha256(f"{method}|{json.dumps(args)}|{self.seq}".encode()).hexdigest()
        return "0xdry" + digest, self.seq

    def pause_deposits(self) -> ExecResult:
        try:
            if self.paused:
                return _result("skipped", note="already paused")
            self.paused = True
            tx, block = self._tx("pause_deposits", [])
            return _result("executed", tx, block)
        except Exception as e:  # noqa: BLE001
            return _failed(e)

    def unpause_deposits(self) -> ExecResult:
        try:
            if not self.paused:
                return _result("skipped", note="not paused")
            self.paused = False
            tx, block = self._tx("unpause_deposits", [])
            return _result("executed", tx, block)
        except Exception as e:  # noqa: BLE001
            return _failed(e)

    def emergency_withdraw(self, deployment_id: str, asset: str) -> ExecResult:
        try:
            if (deployment_id, asset) in self.withdrawn:
                return _result("skipped", note="no position left")
            self.withdrawn.add((deployment_id, asset))
            tx, block = self._tx("emergency_withdraw", [deployment_id, asset])
            return _result("executed", tx, block)  # amount None: the Responder fills withdrawable_now
        except Exception as e:  # noqa: BLE001
            return _failed(e)

    def anchor(self, record_hash: str, kind: str, uri: str) -> ExecResult:
        try:
            from backend import evidence

            anchors = evidence.read_anchors()
            if record_hash in anchors:
                prev = anchors[record_hash]
                return _result("skipped", prev.get("tx_hash"), prev.get("block_number"), note="already anchored")
            tx, block = self._tx("anchor", [record_hash, kind, uri])
            anchors[record_hash] = {"tx_hash": tx, "block_number": block, "kind": kind, "uri": uri}
            evidence.write_anchors(anchors)
            return _result("executed", tx, block)
        except Exception as e:  # noqa: BLE001
            return _failed(e)


def _revert_reason(e: Exception) -> str:
    message = getattr(e, "message", None) or str(e)
    return str(message).replace("execution reverted: ", "")[:200]


class Web3Executor:
    """Guardian key: pause and emergency withdraw only. Owner key: unpause. Evidence key: anchor."""

    def _send(self, fn, sender) -> ExecResult:
        from web3.exceptions import ContractLogicError

        from backend import chain

        try:
            fn.call({"from": sender.address})
        except ContractLogicError as e:
            return _result("failed", note=_revert_reason(e))
        try:
            receipt = chain.send(fn, sender)
        except ContractLogicError as e:
            return _result("failed", note=_revert_reason(e))
        if receipt["status"] != 1:
            return _result("failed", receipt["tx_hash"], receipt["block_number"], note="reverted")
        return _result("executed", receipt["tx_hash"], receipt["block_number"])

    def pause_deposits(self) -> ExecResult:
        try:
            from backend import chain

            vault = chain.vault()
            if vault.functions.depositsPaused().call():
                return _result("skipped", note="already paused")
            return self._send(vault.functions.pauseDeposits(), chain.account("guardian"))
        except Exception as e:  # noqa: BLE001
            return _failed(e)

    def unpause_deposits(self) -> ExecResult:
        try:
            from backend import chain

            vault = chain.vault()
            if not vault.functions.depositsPaused().call():
                return _result("skipped", note="not paused")
            return self._send(vault.functions.unpauseDeposits(), chain.account("owner"))  # owner-only
        except Exception as e:  # noqa: BLE001
            return _failed(e)

    def emergency_withdraw(self, deployment_id: str, asset: str) -> ExecResult:
        try:
            from backend import chain

            vault = chain.vault()
            market = chain.lending(deployment_id)
            asset_addr = chain.load_deployment()["assets"][asset]
            supplied = market.functions.getUserSupplied(vault.address, asset_addr).call()
            if supplied == 0:
                return _result("skipped", note="no position left")
            reserve = next(r for r in market.functions.getReservesData().call() if r[0].lower() == asset_addr.lower())
            liquidity = reserve[3]  # availableLiquidity
            if liquidity == 0:
                return _result("skipped", note="no liquidity")
            res = self._send(vault.functions.emergencyWithdraw(market.address, asset_addr), chain.account("guardian"))
            if res["status"] != "executed":
                return res
            amount = min(supplied, liquidity)
            try:
                receipt = chain.w3().eth.get_transaction_receipt(res["tx_hash"])
                events = vault.events.EmergencyWithdrawal().process_receipt(receipt)
                if events:
                    amount = events[0]["args"]["amount"]
            except Exception:  # noqa: BLE001
                logger.exception("could not read EmergencyWithdrawal event")
            return {**res, "amount": str(amount)}
        except Exception as e:  # noqa: BLE001
            return _failed(e)

    def anchor(self, record_hash: str, kind: str, uri: str) -> ExecResult:
        try:
            from backend import chain

            registry = chain.registry()
            h = bytes.fromhex(record_hash[2:])
            block = registry.functions.anchoredAt(h).call()
            if block > 0:
                return _result("skipped", block_number=block, note="already anchored")
            return self._send(registry.functions.anchor(h, kind, uri), chain.account("evidence"))
        except Exception as e:  # noqa: BLE001
            return _failed(e)


def make_executor() -> Executor:
    return DryRunExecutor() if settings.DRY_RUN_ACTIONS else Web3Executor()


@lru_cache(maxsize=1)
def get_executor() -> Executor:
    """Singleton shared by the Responder (main.py) and api/response.py. Tests call get_executor.cache_clear()."""
    return make_executor()
