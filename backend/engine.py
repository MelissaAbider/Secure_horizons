# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""STUB T0 shim, to be replaced by T3. No detection logic.

Keeps the Engine interface T4 relies on (Engine(store), on_alerts(handler), process(snapshot), run_forever()).
inject() is SHIM-ONLY: it lets T4 + T5 be exercised end-to-end without the real engine.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from backend import settings
from backend.models import Alert, Snapshot

logger = logging.getLogger("t0shim.engine")


class Engine:
    def __init__(self, store):
        self.store = store
        self._handlers: list[Callable[[list[Alert], Snapshot], object]] = []

    def on_alerts(self, handler: Callable[[list[Alert], Snapshot], object]) -> None:
        self._handlers.append(handler)

    def process(self, snapshot: Snapshot) -> list[Alert]:
        """Stub: stores the snapshot, detects nothing."""
        self.store.add_snapshot(snapshot)
        return []

    def inject(self, alerts: list[Alert], snapshot: Snapshot) -> list[Alert]:
        """SHIM-ONLY (not part of the T3 contract): store the snapshot and the alerts, then call every subscriber
        synchronously, in subscription order. Handler exceptions are logged, never raised."""
        self.store.add_snapshot(snapshot)
        if alerts:
            self.store.add_alerts(alerts)
        for handler in self._handlers:
            try:
                handler(alerts, snapshot)
            except Exception:  # noqa: BLE001
                logger.exception("alert handler failed on block %s", snapshot.block_number)
        return alerts

    async def run_forever(self) -> None:
        """Stub loop: sleeps POLL_INTERVAL_S, reads nothing."""
        while True:
            await asyncio.sleep(settings.POLL_INTERVAL_S)
