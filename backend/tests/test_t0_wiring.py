"""T0-07: main.py wires engine -> responder -> incidents, with the real module of a task when it exists."""
from __future__ import annotations

from backend import main


def test_components_loaded() -> None:
    assert set(main.SOURCES) >= {"engine (T3)", "responder (T4)", "executor (T4)", "incidents (T5)",
                                 "api/state (T3)", "api/response (T4)", "api/incidents (T5)", "api/demo (T2)", "api/metrics (T7)"}
    assert set(main.SOURCES.values()) <= {"real", "fallback"}


def test_fallback_wiring() -> None:
    if main.SOURCES["engine (T3)"] == "fallback":
        assert main.responder.handle in main.engine.handlers
    if main.SOURCES["responder (T4)"] == "fallback":
        assert main.incidents.handle in main.responder.handlers
