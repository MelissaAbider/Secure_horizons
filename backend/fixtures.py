"""Loads the example data in fixtures/ (TASKS.md 2.13). Owner: T0."""
from __future__ import annotations

import json
from typing import Any

from backend import settings


def load(name: str) -> Any:
    with open(settings.FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(name: str) -> list[Any]:
    with open(settings.FIXTURES_DIR / name, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
