"""T4-01 to T4-10: playbook and pure planning (TASKS.md T4 3.1, 3.2)."""
from backend.responder import assess, load_playbook, plan_actions
from backend.tests.test_t4_fixtures import load_attack, make_alert, r1_alert


def _playbook() -> dict:
    return load_playbook()[0]


def _sig(actions):
    return [(a.type, a.mode, a.status) for a in actions]


def _with_position(snapshot, deployment_id, asset, **changes):
    positions = [p.model_copy(update=changes) if (p.deployment_id, p.asset) == (deployment_id, asset) else p
                 for p in snapshot.positions]
    return snapshot.model_copy(update={"positions": positions})


def _with_paused_vault(snapshot):
    return snapshot.model_copy(update={"vault": snapshot.vault.model_copy(update={"deposits_paused": True})})


def test_playbook_loads():
    playbook, version, text = load_playbook()
    assert playbook["min_exposure_usd"] == 1000
    assert version.startswith("sha256:")
    assert len(version) == 71
    assert "matrix" in text


def test_plan_r1_critical_attack():
    snap = load_attack(45201812)
    alert = r1_alert(snap)
    actions = plan_actions([alert], snap, _playbook())
    assert _sig(actions) == [
        ("NOTIFY", "auto", "planned"),
        ("PAUSE_DEPOSITS", "auto", "planned"),
        *[("EMERGENCY_WITHDRAW", "auto", "planned")] * 4,
        ("OPEN_INCIDENT", "auto", "planned"),
        ("UNPAUSE_DEPOSITS", "human", "pending_approval"),
    ]
    assert [a.params for a in actions[2:6]] == [
        {"deployment_id": "lend-eth", "asset": "USDC"},
        {"deployment_id": "lend-eth", "asset": "WETH"},
        {"deployment_id": "lend-avax", "asset": "USDC"},
        {"deployment_id": "lend-avax", "asset": "WETH"},
    ]
    assert all(a.params == {} for a in actions[:2] + actions[6:])
    assert all(a.amount is None and a.tx_hash is None and a.executed_at is None for a in actions)
    result = assess([alert], snap, _playbook())
    assert result["exposure_usd"] == 1325000.0
    assert result["withdrawable_usd"] == 1325000.0
    assert result["matrix_cell"] == "critical|exposure>=1k|exit_possible"


def test_plan_r2_high():
    snap = load_attack(45201826)
    alert = make_alert("R2_LIQUIDITY_DROP", "high", snap, "lend-eth", "WETH", 375000.0)
    actions = plan_actions([alert], snap, _playbook())
    assert _sig(actions) == [
        ("NOTIFY", "auto", "planned"),
        ("PAUSE_DEPOSITS", "auto", "planned"),
        ("EMERGENCY_WITHDRAW", "human", "pending_approval"),
        ("OPEN_INCIDENT", "auto", "planned"),
    ]
    assert actions[2].params == {"deployment_id": "lend-eth", "asset": "WETH"}
    assert assess([alert], snap, _playbook())["exposure_usd"] == 375000.0


def test_plan_warning_notify_only():
    snap = load_attack(45201836)
    alert = make_alert("R3_UTILIZATION_HIGH", "warning", snap, "lend-eth", "WETH", 375000.0)
    assert _sig(plan_actions([alert], snap, _playbook())) == [("NOTIFY", "auto", "planned")]


def test_plan_below_min_exposure():
    snap = _with_position(load_attack(45201836), "lend-eth", "WETH", value_usd=500.0)
    for severity in ("high", "critical"):
        alert = make_alert("R4_POSITION_STUCK", severity, snap, "lend-eth", "WETH", 500.0)
        assert _sig(plan_actions([alert], snap, _playbook())) == [("NOTIFY", "auto", "planned")]
    high = make_alert("R4_POSITION_STUCK", "high", snap, "lend-eth", "WETH", 500.0)
    assert assess([high], snap, _playbook())["matrix_cell"] == "high|exposure<1k|exit_possible"


def test_plan_info_empty():
    snap = load_attack(45201826)
    alert = make_alert("R5_RESERVE_FROZEN", "info", snap, "lend-eth", "rsETH", 775000.0)
    assert plan_actions([alert], snap, _playbook()) == []


def test_plan_critical_no_liquidity():
    snap = load_attack(45201838)
    alert = make_alert("R4_POSITION_STUCK", "critical", snap, "lend-eth", "WETH", 375000.0)
    actions = plan_actions([alert], snap, _playbook())
    assert _sig(actions) == [
        ("NOTIFY", "auto", "planned"),
        ("PAUSE_DEPOSITS", "auto", "planned"),
        ("OPEN_INCIDENT", "auto", "planned"),
        ("UNPAUSE_DEPOSITS", "human", "pending_approval"),
    ]
    assert assess([alert], snap, _playbook())["matrix_cell"] == "critical|exposure>=1k|no_liquidity"


def test_plan_already_paused():
    snap = _with_paused_vault(load_attack(45201812))
    actions = plan_actions([r1_alert(snap)], snap, _playbook())
    pause = [a for a in actions if a.type == "PAUSE_DEPOSITS"]
    assert len(pause) == 1
    assert pause[0].status == "skipped"
    assert pause[0].note == "already paused"


def test_plan_group_no_double_count():
    snap = load_attack(45201812)
    alerts = [r1_alert(snap), make_alert("R2_LIQUIDITY_DROP", "high", snap, "lend-eth", "WETH", 375000.0)]
    result = assess(alerts, snap, _playbook())
    assert result["severity"] == "critical"
    assert result["exposure_usd"] == 1325000.0
    actions = plan_actions(alerts, snap, _playbook())
    assert sum(a.type == "EMERGENCY_WITHDRAW" for a in actions) == 4


def test_plan_is_pure():
    snap = load_attack(45201812)
    alerts = [r1_alert(snap)]
    before_snap = snap.model_dump()
    before_alerts = [a.model_dump() for a in alerts]
    first = plan_actions(alerts, snap, _playbook())
    second = plan_actions(alerts, snap, _playbook())
    assert first == second
    assert assess(alerts, snap, _playbook()) == assess(alerts, snap, _playbook())
    assert snap.model_dump() == before_snap
    assert [a.model_dump() for a in alerts] == before_alerts
