"""T5 test factories (TASKS.md T5, "Tests qui doivent passer"). No tests here; imported by the other test_t5_* files.

- load_attack(): the 41 raw attack snapshots (fixtures/snapshots_attack.jsonl if it exists, else build_attack_series()).
- make_reacted_series(): same series with our reaction from block 45201814.
- make_alert_r1(), make_decision_r1(no_reaction=False): the R1 alert and decision of block 45201812.
- FakeStore: in-memory Store (2.10), with generation.
- run_series(manager, snapshots, at): adds each snapshot then calls manager.handle.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from backend import settings
from backend.models import (
    Action,
    Alert,
    Decision,
    PositionSnapshot,
    ReserveSnapshot,
    Snapshot,
    TokenSnapshot,
    VaultStatus,
)
from backend.tests.test_t4_fixtures import (  # same world as the T4 factory (TASKS.md 2.2)
    ADDRESSES,
    DECIMALS,
    INITIAL,
    LTV,
    PRICES,
    VAULT,
    VAULT_SUPPLIED,
    FakeStore,
    _rates,
)

FIRST_BLOCK = 45201800
LAST_BLOCK = 45201880
FORGED_BLOCK = 45201812
REACTION_BLOCK = 45201814
T0 = datetime(2026, 10, 11, 8, 0, 0, tzinfo=timezone.utc)  # block 45201800; 2 s per block -> 45201812 = 08:00:24Z

# Raw attack, no reaction. (block, kind, deployment, asset, whole tokens).
# lend-eth WETH liquidity: 800 -> 600 (824) -> 500 (826) -> 300 (832) -> 100 (836) -> 0 (838 and after).
SERIES_EVENTS = [
    (45201812, "forged_mint", None, "rsETH", 5_000),
    (45201814, "collateral", "lend-eth", "rsETH", 5_000),
    (45201824, "borrow", "lend-eth", "WETH", 200),
    (45201826, "borrow", "lend-eth", "WETH", 100),
    (45201832, "borrow", "lend-eth", "WETH", 100),
    (45201832, "bot_withdraw", "lend-eth", "WETH", 100),
    (45201836, "borrow", "lend-eth", "WETH", 100),
    (45201836, "bot_withdraw", "lend-eth", "WETH", 100),
    (45201838, "borrow", "lend-eth", "WETH", 100),
    (45201878, "freeze", "lend-eth", "rsETH", 0),
]


def at_time(block: int) -> datetime:
    return T0 + timedelta(seconds=2 * (block - FIRST_BLOCK))


def _snapshot(block: int) -> Snapshot:
    state = {dep: {a: dict(v) for a, v in assets.items()} for dep, assets in INITIAL.items()}
    frozen: set[tuple[str, str]] = set()
    supply, backing = 1_200, 1_200
    for ev_block, kind, dep, asset, amount in SERIES_EVENTS:
        if ev_block > block:
            continue
        if kind == "forged_mint":
            supply += amount
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
                utilization_bps=util, supply_apy_bps=supply_apy, borrow_apy_bps=borrow_apy, ltv_bps=LTV[asset],
                borrowable=asset != "rsETH", frozen=(dep, asset) in frozen, paused=False, price_usd=PRICES[asset],
            ))
            held = VAULT_SUPPLIED.get((dep, asset))
            if held:
                withdrawable = min(held, available)
                positions.append(PositionSnapshot(
                    wallet=VAULT, deployment_id=dep, asset=asset, supplied=units(asset, held),
                    withdrawable_now=units(asset, withdrawable), withdrawable_ratio_bps=withdrawable * 10000 // held,
                    value_usd=float(held * PRICES[asset]), withdrawable_usd=float(withdrawable * PRICES[asset]),
                ))
    tokens = [
        TokenSnapshot(symbol="USDC", address=ADDRESSES["USDC"], decimals=6, total_supply=units("USDC", 10_000_000),
                      price_usd=1.0),
        TokenSnapshot(symbol="WETH", address=ADDRESSES["WETH"], decimals=18, total_supply=units("WETH", 10_000),
                      price_usd=2500.0),
        TokenSnapshot(symbol="rsETH", address=ADDRESSES["rsETH"], decimals=18, total_supply=units("rsETH", supply),
                      backing=units("WETH", backing), backing_ratio_bps=backing * 10000 // supply, price_usd=2500.0),
    ]
    return Snapshot(
        network="fuji", chain_id=43113, block_number=block, block_time=at_time(block), source="fixture",
        reserves=reserves, tokens=tokens, positions=positions,
        vault=VaultStatus(address=VAULT, deposits_paused=False, idle_balances={"USDC": "0", "WETH": "0", "rsETH": "0"}),
    )


def build_attack_series() -> list[Snapshot]:
    """Synthetic raw attack series: 41 snapshots, blocks 45201800..45201880, one every 2 blocks, no reaction.

    Same world as the T4 factory (TASKS.md 2.2): vault 150 WETH + 400,000 USDC on lend-eth,
    100 WETH + 300,000 USDC on lend-avax (1,325,000 USD); prices USDC 1, WETH 2,500, rsETH 2,500.
    - rsETH backing 10000 bps up to 45201810, 1935 bps (1,200 / 6,200) from 45201812.
    - lend-eth WETH liquidity 800 -> 600 (824) -> 500 (826) -> 300 (832) -> 100 (836) -> 0 (838+);
      the vault WETH position there is stuck (375,000 USD at risk) from 45201838.
    - rsETH reserve frozen on lend-eth at 45201878. lend-avax untouched.
    - block_time: 2 s per block, 45201812 -> 2026-10-11T08:00:24Z.
    Note: between 45201816 and 45201834 the T4 factory follows a slightly different borrow schedule;
    both agree on the blocks the T4 tests use (812, 826, 836, 838).
    """
    return [_snapshot(b) for b in range(FIRST_BLOCK, LAST_BLOCK + 1, 2)]


def load_attack() -> list[Snapshot]:
    """The 41 raw snapshots: fixtures/snapshots_attack.jsonl if it exists, else build_attack_series()."""
    path = settings.FIXTURES_DIR / "snapshots_attack.jsonl"
    if path.exists():
        return [Snapshot.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    return build_attack_series()


def make_reacted_series() -> list[Snapshot]:
    """Copy of the raw series with our reaction: from 45201814 nothing left in the markets, all in the vault."""
    reacted = []
    for s in load_attack():
        if s.block_number >= REACTION_BLOCK:
            positions = [p.model_copy(update={"supplied": "0", "withdrawable_now": "0", "withdrawable_ratio_bps": 10000,
                                              "value_usd": 0.0, "withdrawable_usd": 0.0}) for p in s.positions]
            vault = s.vault.model_copy(update={"deposits_paused": True, "idle_balances": {
                "WETH": "250000000000000000000", "USDC": "700000000000"}})
            s = s.model_copy(update={"positions": positions, "vault": vault})
        reacted.append(s)
    return reacted


def make_alert_r1() -> Alert:
    return Alert(
        id="ALT-fuji-45201812-R1_BACKING_DROP-global-rsETH", rule_id="R1_BACKING_DROP", severity="critical",
        network="fuji", deployment_id=None, asset="rsETH", block_number=FORGED_BLOCK,
        block_time=at_time(FORGED_BLOCK), detected_at=at_time(FORGED_BLOCK) + timedelta(seconds=2),
        title="rsETH backing below threshold",
        explanation="rsETH backing fell to 19.4 % (1,200 WETH backing for 6,200 rsETH supply).",
        metrics={"backing_ratio_bps": 1935, "backing": 1200.0, "total_supply": 6200.0, "threshold_bps": 9900,
                 "exposed_deployments": "lend-eth,lend-avax"},
        exposure_usd=1325000.0, rules_version="sha256:test",
    )


def make_alert(rule_id: str, severity: str, block: int, deployment_id: str | None, asset: str | None,
               exposure_usd: float, title: str | None = None) -> Alert:
    return Alert(
        id=f"ALT-fuji-{block}-{rule_id}-{deployment_id or 'global'}-{asset or 'all'}", rule_id=rule_id,
        severity=severity, network="fuji", deployment_id=deployment_id, asset=asset, block_number=block,
        block_time=at_time(block), detected_at=at_time(block) + timedelta(seconds=2),
        title=title or f"{rule_id} on {deployment_id}/{asset}", explanation=f"{rule_id} test alert.", metrics={},
        exposure_usd=exposure_usd, rules_version="sha256:test",
    )


EW_ORDER = [("lend-eth", "WETH", "150000000000000000000"), ("lend-eth", "USDC", "400000000000"),
            ("lend-avax", "WETH", "100000000000000000000"), ("lend-avax", "USDC", "300000000000")]


def make_decision_r1(no_reaction: bool = False) -> Decision:
    """DEC-fuji-45201812-1 with the 8 actions of 2.8, notes in the T4 formats."""
    created = at_time(FORGED_BLOCK) + timedelta(seconds=2)  # 08:00:26Z

    def done(i: int) -> datetime:
        return created + timedelta(seconds=2 * i)

    actions = [
        Action(type="NOTIFY", mode="auto", status="executed", executed_at=done(0), note="channels: log,webhook,sns"),
        Action(type="PAUSE_DEPOSITS", mode="auto", status="executed", tx_hash="0x" + "01" * 32, executed_at=done(1)),
    ]
    for i, (dep, asset, amount) in enumerate(EW_ORDER, start=2):
        params = {"deployment_id": dep, "asset": asset}
        if no_reaction:
            actions.append(Action(type="EMERGENCY_WITHDRAW", mode="auto", status="skipped", params=params,
                                  executed_at=done(i), note="no liquidity"))
        else:
            actions.append(Action(type="EMERGENCY_WITHDRAW", mode="auto", status="executed", params=params,
                                  tx_hash="0x" + f"{i:02x}" * 32, amount=amount, executed_at=done(i)))
    actions += [
        Action(type="OPEN_INCIDENT", mode="auto", status="executed", executed_at=done(6),
               note="delegated to incident manager"),
        Action(type="UNPAUSE_DEPOSITS", mode="human", status="pending_approval"),
    ]
    return Decision(
        id="DEC-fuji-45201812-1", created_at=created, network="fuji", block_number=FORGED_BLOCK,
        alert_ids=[make_alert_r1().id], severity="critical", exposure_usd=1325000.0, withdrawable_usd=1325000.0,
        exit_cost_bps=0, matrix_cell="critical|exposure>=1k|exit_possible",
        rationale="critical alert(s) R1_BACKING_DROP with $1,325,000 exposed: 7 automatic action(s), 1 awaiting approval.",
        actions=actions, inputs_hash="0x" + "aa" * 32, rules_version="sha256:test", playbook_version="sha256:test",
        record_hash="0x" + "bb" * 32, anchor_tx="0x" + "cc" * 32, anchor_block=45201816,
    )


def make_decision_r2_high(block: int = 45201826) -> tuple[Decision, Alert]:
    """R2 high on lend-eth WETH: NOTIFY, PAUSE (already paused), EMERGENCY_WITHDRAW pending, OPEN_INCIDENT."""
    alert = make_alert("R2_LIQUIDITY_DROP", "high", block, "lend-eth", "WETH", 375000.0,
                       title="WETH liquidity dropped on lend-eth")
    created = at_time(block) + timedelta(seconds=2)
    return Decision(
        id=f"DEC-fuji-{block}-1", created_at=created, network="fuji", block_number=block, alert_ids=[alert.id],
        severity="high", exposure_usd=375000.0, withdrawable_usd=375000.0, matrix_cell="high|exposure>=1k|exit_possible",
        rationale="high alert(s) R2_LIQUIDITY_DROP with $375,000 exposed: 3 automatic action(s), 1 awaiting approval.",
        actions=[
            Action(type="NOTIFY", mode="auto", status="executed", executed_at=created, note="channels: log"),
            Action(type="PAUSE_DEPOSITS", mode="auto", status="skipped", note="already paused"),
            Action(type="EMERGENCY_WITHDRAW", mode="human", status="pending_approval",
                   params={"deployment_id": "lend-eth", "asset": "WETH"}),
            Action(type="OPEN_INCIDENT", mode="auto", status="executed", executed_at=created,
                   note="delegated to incident manager"),
        ],
        inputs_hash="0x" + "ad" * 32, rules_version="sha256:test", playbook_version="sha256:test",
        record_hash="0x" + "be" * 32, anchor_tx=None, anchor_block=None,
    ), alert


def make_decision_warning(block: int = 45201836) -> tuple[Decision, Alert]:
    alert = make_alert("R3_UTILIZATION_HIGH", "warning", block, "lend-eth", "WETH", 375000.0)
    return Decision(
        id=f"DEC-fuji-{block}-1", created_at=at_time(block) + timedelta(seconds=2), network="fuji", block_number=block,
        alert_ids=[alert.id], severity="warning", exposure_usd=375000.0, withdrawable_usd=250000.0,
        matrix_cell="warning|exposure>=1k|exit_possible",
        rationale="warning alert(s) R3_UTILIZATION_HIGH with $375,000 exposed: 1 automatic action(s), 0 awaiting approval.",
        actions=[Action(type="NOTIFY", mode="auto", status="executed", note="channels: log")],
        inputs_hash="0x" + "ae" * 32, rules_version="sha256:test", playbook_version="sha256:test",
    ), alert


def run_series(manager, snapshots: list[Snapshot], at: dict | None = None):
    """Adds each snapshot to manager.store, then calls handle (with [], [] outside the blocks given in `at`)."""
    at = at or {}
    result = None
    for s in snapshots:
        manager.store.add_snapshot(s)
        decisions, alerts = at.get(s.block_number, ([], []))
        result = manager.handle(decisions, alerts, s)
    return result


def run_reacted_incident(monkeypatch, store: FakeStore | None = None, bedrock_model_id: str = ""):
    """T5-17 setup: reacted series, R1 decision at 45201812, llm_async=False. LLM disabled unless bedrock_model_id.

    Returns (incident, store)."""
    from backend.incidents import IncidentManager

    monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", bedrock_model_id)
    store = store or FakeStore()
    manager = IncidentManager(store, llm_async=False)
    run_series(manager, make_reacted_series(), at={FORGED_BLOCK: ([make_decision_r1()], [make_alert_r1()])})
    (incident,) = store.incidents()
    return incident, store


def dump(obj) -> str:
    return json.dumps(obj.model_dump(mode="json"), indent=2)
