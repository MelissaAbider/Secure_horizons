"""T4-14, T4-15: DryRunExecutor (TASKS.md T4 3.3)."""
from backend.executor import DryRunExecutor


def test_dry_run_hash():
    first = DryRunExecutor().pause_deposits()
    second = DryRunExecutor().pause_deposits()
    assert first["status"] == "executed"
    assert first["tx_hash"].startswith("0xdry")
    assert len(first["tx_hash"]) == 69
    assert first["tx_hash"] == second["tx_hash"]


def test_dry_run_idempotent():
    executor = DryRunExecutor()
    assert executor.pause_deposits()["status"] == "executed"
    again = executor.pause_deposits()
    assert (again["status"], again["note"]) == ("skipped", "already paused")
    assert executor.emergency_withdraw("lend-eth", "USDC")["status"] == "executed"
    again = executor.emergency_withdraw("lend-eth", "USDC")
    assert (again["status"], again["note"]) == ("skipped", "no position left")
