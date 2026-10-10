from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from backend import rules, settings
from backend.models import Alert, Snapshot

log = logging.getLogger("backend.engine")


@dataclass
class EngineStatus:
    running: bool = False
    rpc_ok: bool = False
    rpc_url: str = ""
    last_block: int = 0
    last_update: datetime | None = None
    last_error: str | None = None
    consecutive_errors: int = 0
    maintenance: bool = False
    pending_handlers: int = 0


STATUS = EngineStatus()


def maintenance_flag_path() -> Path:
    return settings.DATA_DIR / "runtime" / settings.NETWORK / "maintenance.flag"


class Engine:
    def __init__(self, store, cfg: dict | None = None, clock: Callable[[], datetime] | None = None):
        self.store = store
        self.cfg = cfg or rules.load_rules()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.window: deque[Snapshot] = deque(maxlen=self.cfg["window_snapshots"])
        self.latch = rules.AlertLatch()
        self.handlers: list[Callable[[list[Alert], Snapshot], None]] = []
        self._generation = getattr(store, "generation", 0)
        self._last_block = 0
        self._maintenance = False
        self._stopped = False

    def on_alerts(self, handler: Callable[[list[Alert], Snapshot], None]) -> None:
        self.handlers.append(handler)

    def reset(self) -> None:
        self.window.clear()
        self.latch.reset()
        self._last_block = 0

    def in_maintenance(self) -> bool:
        return maintenance_flag_path().exists()

    def ingest(self, snapshot: Snapshot) -> list[Alert]:
        generation = getattr(self.store, "generation", 0)
        if generation != self._generation:
            self.reset()
            self._generation = generation
        if snapshot.block_number == self._last_block:
            return []
        if self._last_block and snapshot.block_number < self._last_block:
            self.reset()
        self._last_block = snapshot.block_number
        if self.in_maintenance():
            self.store.add_snapshot(snapshot)
            self._maintenance = STATUS.maintenance = True
            return []
        if self._maintenance:
            self.reset()
            self._last_block = snapshot.block_number
            self._maintenance = STATUS.maintenance = False
        self.window.append(snapshot)
        candidates = rules.evaluate_all(list(self.window), self.cfg)
        new = [alert.model_copy(update={"detected_at": self.clock()}) for alert in self.latch.filter(candidates)]
        self.store.add_snapshot(snapshot)
        if new:
            self.store.add_alerts(new)
        return new

    def process(self, snapshot: Snapshot) -> list[Alert]:
        new = self.ingest(snapshot)
        for handler in self.handlers if new else []:
            try:
                handler(new, snapshot)
            except Exception:
                log.exception("alert handler failed")
        return new

    def stop(self) -> None:
        self._stopped = True

    async def run_forever(self) -> None:
        from backend.collector import build_snapshot
        from backend.chain import w3

        STATUS.running = True
        STATUS.rpc_url = settings.RPC_URL
        client = w3()
        while not self._stopped:
            try:
                head = await asyncio.to_thread(lambda: client.eth.block_number)
                if head > self._last_block:
                    snapshot = await asyncio.to_thread(build_snapshot, head, client)
                    new = await asyncio.to_thread(self.ingest, snapshot)
                    for handler in self.handlers if new else []:
                        await asyncio.to_thread(handler, new, snapshot)
                STATUS.rpc_ok = True
                STATUS.consecutive_errors = 0
                STATUS.last_block = head
                STATUS.last_update = self.clock()
            except Exception as exc:
                STATUS.rpc_ok = False
                STATUS.last_error = str(exc)[:200]
                STATUS.consecutive_errors += 1
                log.warning("monitor error: %s", exc)
            await asyncio.sleep(settings.POLL_INTERVAL_S)
        STATUS.running = False


def replay(path: Path) -> list[Alert]:
    from backend.store import Store

    engine = Engine(Store(runtime_dir=settings.DATA_DIR / "replay"))
    alerts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        alerts.extend(engine.process(Snapshot.model_validate_json(line)))
    return alerts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    if args.replay:
        for alert in replay(args.replay):
            print(alert.block_number, alert.rule_id, alert.severity, alert.deployment_id or "global", alert.asset, alert.exposure_usd, alert.explanation)
    elif args.loop:
        from backend.store import store
        asyncio.run(Engine(store).run_forever())


if __name__ == "__main__":
    main()
