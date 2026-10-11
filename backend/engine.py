from __future__ import annotations

import argparse
import asyncio
import logging
import tempfile
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from backend import consensus, rules, settings
from backend.agent_monitor import AgentMonitor
from backend.ml_monitor import MLMonitor
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
    data_issues: list[str] = field(default_factory=list)
    handler_error: str | None = None
    backpressure: bool = False
    window_start_block: int | None = None
    store_generation: int | None = None
    layers_alerting: list[str] = field(default_factory=list)
    layer_agreement: str = "none"
    agent_available: bool = False
    ml_available: bool = False

    @property
    def detection_ok(self) -> bool:
        return bool(self.running and self.rpc_ok and not self.data_issues and not self.handler_error
                    and not self.backpressure and not self.maintenance)


STATUS = EngineStatus()


def maintenance_flag_path() -> Path:
    return settings.DATA_DIR / "runtime" / settings.NETWORK / "maintenance.flag"


class Engine:
    def __init__(self, store, cfg: dict | None = None, clock: Callable[[], datetime] | None = None,
                 agent: AgentMonitor | None = None, ml: MLMonitor | None = None,
                 extra_layers: list[Callable[[list[Snapshot]], tuple[list[Alert], list[str]]]] | None = None):
        self.store = store
        self.cfg = deepcopy(cfg) if cfg is not None else rules.load_rules()
        rules.validate_config(self.cfg)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        # Independent surveillance layers consulted after the rules on the same window: R7 LLM agent and any
        # other callable(window) -> (alerts, issues), e.g. the R6 ML corroborator. Their failures never block ingestion.
        self._explicit_agent, self._explicit_ml = agent is not None, ml is not None
        self.agent = agent if agent is not None else AgentMonitor(self.cfg)
        self.ml = ml if ml is not None else MLMonitor()
        self.extra_layers = list(extra_layers or [])
        self.last_consensus = consensus.ConsensusResult()
        self.window: deque[Snapshot] = deque(maxlen=self.cfg["window_snapshots"])
        self.latch = rules.AlertLatch()
        self.handlers: list[Callable[[list[Alert], Snapshot], None]] = []
        self._generation = getattr(store, "generation", 0)
        self._last_block: int | None = None
        self._identity: tuple | None = None
        self._latest: Snapshot | None = None
        self._epoch = 0
        self._maintenance = False
        self._stopped = False
        self._agent_task: asyncio.Task | None = None
        self._agent_context: dict[int, tuple[list[Alert], Snapshot, int]] = {}
        self.last_evaluation = rules.Evaluation()

    def on_alerts(self, handler: Callable[[list[Alert], Snapshot], None]) -> None:
        self.handlers.append(handler)

    def reset(self) -> None:
        self.window.clear()
        self.latch.reset()
        self._last_block = None
        self._latest = None
        self._identity = None
        self._agent_context.clear()
        self._epoch += 1
        self.last_evaluation = rules.Evaluation()

    def in_maintenance(self) -> bool:
        return maintenance_flag_path().exists()

    def _check_freshness(self, snapshot: Snapshot) -> None:
        if snapshot.source != "live":
            return
        age = (self.clock() - snapshot.block_time).total_seconds()
        if age > self.cfg["max_snapshot_age_s"]:
            raise ValueError("Live snapshot is stale")
        if age < -self.cfg["max_future_skew_s"]:
            raise ValueError("Live snapshot timestamp is in the future")

    def ingest(self, snapshot: Snapshot, include_agent: bool = True, include_ml: bool = True) -> list[Alert]:
        try:
            rules.validate_snapshot(snapshot)
            self._check_freshness(snapshot)
            identity = (snapshot.network, snapshot.chain_id, snapshot.vault.address.lower(), snapshot.source)
            generation = getattr(self.store, "generation", 0)
            maintenance = self.in_maintenance()
            reset = (generation != self._generation or identity != self._identity or self._maintenance != maintenance
                     or (self._last_block is not None and snapshot.block_number < self._last_block))
            if not reset and snapshot.block_number == self._last_block:
                if snapshot != self._latest:
                    raise ValueError("Conflicting snapshot for the same block; canonical block hash required")
                return []
            prospective = [] if reset else list(self.window)
            prospective.append(snapshot)
            evaluation = rules.Evaluation(issues=["Maintenance: detection suspended"], unavailable_rules=set(rules.RULE_IDS)) if maintenance else rules.evaluate_snapshot(prospective, self.cfg)
        except ValueError:
            STATUS.rpc_ok = False
            STATUS.last_error = "Invalid, stale or inconsistent snapshot; detection not updated"
            raise
        next_latch = rules.AlertLatch() if reset else deepcopy(self.latch)
        candidates, layer_issues = list(evaluation.alerts), []
        if not maintenance:
            layers = ([self.agent.evaluate] if include_agent else []) + ([self.ml.evaluate] if include_ml else []) + self.extra_layers
            for layer in layers:
                try:
                    alerts, issues = layer(prospective)
                except Exception as exc:
                    alerts, issues = [], [f"Surveillance layer failed ({type(exc).__name__}); verdict unavailable"]
                candidates.extend(alerts)
                layer_issues.extend(issues)

        resolved = consensus.resolve(candidates) if not maintenance else consensus.ConsensusResult()
        new = [] if maintenance else [a.model_copy(update={"detected_at": self.clock()})
                                     for a in next_latch.filter(resolved.forwarded, evaluation.unavailable_rules)]
        try:
            self.store.add_snapshot(snapshot)
            if new:
                self.store.add_alerts(new)
        except Exception:
            STATUS.rpc_ok = False
            STATUS.last_error = "Snapshot/alert persistence failed; ingestion remains retryable"
            raise
        if reset:
            self.reset()
        self.latch = next_latch
        self._generation, self._identity = generation, identity
        self._maintenance = STATUS.maintenance = maintenance
        self.last_evaluation = evaluation
        self.last_consensus = resolved
        if not include_agent and not maintenance:
            self._agent_context[snapshot.block_number] = (candidates, snapshot.model_copy(deep=True), self._epoch)
            while len(self._agent_context) > self.cfg["window_snapshots"]:
                del self._agent_context[min(self._agent_context)]
        STATUS.data_issues = list(evaluation.issues) + layer_issues
        STATUS.layers_alerting = sorted(resolved.layers_alerting)
        STATUS.layer_agreement = resolved.agreement
        STATUS.agent_available = self.agent.status.available
        STATUS.ml_available = self.ml.status.available
        if not maintenance:
            self.window.append(snapshot.model_copy(deep=True))
        self._last_block = snapshot.block_number
        self._latest = snapshot.model_copy(deep=True)
        STATUS.last_block = snapshot.block_number
        STATUS.last_update = self.clock()
        STATUS.window_start_block = self.window[0].block_number if self.window else None
        STATUS.store_generation = generation
        for issue in evaluation.issues:
            log.warning("Detection coverage: %s", issue)
        return new

    def _handle(self, alerts: list[Alert], snapshot: Snapshot) -> None:
        for handler in self.handlers:
            try:
                handler([a.model_copy(deep=True) for a in alerts], snapshot.model_copy(deep=True))
            except Exception as exc:
                STATUS.handler_error = type(exc).__name__
                log.error("Alert handler failed (%s); alerts remain stored", type(exc).__name__)

    def process(self, snapshot: Snapshot) -> list[Alert]:
        # Replays/tests are deterministic by default and never call external/live layers unless explicitly injected.
        new = self.ingest(snapshot, include_agent=self._explicit_agent, include_ml=self._explicit_ml)
        if new:
            self._handle(new, snapshot)
        return new

    def stop(self) -> None:
        self._stopped = True

    def _make_client(self, url: str):
        from web3 import Web3
        return Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 20}))

    def _head(self, client) -> int:
        if client.eth.chain_id != settings.CHAIN_ID:
            raise ValueError("RPC chain ID mismatch")
        return client.eth.block_number

    def _deployment_key(self):
        from backend.chain import load_deployment
        dep = load_deployment()
        return dep.get("deployed_at_block"), dep["contracts"]["TreasuryVault"]

    def _build_snapshot(self, head, client):
        from backend.collector import build_snapshot
        return build_snapshot(head, client)

    def _accept_agent_result(self, block: int, result: tuple[list[Alert], list[str]]) -> tuple[list[Alert], Snapshot | None]:
        """Merge a late R7 verdict with rule/ML candidates from the exact observed block, persist and latch it."""
        context = self._agent_context.pop(block, None)
        if context is None:
            return [], None
        base, snapshot, epoch = context
        alerts, issues = result
        if epoch != self._epoch or self.in_maintenance() or getattr(self.store, "generation", 0) != self._generation:
            return [], None
        resolved = consensus.resolve([*base, *alerts])
        next_latch = deepcopy(self.latch)
        new = [a.model_copy(update={"detected_at": self.clock()}) for a in next_latch.filter(resolved.forwarded)]
        if new:
            self.store.add_alerts(new)
        self.latch = next_latch
        self.last_consensus = resolved
        STATUS.layers_alerting = sorted(resolved.layers_alerting)
        STATUS.layer_agreement = resolved.agreement
        STATUS.agent_available = self.agent.status.available
        STATUS.data_issues = [i for i in STATUS.data_issues if not i.startswith("R7 agent")] + list(issues)
        return new, snapshot

    async def _poll_agent(self) -> tuple[list[Alert], Snapshot | None]:
        if self._agent_task is None or not self._agent_task.done():
            return [], None
        block, result = await self._agent_task
        self._agent_task = None
        return self._accept_agent_result(block, result)

    def _schedule_agent(self, window: list[Snapshot]) -> None:
        if not self.agent.status.enabled or self._agent_task is not None:
            return
        block = window[-1].block_number

        async def run():
            return block, await asyncio.to_thread(self.agent.evaluate, window)

        self._agent_task = asyncio.create_task(run())

    async def _dispatcher(self) -> None:
        while True:
            item = await self._queue.get()
            STATUS.pending_handlers = self._queue.qsize()
            try:
                if item is None:
                    return
                epoch, generation, alerts, snapshot = item
                if epoch != self._epoch or generation != getattr(self.store, "generation", 0) or self.in_maintenance():
                    continue
                await asyncio.to_thread(self._handle, alerts, snapshot)
            finally:
                self._queue.task_done()

    async def run_forever(self) -> None:
        STATUS.running = True
        STATUS.rpc_ok = False
        STATUS.handler_error = None
        STATUS.rpc_url = "primary"
        self._stopped = False
        self._queue = asyncio.Queue(maxsize=self.cfg["handler_queue_size"])
        dispatcher = asyncio.create_task(self._dispatcher())
        fallback, fallback_ticks, deployed = False, 0, None
        client = None
        try:
            while not self._stopped:
                try:
                    agent_new, agent_snapshot = await self._poll_agent()
                    if agent_new and agent_snapshot is not None:
                        STATUS.backpressure = self._queue.full()
                        await self._queue.put((self._epoch, self._generation, agent_new, agent_snapshot))
                        STATUS.backpressure = False
                    if client is None:
                        client = self._make_client(settings.RPC_FALLBACK_URL if fallback else settings.RPC_URL)
                    key = await asyncio.to_thread(self._deployment_key)
                    if key != deployed:
                        self.reset()
                        deployed = key
                    head = await asyncio.to_thread(self._head, client)
                    if self._last_block is not None and head < self._last_block:
                        raise ValueError("RPC is behind the last observed block; canonical reset not established")
                    changed = (self._last_block is None or head != self._last_block
                               or self._generation != getattr(self.store, "generation", 0)
                               or self._maintenance != self.in_maintenance())
                    if changed:
                        snapshot = await asyncio.to_thread(self._build_snapshot, head, client)
                        if (snapshot.source != "live" or snapshot.chain_id != settings.CHAIN_ID
                                or snapshot.network != settings.NETWORK or snapshot.block_number != head):
                            raise ValueError("Collector snapshot identity mismatch")
                        new = await asyncio.to_thread(self.ingest, snapshot, False)
                        self._schedule_agent([s.model_copy(deep=True) for s in self.window])
                        if new:
                            STATUS.backpressure = self._queue.full()
                            await self._queue.put((self._epoch, self._generation, new, snapshot.model_copy(deep=True)))
                            STATUS.backpressure = False
                            STATUS.pending_handlers = self._queue.qsize()
                    elif self._latest is not None:
                        self._check_freshness(self._latest)
                    # If blocks arrived while Bedrock was busy, analyze the latest observed window next; never queue an
                    # unbounded backlog of stale LLM calls.
                    if self.window:
                        self._schedule_agent([s.model_copy(deep=True) for s in self.window])
                    STATUS.rpc_ok = True
                    STATUS.consecutive_errors = 0
                    STATUS.last_error = None
                except Exception as exc:
                    STATUS.rpc_ok = False
                    STATUS.last_error = type(exc).__name__
                    STATUS.consecutive_errors += 1
                    log.warning("Monitor failed (%s); no healthy detection claim", type(exc).__name__)
                    if STATUS.consecutive_errors >= 3 and settings.RPC_FALLBACK_URL and not fallback:
                        fallback, fallback_ticks, client = True, 0, None
                        STATUS.rpc_url = "fallback"
                if fallback:
                    fallback_ticks += 1
                    if fallback_ticks >= 30:
                        fallback_ticks = 0
                        try:
                            primary = self._make_client(settings.RPC_URL)
                            primary_head = await asyncio.to_thread(self._head, primary)
                            if self._last_block is None or primary_head >= self._last_block:
                                client, fallback = primary, False
                                STATUS.rpc_url = "primary"
                        except Exception:
                            pass
                await asyncio.sleep(settings.POLL_INTERVAL_S)
        finally:
            self._epoch += 1
            if self._agent_task is not None:
                self._agent_task.cancel()
                self._agent_task = None
            self.agent.close()
            await self._queue.put(None)
            await dispatcher
            STATUS.running = False
            STATUS.rpc_ok = False
            STATUS.pending_handlers = 0
            STATUS.backpressure = False


def replay(path: Path) -> list[Alert]:
    from backend.store import Store

    with tempfile.TemporaryDirectory(prefix="secure-horizons-replay-") as folder:
        engine = Engine(Store(runtime_dir=Path(folder)))
        alerts = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
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
