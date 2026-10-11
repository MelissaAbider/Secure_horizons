"""T0-04: main.py imports, and mounts the router of every task module that exists."""
from __future__ import annotations

import importlib.util

from backend import main


def test_main_mounts_existing_routers() -> None:
    paths = set(main.app.openapi()["paths"])
    expected = {"response": "/api/decisions", "state": "/api/state", "incidents": "/api/incidents", "demo": "/api/demo/attack", "metrics": "/api/metrics"}
    for name, path in expected.items():
        exists = importlib.util.find_spec(f"backend.api.{name}") is not None
        assert (path in paths) == exists, name
