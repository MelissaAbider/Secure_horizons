"""T5-17 to T5-23: IncidentManager (TASKS.md T5 7)."""
from datetime import datetime, timezone

from backend import settings
from backend.dora import T_9_1, T_9_4, T_9_6
from backend.incidents import IncidentManager
from backend.tests.test_t5_factories import (
    FORGED_BLOCK,
    FakeStore,
    at_time,
    load_attack,
    make_alert,
    make_alert_r1,
    make_decision_r1,
    make_decision_r2_high,
    make_decision_warning,
    make_reacted_series,
    run_reacted_incident,
    run_series,
)


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_opens_one_incident_reacted(monkeypatch):
    incident, store = run_reacted_incident(monkeypatch)
    assert incident.id == "INC-20261011-001"
    assert incident.status == "contained"
    assert incident.contained_at == utc("2026-10-11T08:01:04Z")
    assert incident.saved_usd == 1325000.0
    assert incident.at_risk_usd == 0.0
    assert incident.exposure_usd == 1325000.0
    assert incident.severity == "critical"
    assert incident.opened_at == utc("2026-10-11T08:00:26Z")
    assert incident.detected_at == utc("2026-10-11T08:00:26Z")
    assert incident.title == "rsETH backing below threshold (lend-avax, lend-eth)"
    assert incident.decision_ids == ["DEC-fuji-45201812-1"]
    assert incident.alert_ids == [make_alert_r1().id]
    assert incident.dora.is_major is True
    assert incident.dora.thresholds_met == [T_9_1, T_9_4]
    assert incident.dora.deadlines.initial_notification_due == utc("2026-10-11T12:00:26Z")
    assert incident.model_dump(mode="json")["contained_at"] == "2026-10-11T08:01:04Z"
    assert store.get_decision("DEC-fuji-45201812-1") == make_decision_r1()  # never modified


def test_no_open_incident_action(monkeypatch):
    monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", "")
    store = FakeStore()
    manager = IncidentManager(store, llm_async=False)
    decision, alert = make_decision_warning()
    snap = load_attack()[18]
    store.add_snapshot(snap)
    assert manager.handle([decision], [alert], snap) is None
    assert store.incidents() == []


def test_attaches_later_decisions_raw(monkeypatch):
    monkeypatch.setattr(settings, "BEDROCK_MODEL_ID", "")
    store = FakeStore()
    manager = IncidentManager(store, llm_async=False)
    r2, r2_alert = make_decision_r2_high(45201826)
    run_series(manager, load_attack(), at={
        FORGED_BLOCK: ([make_decision_r1(no_reaction=True)], [make_alert_r1()]),
        45201826: ([r2], [r2_alert]),
    })
    (incident,) = store.incidents()
    assert incident.decision_ids == ["DEC-fuji-45201812-1", r2.id]
    assert incident.alert_ids == [make_alert_r1().id, r2_alert.id]
    assert incident.status == "open"
    assert incident.contained_at is None
    assert incident.saved_usd == 0.0
    assert incident.at_risk_usd == 375000.0
    assert incident.dora.thresholds_met == [T_9_1, T_9_4, T_9_6]


def test_timeline(monkeypatch):
    incident, _ = run_reacted_incident(monkeypatch)
    events = incident.timeline
    assert {"alert", "decision", "action", "human", "dora"} <= {e.kind for e in events}
    keys = [(e.at, e.block_number or 0) for e in events]
    assert keys == sorted(keys)
    withdrawals = [e for e in events if e.text.startswith("Emergency withdrawal")]
    assert len(withdrawals) == 4
    assert [e.ref for e in withdrawals] == ["0x" + f"{i:02x}" * 32 for i in range(2, 6)]
    texts = [e.text for e in events]
    assert "Emergency withdrawal: 150 WETH from lend-eth to the vault (375,000 USD)" in texts
    assert "Emergency withdrawal: 400,000 USDC from lend-eth to the vault (400,000 USD)" in texts
    assert "Notification sent (log, webhook, sns)" in texts
    assert "R1_BACKING_DROP critical: rsETH backing below threshold" in texts
    assert "Decision DEC-fuji-45201812-1: critical|exposure>=1k|exit_possible" in texts
    assert "Awaiting human approval: UNPAUSE_DEPOSITS" in texts
    assert "DORA classification proposed: major (9(1), 9(4))" in texts
    assert "Incident contained: no exposed position left" in texts
    assert "WETH liquidity on lend-eth reaches zero" in texts


def _set_action(store, index, **changes):
    decision = store.get_decision("DEC-fuji-45201812-1").model_copy(deep=True)
    for key, value in changes.items():
        setattr(decision.actions[index], key, value)
    store.update_decision(decision)  # simulates T4 POST /approve


def test_human_approval_picked_up(monkeypatch):
    incident, store = run_reacted_incident(monkeypatch)
    manager = IncidentManager(store, llm_async=False)
    _set_action(store, 7, status="executed", note="approved by treasury-signer-1; ", tx_hash="0x" + "07" * 32,
                executed_at=at_time(45201880))
    texts = [e.text for e in manager.refresh(incident.id).timeline]
    assert "UNPAUSE_DEPOSITS approved by treasury-signer-1" in texts
    assert "Deposits unpaused" in texts
    assert not any(t.startswith("Awaiting human approval") for t in texts)

    _set_action(store, 7, status="rejected", note="rejected by risk-officer", tx_hash=None)
    texts = [e.text for e in manager.refresh(incident.id).timeline]
    assert "UNPAUSE_DEPOSITS rejected by risk-officer" in texts
    assert not any(t.startswith("Awaiting human approval") for t in texts)


def test_reopen_on_new_relevant_alert(monkeypatch):
    incident, store = run_reacted_incident(monkeypatch)
    manager = IncidentManager(store, llm_async=False)
    latest = store.latest_snapshot()
    alert = make_alert("R4_POSITION_STUCK", "critical", latest.block_number, "lend-avax", "USDC", 5000.0)
    reopened = manager.handle([], [alert], latest)
    assert reopened.id == incident.id
    assert reopened.status == "open"
    assert reopened.contained_at is None
    assert alert.id in reopened.alert_ids


def test_idempotent_and_resolved(monkeypatch):
    incident, store = run_reacted_incident(monkeypatch)
    manager = IncidentManager(store, llm_async=False)
    latest = store.latest_snapshot()
    again = manager.handle([make_decision_r1()], [make_alert_r1()], latest)
    assert again.decision_ids == ["DEC-fuji-45201812-1"]
    assert again.alert_ids == [make_alert_r1().id]
    assert len(store.incidents()) == 1

    store.upsert_incident(again.model_copy(update={"status": "resolved"}))
    r2, r2_alert = make_decision_r2_high(latest.block_number)
    new = manager.handle([r2], [r2_alert], latest)
    assert new.id == "INC-20261011-002"
    assert len(store.incidents()) == 2
    assert store.get_incident(incident.id).status == "resolved"
