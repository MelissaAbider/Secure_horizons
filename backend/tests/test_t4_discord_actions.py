"""Withdraw buttons on the Discord alert: signature, allow-list, fixed button ids, execution, dashboard list.
No network, no chain: Discord, the bot and the teller window are stubbed."""
import json

import pytest
from fastapi.testclient import TestClient
from nacl.signing import SigningKey

from backend import discord_actions as D
from backend import settings
from backend.alerting import Alerting
from backend.store import Store
from backend.tests.test_t5_alerting import r1, snapshots

KEY = SigningKey(bytes(range(32)))  # test-only key, generated here
ALLOWED = "111"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DRY_RUN_ACTIONS", True)
    monkeypatch.setattr(D, "_sealed_integrations", lambda: ["lend-avax:USDC", "lend-eth:USDC", "lend-eth:WETH"])
    monkeypatch.setattr(D, "_follow_up", lambda *a: None)
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", KEY.verify_key.encode().hex())
    monkeypatch.setenv("DISCORD_ALLOWED_USER_IDS", f"{ALLOWED}, 222")
    D.reset()
    yield tmp_path
    D.reset()


def click(custom_id: str, user_id: str = ALLOWED, interaction_id: str = "9001") -> dict:
    return {"id": interaction_id, "type": 3, "application_id": "42", "token": "interaction-token",
            "data": {"custom_id": custom_id}, "member": {"user": {"id": user_id, "username": "adam"}}}


def signed(body: dict) -> tuple[bytes, dict]:
    raw, ts = json.dumps(body).encode(), "1760169600"
    sig = KEY.sign(ts.encode() + raw).signature.hex()
    return raw, {"X-Signature-Ed25519": sig, "X-Signature-Timestamp": ts, "Content-Type": "application/json"}


def now(fn):
    fn()


def test_buttons_follow_the_alert_scope():
    rows = D.components([r1()])
    ids = [b["custom_id"] for row in rows for b in row["components"]]
    assert ids == ["sh:withdraw:lend-avax:USDC", "sh:withdraw:lend-eth:USDC", "sh:withdraw:lend-eth:WETH",
                   "sh:withdraw:all"]
    assert rows[0]["components"][2]["label"] == "Withdraw WETH from lend-eth"
    assert all(len(row["components"]) <= 5 for row in rows)


def test_bot_payload_has_buttons_and_no_webhook_fields():
    from backend.notify import build_alert_payload

    payload = D.with_buttons(build_alert_payload([r1()], snapshots()[45201812]), [r1()])
    assert "username" not in payload and payload["components"]
    assert payload["allowed_mentions"] == {"parse": []}
    response = next(f for f in payload["embeds"][0]["fields"] if f["name"] == "Response")
    assert "Withdraw buttons below" in response["value"]


def test_signature_check():
    raw, headers = signed({"type": 1})
    pub = KEY.verify_key.encode().hex()
    assert D.verify_signature(pub, headers["X-Signature-Ed25519"], headers["X-Signature-Timestamp"], raw)
    assert not D.verify_signature(pub, headers["X-Signature-Ed25519"], headers["X-Signature-Timestamp"], raw + b" ")
    assert not D.verify_signature(pub, "zz", headers["X-Signature-Timestamp"], raw)
    assert not D.verify_signature("", headers["X-Signature-Ed25519"], headers["X-Signature-Timestamp"], raw)


def test_ping_and_unknown_buttons():
    assert D.handle({"type": 1}) == {"type": 1}
    assert D.handle(click("sh:withdraw:lend-eth:DAI"))["data"]["flags"] == D.EPHEMERAL
    assert D.handle(click("withdraw everything to 0xabc"))["data"]["content"] == "Unknown button."
    assert D.list_actions() == []


def test_user_not_allowed_is_refused_and_listed():
    started = []
    answer = D.handle(click("sh:withdraw:lend-eth:WETH", user_id="999"), start=started.append)
    assert answer["data"]["content"].startswith("Refused") and answer["data"]["flags"] == D.EPHEMERAL
    assert started == []
    (action,) = D.list_actions()
    assert action["status"] == "refused" and action["user_id"] == "999"


def test_allowed_click_in_dry_run():
    answer = D.handle(click("sh:withdraw:lend-eth:WETH"), start=now)
    assert "Withdraw WETH from lend-eth" in answer["data"]["content"] and "dry run" in answer["data"]["content"]
    assert answer["data"]["allowed_mentions"] == {"parse": []}
    (action,) = D.list_actions()
    assert action["status"] == "simulated" and action["integrations"] == ["lend-eth:WETH"]
    assert action["results"][0]["verdict"] == "SIMULATED" and action["finished_at"].endswith("Z")
    assert D.handle(click("sh:withdraw:lend-eth:WETH"), start=now)["data"]["content"] == "Already handled."


def test_live_withdraw_all_uses_the_teller(monkeypatch):
    monkeypatch.setattr(settings, "DRY_RUN_ACTIONS", False)
    calls = []

    def teller(integration):
        calls.append(integration)
        verdict = "FAILED" if integration == "lend-eth:WETH" else "EXECUTED"
        return {"integration": integration, "verdict": verdict, "detail": None, "txs": ["0x" + "ab" * 32]}

    started = []
    D.handle(click("sh:withdraw:all"), start=started.append)
    (action,) = D.list_actions()
    assert action["status"] == "pending"
    D.execute(D.ACTIONS[0], run=teller)
    assert calls == ["lend-avax:USDC", "lend-eth:USDC", "lend-eth:WETH"]
    assert D.list_actions()[0]["status"] == "partial"
    text = D.summary(D.ACTIONS[0])
    assert "lend-eth:WETH: FAILED" in text and "requested by adam" in text
    lines = (settings.runtime_dir() / "discord_actions.jsonl").read_text().splitlines()
    assert json.loads(lines[-1])["status"] == "partial"


def test_api_routes():
    from backend import main as app_main

    client = TestClient(app_main.app)
    raw, headers = signed({"type": 1})
    assert client.post("/api/discord/interactions", content=raw, headers=headers).json() == {"type": 1}
    bad = dict(headers, **{"X-Signature-Timestamp": "1"})
    assert client.post("/api/discord/interactions", content=raw, headers=bad).status_code == 401
    raw, headers = signed(click("sh:withdraw:lend-eth:USDC", interaction_id="9002"))
    assert client.post("/api/discord/interactions", content=raw, headers=headers).json()["type"] == 4
    listed = client.get("/api/discord/actions").json()
    assert listed[0]["label"] == "Withdraw USDC from lend-eth"
    assert client.get("/api/discord/config").json() == {"buttons": False, "interactions": True, "allowed_users": 2}


def test_alert_goes_out_through_the_bot_with_buttons(tmp_path, monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "123")
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_URL", "")
    bot, hook = [], []
    alerting = Alerting(Store(runtime_dir=tmp_path / "runtime"), post=lambda *a: hook.append(a) or 204,
                        post_bot=lambda payload, file: bot.append((payload, file)) or 200)
    alerting.handle([r1()], snapshots()[45201812])
    assert hook == [] and len(bot) == 1
    payload, file = bot[0]
    assert payload["components"] and file[0].endswith("-DORA-draft.pdf")
    assert alerting.deliveries[-1].status == "sent"
