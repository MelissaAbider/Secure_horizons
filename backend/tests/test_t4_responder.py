"""T4-16 to T4-18: Responder.handle (TASKS.md T4 3.6)."""
from backend.executor import DryRunExecutor
from backend.responder import Responder
from backend.tests.test_t4_fixtures import (  # noqa: F401
    FakeStore,
    evidence_tmp,
    handle_r1_critical,
    load_attack,
    make_alert,
    r1_alert,
)


def test_handle_critical(evidence_tmp):
    calls = []
    decisions, alerts, snap, store = handle_r1_critical(handler=lambda *args: calls.append(args))
    assert [d.id for d in decisions] == ["DEC-fuji-45201812-1"]
    d = decisions[0]
    assert [(a.type, a.status) for a in d.actions] == [
        ("NOTIFY", "executed"),
        ("PAUSE_DEPOSITS", "executed"),
        *[("EMERGENCY_WITHDRAW", "executed")] * 4,
        ("OPEN_INCIDENT", "executed"),
        ("UNPAUSE_DEPOSITS", "pending_approval"),
    ]
    assert [a.amount for a in d.actions[2:6]] == [
        "400000000000", "150000000000000000000", "300000000000", "100000000000000000000",
    ]
    assert d.actions[0].note == "channels: log"
    assert d.actions[6].note == "delegated to incident manager"
    assert d.actions[6].params == {}
    assert len(d.record_hash) == 66
    assert d.anchor_tx.startswith("0xdry")
    assert d.anchor_block > 0
    assert d.exposure_usd == 1325000.0
    assert d.matrix_cell == "critical|exposure>=1k|exit_possible"
    assert d.rationale == ("critical alert(s) R1_BACKING_DROP with $1,325,000 exposed: "
                           "7 automatic action(s), 1 awaiting approval.")
    assert (evidence_tmp / "DEC-fuji-45201812-1.json").exists()
    assert store.get_decision(d.id) == d
    assert len(calls) == 1
    assert calls[0][0] == [d]


def test_handle_idempotent(evidence_tmp):
    store = FakeStore()
    responder = Responder(store, DryRunExecutor())
    snap = load_attack(45201812)
    alert = r1_alert(snap)
    assert len(responder.handle([alert], snap)) == 1
    assert responder.handle([alert], snap) == []
    assert len(store.decisions()) == 1

    later = load_attack(45201838)
    later = later.model_copy(update={"vault": later.vault.model_copy(update={"deposits_paused": True})})
    stuck = make_alert("R4_POSITION_STUCK", "critical", later, "lend-eth", "WETH", 375000.0)
    (d,) = responder.handle([alert, stuck], later)
    assert d.id == "DEC-fuji-45201838-1"
    assert d.alert_ids == [stuck.id]
    pause = [a for a in d.actions if a.type == "PAUSE_DEPOSITS"]
    assert [(a.status, a.note) for a in pause] == [("skipped", "already paused")]
    assert not any(a.type == "EMERGENCY_WITHDRAW" for a in d.actions)


class BoomExecutor(DryRunExecutor):
    def emergency_withdraw(self, deployment_id, asset):
        raise RuntimeError("boom")


def test_handle_survives_failures(evidence_tmp):
    (d,), _, _, store = handle_r1_critical(executor=BoomExecutor())
    withdrawals = [a for a in d.actions if a.type == "EMERGENCY_WITHDRAW"]
    assert len(withdrawals) == 4
    assert all(a.status == "failed" and "boom" in a.note for a in withdrawals)
    assert [a.status for a in d.actions if a.type == "OPEN_INCIDENT"] == ["executed"]
    assert store.get_decision(d.id) is not None
