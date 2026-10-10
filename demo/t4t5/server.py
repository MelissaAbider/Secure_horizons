"""Local T4 + T5 demo UI (dry-run, offline). Not part of the product: a show-and-tell page for the team.

Run:  make t4t5-ui   then open http://localhost:8000/demo
Serves the real T4/T5 API of backend.main under /api, plus demo-only scenario routes under /demo/api.
No transaction is sent (DryRunExecutor), no AWS call (SNS/S3/Bedrock variables forced empty).
"""
from __future__ import annotations

import io
import os
import shutil
from contextlib import redirect_stdout
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO_DATA = ROOT / "data" / "demo_t4t5"

# Must be set before any backend import (settings reads the environment at import time).
os.environ.update({
    "DATA_DIR": str(DEMO_DATA), "DRY_RUN_ACTIONS": "true", "USE_FIXTURES": "false", "ENGINE_ENABLED": "false",
    "SNS_TOPIC_ARN": "", "EVIDENCE_BUCKET": "", "BEDROCK_MODEL_ID": "",
})  # ALERT_WEBHOOK_URL is kept from .env: the R1 decision's NOTIFY posts to Discord if it is set

from fastapi import HTTPException  # noqa: E402
from fastapi.responses import FileResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from backend import cli, evidence, settings  # noqa: E402
from backend import main as app_main  # noqa: E402
from backend import responder as responder_mod  # noqa: E402
from backend.executor import get_executor  # noqa: E402
from backend.store import store  # noqa: E402
from backend.tests.test_t5_factories import (  # noqa: E402
    FORGED_BLOCK, REACTION_BLOCK, load_attack, make_alert_r1, make_reacted_series)

evidence.EVIDENCE_DIR = DEMO_DATA / "evidence"
STATIC = Path(__file__).parent / "static"
TAMPER_FIELD = "decision.actions.2.params.asset"

app = app_main.app
SERIES = make_reacted_series()  # 41 snapshots; our reaction (positions back in the vault) from block 45201814
RAW = {s.block_number: s for s in load_attack()}  # same market, but a passive treasury that never reacts
LAST_BLOCK = SERIES[-1].block_number
_state = {"cursor": 0, "engine": app_main.engine, "incidents": app_main.incidents}


def _rewire() -> None:
    """Fresh dry-run executor + fresh Responder/IncidentManager on the shared store."""
    get_executor.cache_clear()
    engine, _responder, incidents = app_main.wire(store)
    _state.update(engine=engine, incidents=incidents)


def _status() -> dict:
    latest = store.latest_snapshot()
    nxt = SERIES[_state["cursor"]].block_number if _state["cursor"] < len(SERIES) else None
    return {"block": latest.block_number if latest else None, "snapshots": len(store.snapshots(limit=2000)),
            "next_block": nxt, "attack_triggered": bool(store.decisions()), "generation": store.generation,
            "dry_run": settings.DRY_RUN_ACTIONS}


def _reset() -> dict:
    store.reset()
    shutil.rmtree(evidence.EVIDENCE_DIR, ignore_errors=True)
    evidence.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    _rewire()
    _state["cursor"] = 0
    for s in SERIES:  # calm market before the forged mint (blocks 45201800..45201810)
        if s.block_number >= FORGED_BLOCK:
            break
        store.add_snapshot(s)
        _state["cursor"] += 1
    return _status()


@app.get("/demo", include_in_schema=False)
def demo_page():
    return FileResponse(STATIC / "index.html")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/demo")


app.mount("/demo/static", StaticFiles(directory=STATIC), name="demo-static")


@app.get("/demo/api/status")
def status() -> dict:
    return _status()


@app.post("/demo/api/reset")
def reset() -> dict:
    return _reset()


@app.post("/demo/api/trigger-r1")
def trigger_r1() -> dict:
    if store.decisions():
        raise HTTPException(409, "attack already triggered: click Reset first")
    snap = next(s for s in SERIES if s.block_number == FORGED_BLOCK)
    wall_clock = responder_mod._now
    responder_mod._now = lambda: snap.block_time + timedelta(seconds=2)  # scenario clock (like make decision-demo)
    try:
        _state["engine"].inject([make_alert_r1()], snap)
    finally:
        responder_mod._now = wall_clock
    _state["cursor"] = SERIES.index(snap) + 1
    d = store.decisions()
    return {**_status(), "decision_id": d[0].id if d else None,
            "incident_id": store.incidents()[0].id if store.incidents() else None}


def _human(base: str, decimals: int) -> float:
    return int(base) / 10 ** decimals


def _positions_view(s) -> list[dict]:
    dec = {(r.deployment_id, r.asset): r.decimals for r in s.reserves}
    return [{"deployment_id": p.deployment_id, "asset": p.asset,
             "amount": _human(p.supplied, dec.get((p.deployment_id, p.asset), 18)),
             "withdrawable": _human(p.withdrawable_now, dec.get((p.deployment_id, p.asset), 18)),
             "value_usd": p.value_usd, "withdrawable_usd": p.withdrawable_usd}
            for p in s.positions if int(p.supplied) > 0]


@app.get("/demo/api/world")
def world() -> dict:
    """Plain view of the scenario for the UI: our vault, the same vault if it had not reacted, the markets."""
    latest = store.latest_snapshot()
    if latest is None:
        return {"block": None}
    ours = latest
    if store.decisions() and latest.block_number < REACTION_BLOCK:  # withdrawals already executed by T4
        ours = next(s for s in SERIES if s.block_number == REACTION_BLOCK)
    prices = {t.symbol: t.price_usd for t in latest.tokens}
    decimals = {t.symbol: t.decimals for t in latest.tokens}
    idle = {sym: _human(v, decimals.get(sym, 18)) for sym, v in ours.vault.idle_balances.items() if int(v) > 0}
    idle_usd = sum(amount * prices.get(sym, 0) for sym, amount in idle.items())
    passive = RAW.get(latest.block_number, latest)
    passive_pos = _positions_view(passive)
    ours_pos = _positions_view(ours)
    rseth = next((t for t in latest.tokens if t.symbol == "rsETH"), None)
    markets = [{"deployment_id": r.deployment_id, "asset": r.asset,
                "supplied": _human(r.total_supplied, r.decimals), "borrowed": _human(r.total_borrowed, r.decimals),
                "available": _human(r.available_liquidity, r.decimals), "utilization_bps": r.utilization_bps,
                "frozen": r.frozen, "paused": r.paused, "collateral": _human(r.total_collateral, r.decimals),
                "borrowable": r.borrowable}
               for r in latest.reserves]
    return {
        "block": latest.block_number, "block_time": latest.block_time.isoformat().replace("+00:00", "Z"),
        "first_block": SERIES[0].block_number, "last_block": LAST_BLOCK, "forged_block": FORGED_BLOCK,
        "rseth": None if rseth is None else {
            "backing_ratio_bps": rseth.backing_ratio_bps, "supply": _human(rseth.total_supply, rseth.decimals),
            "backing": _human(rseth.backing or "0", 18)},
        "ours": {"positions": ours_pos, "idle": idle, "idle_usd": round(idle_usd, 2),
                 "deposits_paused": ours.vault.deposits_paused,
                 "safe_usd": round(idle_usd + sum(p["withdrawable_usd"] for p in ours_pos), 2),
                 "stuck_usd": round(sum(p["value_usd"] - p["withdrawable_usd"] for p in ours_pos), 2)},
        "passive": {"positions": passive_pos,
                    "safe_usd": round(sum(p["withdrawable_usd"] for p in passive_pos), 2),
                    "stuck_usd": round(sum(p["value_usd"] - p["withdrawable_usd"] for p in passive_pos), 2)},
        "markets": markets,
    }


@app.post("/demo/api/replay-r1")
def replay_r1() -> dict:
    """T4-17: inject the very same R1 alert again. T4 must not create a second decision, T5 not a second incident."""
    if not store.decisions():
        raise HTTPException(409, "trigger the attack first")
    snap = next(s for s in SERIES if s.block_number == FORGED_BLOCK)
    _state["engine"].inject([make_alert_r1()], snap)
    return {"decisions": len(store.decisions()), "incidents": len(store.incidents())}


@app.post("/demo/api/advance")
def advance(n: int = 10) -> dict:
    if not store.decisions():
        raise HTTPException(409, "trigger the attack first")
    added = 0
    while added < n and _state["cursor"] < len(SERIES):
        s = SERIES[_state["cursor"]]
        store.add_snapshot(s)
        _state["incidents"].handle([], [], s)  # T5 recomputes status, amounts, timeline
        _state["cursor"] += 1
        added += 1
    return {**_status(), "added": added}


@app.get("/demo/api/report.pdf/{incident_id}")
def report_pdf(incident_id: str):
    """DORA initial notification draft as PDF (backend.dora_pdf, T5), built from the live incident."""
    from fastapi.responses import Response

    from backend.dora_pdf import render_pdf
    incident = store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(404, "incident not found")
    _state["incidents"].refresh(incident_id)
    incident = store.get_incident(incident_id)
    return Response(render_pdf(incident), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{incident_id}-DORA-draft.pdf"'})


@app.get("/demo/api/email-status")
def email_status() -> dict:
    from backend import mailer
    return {"configured": mailer.configured()}


@app.post("/demo/api/email-report/{incident_id}")
def email_report(incident_id: str, body: dict) -> dict:
    """E-mail the DORA draft PDF to the address typed in the page (allow-listed, rate-limited, SMTP from .env)."""
    from backend import mailer
    from backend.dora_pdf import render_pdf
    incident = store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(404, "incident not found")
    _state["incidents"].refresh(incident_id)
    incident = store.get_incident(incident_id)
    try:
        return mailer.send_report(incident, str(body.get("email", "")), render_pdf(incident))
    except mailer.MailError as e:
        raise HTTPException(e.status, e.detail) from None


@app.get("/demo/api/discord-preview/{decision_id}")
def discord_preview(decision_id: str) -> dict:
    """The JSON posted to Discord for this decision (the webhook URL itself is never returned)."""
    from backend.notify import build_discord_payload
    d = store.get_decision(decision_id)
    if d is None:
        raise HTTPException(404, "decision not found")
    alerts = [a for a in store.alerts() if a.id in d.alert_ids]
    return {"webhook_configured": bool(settings.ALERT_WEBHOOK_URL), "payload": build_discord_payload(d, alerts)}


def _run_cli(*argv: str) -> dict:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(list(argv))
    return {"exit_code": code, "output": buf.getvalue().strip()}


@app.post("/demo/api/tamper/{decision_id}")
def tamper(decision_id: str) -> dict:
    return _run_cli("tamper", decision_id, "--field", TAMPER_FIELD, "--value", "DAI")


@app.post("/demo/api/restore/{decision_id}")
def restore(decision_id: str) -> dict:
    return _run_cli("restore", decision_id)


@app.post("/demo/api/verify-cli/{decision_id}")
def verify_cli(decision_id: str) -> dict:
    return _run_cli("verify", decision_id)


_reset()
