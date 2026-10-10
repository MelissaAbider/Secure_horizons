"""T4 test mocks (TASKS.md T4 3.9). No tests here; imported by the other test_t4_* files.

- load_attack(block): Snapshot from fixtures/snapshots_attack.jsonl if the file exists,
  otherwise from build_attack_snapshot(block) (synthetic, see below).
- make_alert(...): hand-made Alert with an id in the 2.5 format.
- FakeStore: in-memory Store with the 2.10 methods.
- evidence_tmp: pytest fixture that points backend.evidence.EVIDENCE_DIR to tmp_path.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from backend import settings
from backend.models import (
    Alert,
    Decision,
    Incident,
    PositionSnapshot,
    ReserveSnapshot,
    Snapshot,
    TokenSnapshot,
    VaultStatus,
)

# ---------- Synthetic attack series (used only while fixtures/snapshots_attack.jsonl is missing) ----------

FIRST_BLOCK = 45201800
LAST_BLOCK = 45201880
FORGED_BLOCK = 45201812
T0 = datetime(2026, 10, 11, 8, 0, 0, tzinfo=timezone.utc)  # block 45201800; Fuji ~2 s per block

VAULT = "0x00000000000000000000000000000000000000a1"
ADDRESSES = {
    "USDC": "0x0000000000000000000000000000000000000c01",
    "WETH": "0x0000000000000000000000000000000000000c02",
    "rsETH": "0x0000000000000000000000000000000000000c03",
}
DECIMALS = {"USDC": 6, "WETH": 18, "rsETH": 18}
PRICES = {"USDC": 1.0, "WETH": 2500.0, "rsETH": 2500.0}
LTV = {"USDC": 8000, "WETH": 8000, "rsETH": 7500}

# Initial deployment, TASKS.md 2.2 (whole tokens). Reserve order = getAssets() order.
INITIAL = {
    "lend-eth": {
        "USDC": {"supplied": 3_000_000, "borrowed": 1_800_000, "collateral": 4_500_000},
        "WETH": {"supplied": 2_000, "borrowed": 1_200, "collateral": 0},
        "rsETH": {"supplied": 0, "borrowed": 0, "collateral": 900},
    },
    "lend-avax": {
        "USDC": {"supplied": 2_000_000, "borrowed": 1_100_000, "collateral": 3_000_000},
        "WETH": {"supplied": 1_000, "borrowed": 550, "collateral": 0},
        "rsETH": {"supplied": 0, "borrowed": 0, "collateral": 300},
    },
}
VAULT_SUPPLIED = {("lend-eth", "USDC"): 400_000, ("lend-eth", "WETH"): 150,
                  ("lend-avax", "USDC"): 300_000, ("lend-avax", "WETH"): 100}

# Default attack, no reaction from us (TASKS.md 1.2 and 2.2). (block, kind, deployment, asset, whole tokens)
ATTACK_EVENTS = [
    (45201812, "forged_mint", None, "rsETH", 5_000),
    (45201814, "collateral", "lend-eth", "rsETH", 5_000),
    (45201816, "borrow", "lend-eth", "WETH", 100),
    (45201820, "borrow", "lend-eth", "WETH", 100),
    (45201824, "borrow", "lend-eth", "WETH", 100),
    (45201828, "borrow", "lend-eth", "WETH", 100),
    (45201830, "bot_withdraw", "lend-eth", "WETH", 100),
    (45201832, "borrow", "lend-eth", "WETH", 100),
    (45201834, "bot_withdraw", "lend-eth", "WETH", 100),
    (45201838, "borrow", "lend-eth", "WETH", 100),  # lend-eth WETH liquidity reaches zero
    (45201870, "freeze", "lend-eth", "rsETH", 0),    # protocol guardian freezes rsETH
]


def _rates(borrowed: int, supplied: int) -> tuple[int, int, int]:
    """(utilization_bps, supply_apy_bps, borrow_apy_bps) with the 2.2 rate model."""
    if supplied == 0:
        return 0, 0, 100
    u = borrowed / supplied
    borrow = 100 + 300 * u / 0.8 if u <= 0.8 else 400 + 7500 * (u - 0.8) / 0.2
    return borrowed * 10000 // supplied, round(borrow * u * 0.85), round(borrow)


def build_attack_snapshot(block: int) -> Snapshot:
    """Synthetic Snapshot of the default attack at `block` (45201800..45201880), without our reaction.

    Built from the 2.2 deployment table and ATTACK_EVENTS so that the T4 test numbers hold:
    - 45201812: forged mint, rsETH backing 1,200 / 6,200; all 4 vault positions fully withdrawable (1,325,000 USD).
    - 45201826: lend-eth WETH liquidity 500 (-37.5 % vs 800), vault WETH still fully withdrawable.
    - 45201836: lend-eth WETH utilization 94.4 %, liquidity 100, vault WETH 100 / 150 withdrawable.
    - 45201838: lend-eth WETH liquidity 0, vault WETH withdrawable ratio 0.
    Replace with fixtures/snapshots_attack.jsonl once T0 ships it (load_attack switches automatically).
    """
    if not FIRST_BLOCK <= block <= LAST_BLOCK:
        raise ValueError(f"block {block} outside {FIRST_BLOCK}..{LAST_BLOCK}")
    state = {dep: {a: dict(v) for a, v in assets.items()} for dep, assets in INITIAL.items()}
    frozen: set[tuple[str, str]] = set()
    rseth_supply, rseth_backing = 1_200, 1_200
    for ev_block, kind, dep, asset, amount in ATTACK_EVENTS:
        if ev_block > block:
            break
        if kind == "forged_mint":
            rseth_supply += amount
        elif kind == "collateral":
            state[dep][asset]["collateral"] += amount
        elif kind == "borrow":
            state[dep][asset]["borrowed"] += amount
        elif kind == "bot_withdraw":
            state[dep][asset]["supplied"] -= amount
        elif kind == "freeze":
            frozen.add((dep, asset))

    def units(asset: str, whole: int) -> str:
        return str(whole * 10 ** DECIMALS[asset])

    reserves, positions = [], []
    for dep, assets in state.items():
        for asset, r in assets.items():
            available = r["supplied"] - r["borrowed"]
            util, supply_apy, borrow_apy = _rates(r["borrowed"], r["supplied"])
            reserves.append(ReserveSnapshot(
                deployment_id=dep, asset=asset, asset_address=ADDRESSES[asset], decimals=DECIMALS[asset],
                total_supplied=units(asset, r["supplied"]), total_borrowed=units(asset, r["borrowed"]),
                available_liquidity=units(asset, available), total_collateral=units(asset, r["collateral"]),
                utilization_bps=util, supply_apy_bps=supply_apy, borrow_apy_bps=borrow_apy,
                ltv_bps=LTV[asset], borrowable=asset != "rsETH", frozen=(dep, asset) in frozen, paused=False,
                price_usd=PRICES[asset],
            ))
            supplied = VAULT_SUPPLIED.get((dep, asset))
            if supplied:
                withdrawable = min(supplied, available)
                positions.append(PositionSnapshot(
                    wallet=VAULT, deployment_id=dep, asset=asset,
                    supplied=units(asset, supplied), withdrawable_now=units(asset, withdrawable),
                    withdrawable_ratio_bps=withdrawable * 10000 // supplied,
                    value_usd=float(supplied * PRICES[asset]), withdrawable_usd=float(withdrawable * PRICES[asset]),
                ))
    tokens = [
        TokenSnapshot(symbol="USDC", address=ADDRESSES["USDC"], decimals=6, total_supply=units("USDC", 10_000_000),
                      price_usd=1.0),
        TokenSnapshot(symbol="WETH", address=ADDRESSES["WETH"], decimals=18, total_supply=units("WETH", 10_000),
                      price_usd=2500.0),
        TokenSnapshot(symbol="rsETH", address=ADDRESSES["rsETH"], decimals=18,
                      total_supply=units("rsETH", rseth_supply), backing=units("WETH", rseth_backing),
                      backing_ratio_bps=rseth_backing * 10000 // rseth_supply, price_usd=2500.0),
    ]
    return Snapshot(
        network="fuji", chain_id=43113, block_number=block, block_time=T0 + timedelta(seconds=2 * (block - FIRST_BLOCK)),
        source="fixture", reserves=reserves, tokens=tokens, positions=positions,
        vault=VaultStatus(address=VAULT, deposits_paused=False, idle_balances={"USDC": "0", "WETH": "0", "rsETH": "0"}),
    )


def load_attack(block: int) -> Snapshot:
    """Snapshot of `block` from fixtures/snapshots_attack.jsonl, else the synthetic builder."""
    path = settings.FIXTURES_DIR / "snapshots_attack.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line)["block_number"] == block:
                return Snapshot.model_validate_json(line)
        raise KeyError(f"block {block} not in {path}")
    return build_attack_snapshot(block)


def make_alert(rule_id: str, severity: str, snapshot: Snapshot, deployment_id: str | None = None,
               asset: str | None = None, exposure_usd: float = 0.0) -> Alert:
    """Hand-made Alert; id ALT-<network>-<block>-<rule_id>-<deployment_id or global>-<asset or all>."""
    alert_id = f"ALT-{snapshot.network}-{snapshot.block_number}-{rule_id}-{deployment_id or 'global'}-{asset or 'all'}"
    return Alert(
        id=alert_id, rule_id=rule_id, severity=severity, network=snapshot.network,
        deployment_id=deployment_id, asset=asset, block_number=snapshot.block_number,
        block_time=snapshot.block_time, detected_at=snapshot.block_time + timedelta(seconds=2),
        title=f"{rule_id} on {deployment_id or 'global'}/{asset or 'all'}",
        explanation=f"Test alert {rule_id} ({severity}).", metrics={}, exposure_usd=exposure_usd,
        rules_version="sha256:test",
    )


def r1_alert(snapshot: Snapshot) -> Alert:
    return make_alert("R1_BACKING_DROP", "critical", snapshot, asset="rsETH", exposure_usd=1325000.0)


class FakeStore:
    """In-memory Store with the TASKS.md 2.10 methods."""

    def __init__(self) -> None:
        self.generation = 0
        self.reset()
        self.generation = 0

    def add_snapshot(self, s: Snapshot) -> None:
        self._snapshots.append(s)

    def latest_snapshot(self) -> Snapshot | None:
        return self._snapshots[-1] if self._snapshots else None

    def snapshots(self, limit: int = 500) -> list[Snapshot]:
        return self._snapshots[-limit:]

    def add_alerts(self, alerts: list[Alert]) -> None:
        self._alerts.extend(alerts)

    def alerts(self, since_block: int = 0) -> list[Alert]:
        return [a for a in reversed(self._alerts) if a.block_number >= since_block]

    def add_decision(self, d: Decision) -> None:
        self._decisions.append(d)

    def update_decision(self, d: Decision) -> None:
        self._decisions = [d if x.id == d.id else x for x in self._decisions]

    def decisions(self) -> list[Decision]:
        return list(reversed(self._decisions))

    def get_decision(self, decision_id: str) -> Decision | None:
        return next((d for d in self._decisions if d.id == decision_id), None)

    def upsert_incident(self, i: Incident) -> None:
        self._incidents = [x for x in self._incidents if x.id != i.id] + [i]

    def incidents(self) -> list[Incident]:
        return list(self._incidents)

    def get_incident(self, incident_id: str) -> Incident | None:
        return next((i for i in self._incidents if i.id == incident_id), None)

    def reset(self) -> None:
        self._snapshots: list[Snapshot] = []
        self._alerts: list[Alert] = []
        self._decisions: list[Decision] = []
        self._incidents: list[Incident] = []
        self.generation += 1


@pytest.fixture
def evidence_tmp(tmp_path, monkeypatch):
    """Evidence files go to tmp_path; dry-run, no webhook, no SNS, no S3."""
    from backend import evidence

    monkeypatch.setattr(evidence, "EVIDENCE_DIR", tmp_path)
    monkeypatch.setattr(settings, "DRY_RUN_ACTIONS", True)
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_URL", "")
    monkeypatch.setattr(settings, "SNS_TOPIC_ARN", "")
    monkeypatch.setattr(settings, "EVIDENCE_BUCKET", "")
    return tmp_path


def handle_r1_critical(store: FakeStore | None = None, executor=None, handler=None):
    """T4-16 setup: R1 critical on block 45201812 through Responder.handle. Needs evidence_tmp."""
    from backend.executor import DryRunExecutor
    from backend.responder import Responder

    store = store or FakeStore()
    responder = Responder(store, executor or DryRunExecutor())
    if handler:
        responder.on_decisions(handler)
    snap = load_attack(FORGED_BLOCK)
    alert = r1_alert(snap)
    return responder.handle([alert], snap), [alert], snap, store
