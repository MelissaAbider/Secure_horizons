from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, localcontext

from fastapi import APIRouter, HTTPException, Query, Response

from backend import engine, fixtures, rules, settings
from backend.collector import ratio_bps
from backend.models import Alert, Health, SeriesPoint, Snapshot, StateResponse
from backend.store import store

router = APIRouter(tags=["state"])
log = logging.getLogger("backend.api.state")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _identity(s: Snapshot) -> tuple:
    return s.network, s.chain_id, s.vault.address.lower(), s.source


def _history(source, limit=2000) -> list[Snapshot]:
    rows = source.snapshots(limit=2000)
    if not rows:
        return []
    result = [rows[-1]]
    for s in reversed(rows[:-1]):
        if _identity(s) != _identity(result[-1]) or s.block_number > result[-1].block_number:
            break
        if s.block_number == result[-1].block_number:
            if s != result[-1]:
                raise ValueError("Conflicting historical snapshots")
            continue
        result.append(s)
        if len(result) >= limit:
            break
    return list(reversed(result))[-limit:]


def current_evaluation(source, cfg=None, history=None) -> rules.Evaluation:
    cfg = rules.load_rules() if cfg is None else cfg
    try:
        history = _history(source) if history is None else history
        if not history:
            return rules.evaluate_snapshot([], cfg)
        latest = history[-1]
        status_matches = (engine.STATUS.last_block == latest.block_number
                          and engine.STATUS.store_generation == getattr(source, "generation", 0))
        if engine.maintenance_flag_path().exists() or (status_matches and engine.STATUS.maintenance):
            return rules.Evaluation(issues=["Maintenance: detection suspended"], unavailable_rules=set(rules.RULE_IDS))
        if status_matches and engine.STATUS.window_start_block is not None:
            history = [s for s in history if s.block_number >= engine.STATUS.window_start_block]
        return rules.evaluate_snapshot(history[-cfg["window_snapshots"]:], cfg)
    except ValueError:
        return rules.Evaluation(issues=["Invalid or inconsistent snapshot history"], unavailable_rules=set(rules.RULE_IDS))


def _coverage(latest, report, cfg):
    issues = list(report.issues)
    if latest is not None and latest.block_time.utcoffset() is None:
        issues.append("Invalid snapshot timestamp")
    elif latest is not None and latest.source == "live":
        age = (utcnow() - latest.block_time).total_seconds()
        if age > cfg["max_snapshot_age_s"]:
            issues.append("Live snapshot is stale")
        if age < -cfg["max_future_skew_s"]:
            issues.append("Live snapshot timestamp is in the future")
    return issues


def _headers(response: Response, issues: list[str], mode="observed") -> None:
    response.headers["X-Monitoring-Status"] = "degraded" if issues else mode
    response.headers["X-Monitoring-Issues"] = json.dumps(issues, ensure_ascii=True)
    response.headers["Access-Control-Expose-Headers"] = "X-Monitoring-Status, X-Monitoring-Issues"


def _effective_positions(s: Snapshot):
    positions = []
    with localcontext() as context:
        context.prec = 110
        for p in s.positions:
            supplied = int(p.supplied)
            amount = rules.effective_withdrawable(s, p)
            value = Decimal(str(p.value_usd))
            withdrawable_usd = float((value * Decimal(amount) / Decimal(supplied)).quantize(Decimal("0.01"))) if supplied else 0.0
            positions.append(p.model_copy(update={"withdrawable_now": str(amount),
                                                   "withdrawable_ratio_bps": ratio_bps(amount, supplied),
                                                   "withdrawable_usd": withdrawable_usd}))
    return positions


def compute_totals(s: Snapshot) -> dict[str, float]:
    rules.validate_snapshot(s)
    tokens = {t.symbol: t for t in s.tokens}
    with localcontext() as context:
        context.prec = 110
        idle = Decimal(0)
        for symbol, balance in s.vault.idle_balances.items():
            t = tokens.get(symbol)
            if t is None:
                log.warning("Idle asset is outside the configured token inventory")
                continue
            idle += Decimal(int(balance)) * Decimal(str(t.price_usd)) / Decimal(10**t.decimals)
        positions = _effective_positions(s)
        value = sum((Decimal(str(p.value_usd)) for p in positions), Decimal(0))
        withdrawable = sum((Decimal(str(p.withdrawable_usd)) for p in positions), Decimal(0))
        totals = {"value_usd": value + idle, "withdrawable_usd": withdrawable,
                  "idle_usd": idle, "at_risk_usd": max(value - withdrawable, Decimal(0))}
        return {name: float(amount.quantize(Decimal("0.01"))) for name, amount in totals.items()}


def _risk(report: rules.Evaluation, issues: list[str]) -> str:
    severities = [a.severity for a in report.alerts]
    severities.append("warning" if issues else "info")
    return max(severities, key=rules.SEVERITY_RANK.__getitem__)


def compute_risk_level(source) -> str:
    report = current_evaluation(source)
    return _risk(report, report.issues)


@router.get("/health", response_model=Health)
def health(response: Response) -> Health:
    if settings.USE_FIXTURES:
        _headers(response, [], "fixture")
        return Health.model_validate(fixtures.load("health.json"))
    cfg = rules.load_rules()
    latest = store.latest_snapshot()
    report = current_evaluation(store, cfg)
    issues = _coverage(latest, report, cfg)
    if not engine.STATUS.running:
        issues.append("Monitoring engine is not running")
    if not engine.STATUS.rpc_ok:
        issues.append("RPC collection is not healthy")
    if engine.STATUS.handler_error:
        issues.append("An alert handler failed")
    if engine.STATUS.backpressure:
        issues.append("Alert dispatch is backpressured")
    _headers(response, issues)
    return Health(status="degraded" if issues else "ok", network=latest.network if latest else settings.NETWORK,
                  chain_id=latest.chain_id if latest else settings.CHAIN_ID, block_number=latest.block_number if latest else 0,
                  rpc_ok=engine.STATUS.rpc_ok, engine_running=engine.STATUS.running, version="0.1.0")


@router.get("/state", response_model=StateResponse)
def get_state(response: Response) -> StateResponse:
    if settings.USE_FIXTURES:
        _headers(response, [], "fixture")
        return StateResponse.model_validate(fixtures.load("state.json"))
    try:
        rows = _history(store)
    except ValueError:
        raise HTTPException(503, detail="invalid snapshot history") from None
    if not rows:
        raise HTTPException(503, detail="no snapshot yet")
    latest = rows[-1]
    cfg = rules.load_rules()
    report = current_evaluation(store, cfg, rows)
    issues = _coverage(latest, report, cfg)
    if any(symbol not in {t.symbol for t in latest.tokens} for symbol in latest.vault.idle_balances):
        issues.append("Unknown idle asset omitted from valuation")
    _headers(response, issues)
    try:
        totals = compute_totals(latest)
    except ValueError:
        raise HTTPException(503, detail="invalid snapshot") from None
    incident = next((i.id for i in store.incidents() if i.status != "resolved"), None)
    return StateResponse(network=latest.network, chain_id=latest.chain_id, block_number=latest.block_number,
                         block_time=latest.block_time, updated_at=engine.STATUS.last_update or latest.block_time,
                         risk_level=_risk(report, issues), open_incident_id=incident, vault=latest.vault,
                         positions=_effective_positions(latest), reserves=latest.reserves, tokens=latest.tokens, totals=totals)


@router.get("/series", response_model=list[SeriesPoint])
def series(deployment_id: str = "lend-eth", asset: str = "WETH", limit: int = Query(300, ge=1, le=2000)) -> list[SeriesPoint]:
    if settings.USE_FIXTURES:
        return [SeriesPoint.model_validate(p) for p in fixtures.load("series.json").get(f"{deployment_id}:{asset}", [])][-limit:]
    try:
        rows = _history(store)
    except ValueError:
        raise HTTPException(503, detail="invalid snapshot history") from None
    try:
        for s in rows:
            rules.validate_snapshot(s)
    except ValueError:
        raise HTTPException(503, detail="invalid snapshot history") from None
    result = []
    for s in rows:
        r = next((r for r in s.reserves if (r.deployment_id, r.asset) == (deployment_id, asset)), None)
        if r is None:
            continue
        p = next((p for p in s.positions if (p.deployment_id, p.asset) == (deployment_id, asset)), None)
        token = next((t for t in s.tokens if t.symbol == "rsETH"), None)
        result.append(SeriesPoint(block_number=s.block_number, block_time=s.block_time, utilization_bps=r.utilization_bps,
                                  available_liquidity=r.available_liquidity, supply_apy_bps=r.supply_apy_bps,
                                  withdrawable_ratio_bps=ratio_bps(rules.effective_withdrawable(s, p), int(p.supplied)) if p else None,
                                  backing_ratio_bps=token.backing_ratio_bps if token else None))
    return result[-limit:]


@router.get("/alerts", response_model=list[Alert])
def alerts(since_block: int = Query(0, ge=0)) -> list[Alert]:
    values = [Alert.model_validate(a) for a in fixtures.load("alerts.json")] if settings.USE_FIXTURES else store.alerts(since_block)
    unique = {a.id: a for a in values if a.block_number >= since_block}
    return sorted(unique.values(), key=lambda a: (a.block_number, a.rule_id, a.id), reverse=True)
