# T0 SHIM (branch Adam-(T4,-T5)): provisional, to be replaced by the real T0.
"""T0 shim: backend/chain.py offline parts (no web3 needed)."""
import json

import pytest

from backend import settings


def test_import_without_web3():
    import backend.chain  # noqa: F401


def test_load_deployment(tmp_path, monkeypatch):
    from backend import chain

    path = tmp_path / "local.json"
    monkeypatch.setattr(settings, "DEPLOYMENTS_FILE", path)
    with pytest.raises(FileNotFoundError):
        chain.load_deployment()
    path.write_text(json.dumps({"network": "local", "assets": {}}), encoding="utf-8")
    assert chain.load_deployment()["network"] == "local"
    path.write_text(json.dumps({"network": "fuji", "assets": {}}), encoding="utf-8")
    assert chain.load_deployment()["network"] == "fuji"  # re-read on every call


def test_load_abi(tmp_path, monkeypatch):
    from backend import chain

    monkeypatch.setattr(settings, "ABI_DIR", tmp_path)
    (tmp_path / "Vault.json").write_text(json.dumps([{"type": "function", "name": "x"}]), encoding="utf-8")
    (tmp_path / "Bridge.json").write_text(json.dumps({"abi": [{"type": "event"}]}), encoding="utf-8")
    assert chain.load_abi("Vault") == [{"type": "function", "name": "x"}]
    assert chain.load_abi("Bridge") == [{"type": "event"}]


def test_explorer_tx():
    from backend import chain

    assert chain.explorer_tx("0xab") == f"{settings.EXPLORER_URL}/tx/0xab"
