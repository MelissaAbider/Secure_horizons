"""MCP tools of the allocation agent: four read tools and one action tool. Owner: agent.

One registry (TOOLS) serves the Bedrock agent loop (backend/autopilot.py), the HTTP API (backend/api/agent.py)
and the MCP server (backend/mcp_server.py), so every client sees the same names, descriptions and JSON schemas.

- get_rules       the guaranteed rules (backend/config/agent_rules.yaml); read-only
- get_markets     lending markets from the latest on-chain snapshot: APY, liquidity, utilization, frozen/paused
- get_portfolio   the Safe: idle balances, positions, sealed integrations, value in USD
- get_alerts      active high/critical alerts and open incidents
- propose_allocation  one deposit or withdraw. The platform re-reads the chain and checks the rules (check_move,
                  pure); if allowed it executes through the teller-window module (sealed list, back to the Safe),
                  above the signature threshold it waits for a human, otherwise it is refused with reasons.

The agent holds no key and never signs: execution is the platform's teller path, as for the dashboard.
DRY_RUN_ACTIONS=true (default): an allowed move is recorded as simulated, nothing is sent.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional

import yaml

from backend import settings
from backend.models import Alert, Snapshot

log = logging.getLogger("backend.agent_tools")

RULES_PATH = settings.CONFIG_DIR / "agent_rules.yaml"
ACTIONS = ("deposit", "withdraw")
RECENT_BLOCKS = 150  # an alert without an open incident stays active this long (~5 min on Fuji)

PORTFOLIO_TTL_S = 5.0  # several tools in one cycle share one read of the Safe; any execution clears it

_LOCK = threading.Lock()
_PAPER: dict[str, Any] = {}  # paper treasury in memory (dry run without a Safe), see agent_rules.yaml
_PORTFOLIO_CACHE: dict[str, Any] = {"at": None, "value": None}
MOVES: dict[str, dict] = {}  # move id -> move with verdict and outcome (pending signatures included)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))


# ---------- context: what the platform reads before every decision ----------

def _store():
    from backend.store import store

    return store


def active_alerts(store, block: int) -> list[Alert]:
    """High/critical alerts in an open incident, or recent ones."""
    open_ids = {a for i in store.incidents() if i.status != "resolved" for a in i.alert_ids}
    return [a for a in store.alerts(0) if a.severity in ("high", "critical")
            and (a.id in open_ids or a.block_number >= block - RECENT_BLOCKS)]


def _prices(snapshot: Snapshot) -> dict[str, float]:
    prices = {t.symbol: t.price_usd for t in snapshot.tokens}
    for r in snapshot.reserves:
        prices.setdefault(r.asset, r.price_usd)
    return prices


def read_portfolio() -> dict:
    """The Safe on chain (sealed/live.py). Amounts in whole tokens (strings)."""
    from sealed import live

    s = live.status()
    if not s.get("connected"):
        return {"connected": False, "sealed_integrations": [], "idle": {}, "positions": {}}
    dec = s["decimals"]

    def tokens(asset: str, units: str) -> str:
        return str(Decimal(int(units)) / Decimal(10 ** dec[asset]))

    return {"connected": True, "safe": s["safe"], "sealed_integrations": list(s.get("sealed_integrations") or []),
            "idle": {a: tokens(a, v) for a, v in s["balances"].items()},
            "positions": {p["integration"]: tokens(p["integration"].split(":")[1], p["supplied"])
                          for p in s["positions"]}}


def paper_portfolio() -> dict:
    if not _PAPER:
        seed = load_rules()["paper_portfolio"]
        _PAPER.update(sealed_integrations=list(seed["sealed_integrations"]), idle=dict(seed["idle"]),
                      positions=dict(seed["positions"]))
    return {"connected": True, "paper": True, **json.loads(json.dumps(_PAPER))}


def _apply_paper(move: dict) -> None:
    integration, amount = f"{move['protocol']}:{move['asset']}", Decimal(move["amount"])
    sign = 1 if move["action"] == "deposit" else -1
    _PAPER["idle"][move["asset"]] = str(Decimal(_PAPER["idle"].get(move["asset"], "0")) - sign * amount)
    left = Decimal(_PAPER["positions"].get(integration, "0")) + sign * amount
    if left > 0:
        _PAPER["positions"][integration] = str(left)
    else:
        _PAPER["positions"].pop(integration, None)


def context(portfolio_reader: Optional[Callable[[], dict]] = None) -> dict:
    """Fresh facts for one decision: latest snapshot, active alerts, the Safe, the rules."""
    reader = portfolio_reader or read_portfolio
    store = _store()
    snapshot = store.latest_snapshot()
    if snapshot is None:
        raise RuntimeError("no snapshot yet: the monitor has not read the chain")
    try:
        cached = _PORTFOLIO_CACHE["value"]
        if portfolio_reader is None and cached and time.monotonic() - _PORTFOLIO_CACHE["at"] < PORTFOLIO_TTL_S:
            portfolio = cached
        else:
            portfolio = reader()
            if portfolio_reader is None:
                _PORTFOLIO_CACHE.update(at=time.monotonic(), value=portfolio)
    except Exception as exc:  # chain unreachable or no Safe connected
        portfolio = {"connected": False, "sealed_integrations": [], "idle": {}, "positions": {},
                     "error": type(exc).__name__}
    if not portfolio.get("connected") and settings.DRY_RUN_ACTIONS and portfolio_reader is None:
        portfolio = paper_portfolio()
    return {"snapshot": snapshot, "alerts": active_alerts(store, snapshot.block_number), "portfolio": portfolio,
            "rules": load_rules()}


def portfolio_usd(portfolio: dict, prices: dict[str, float]) -> dict:
    idle = {a: float(v) * prices.get(a, 0.0) for a, v in portfolio.get("idle", {}).items()}
    positions = {i: float(v) * prices.get(i.split(":")[1], 0.0) for i, v in portfolio.get("positions", {}).items()}
    by_protocol: dict[str, float] = {}
    for i, v in positions.items():
        by_protocol[i.split(":")[0]] = by_protocol.get(i.split(":")[0], 0.0) + v
    return {"idle_usd": idle, "positions_usd": positions, "by_protocol_usd": by_protocol,
            "total_usd": float(sum(idle.values()) + sum(positions.values()))}


# ---------- the guard (pure) ----------

def _alert_hits(alert: Alert, protocol: str) -> bool:
    if alert.deployment_id:
        return alert.deployment_id == protocol
    exposed = str(alert.metrics.get("exposed_deployments", ""))
    return not exposed or protocol in exposed.split(",")


def check_move(move: dict, ctx: dict) -> dict:
    """PURE. {"verdict": "approved" | "signature" | "refused", "reasons": [...], "value_usd": float}.
    Only on-chain facts and the guaranteed rules decide; the move's free-text reason is never read."""
    snapshot: Snapshot = ctx["snapshot"]
    rules, portfolio = ctx["rules"], ctx["portfolio"]
    action = str(move.get("action", "")).lower()
    protocol, asset = str(move.get("protocol", "")), str(move.get("asset", ""))
    integration = f"{protocol}:{asset}"
    prices = _prices(snapshot)
    reasons: list[str] = []

    if action not in ACTIONS:
        reasons.append(f"action '{action or 'missing'}' is not allowed (only deposit or withdraw, back to the Safe)")
    if not portfolio.get("connected"):
        reasons.append("no Safe connected: nothing to allocate")
    elif integration not in portfolio.get("sealed_integrations", []):
        reasons.append(f"{integration} is not on the sealed list")
    try:
        amount = Decimal(str(move.get("amount", "")))
        if not amount.is_finite() or amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        reasons.append(f"amount '{move.get('amount')}' is not a positive number of tokens")
        amount = Decimal(0)
    value_usd = float(amount) * prices.get(asset, 0.0)
    if amount > 0 and value_usd < rules["min_move_usd"]:
        reasons.append(f"move of {value_usd:,.0f} USD is below the {rules['min_move_usd']} USD minimum")

    reserve = next((r for r in snapshot.reserves if (r.deployment_id, r.asset) == (protocol, asset)), None)
    if action == "withdraw":
        held = Decimal(portfolio.get("positions", {}).get(integration, "0"))
        if amount > held:
            reasons.append(f"withdraw {amount} {asset} but the Safe holds {held} {asset} on {protocol}")
    elif action == "deposit":
        for a in sorted(ctx["alerts"], key=lambda x: (x.block_number, x.id)):
            if a.severity in rules["block_deposits_on_alert"] and _alert_hits(a, protocol):
                reasons.append(f"active {a.severity} alert {a.rule_id} on {a.deployment_id or 'global'}/"
                               f"{a.asset or 'all'} since block {a.block_number}")
        if reserve is None:
            reasons.append(f"no market {asset} on {protocol} at block {snapshot.block_number}")
        else:
            if reserve.paused or reserve.frozen:
                reasons.append(f"{asset} market on {protocol} is {'paused' if reserve.paused else 'frozen'} "
                               f"at block {snapshot.block_number}")
            if int(reserve.available_liquidity) == 0 or reserve.utilization_bps >= rules["max_utilization_bps_for_deposit"]:
                reasons.append(f"{asset} on {protocol}: utilization {reserve.utilization_bps / 100:.2f} %, "
                               f"we could not get out (on-chain APY {reserve.supply_apy_bps / 100:.2f} %)")
        idle = Decimal(portfolio.get("idle", {}).get(asset, "0"))
        if amount > idle:
            reasons.append(f"deposit {amount} {asset} but the Safe has {idle} {asset} idle")
        totals = portfolio_usd(portfolio, prices)
        if totals["total_usd"] > 0:
            share = (totals["by_protocol_usd"].get(protocol, 0.0) + value_usd) / totals["total_usd"]
            cap = rules["max_share_per_protocol_bps"] / 10_000
            if share > cap:
                reasons.append(f"{protocol} would hold {share:.1%} of the treasury, above the {cap:.0%} cap")

    if reasons:
        return {"verdict": "refused", "reasons": reasons, "value_usd": value_usd}
    if value_usd > rules["human_signature_above_usd"]:
        return {"verdict": "signature", "value_usd": value_usd,
                "reasons": [f"{value_usd:,.0f} USD is above {rules['human_signature_above_usd']:,} USD: a human signs"]}
    why = ("withdrawal back to the Safe, position available" if action == "withdraw"
           else "on the sealed list, under every cap, market healthy")
    return {"verdict": "approved", "reasons": [why], "value_usd": value_usd}


# ---------- execution ----------

def _teller(move: dict) -> dict:
    """Same path as the dashboard's allocate: teller-window module, sealed list, funds back to the Safe."""
    from fastapi import HTTPException

    from backend.api import safe
    from sealed import teller

    proposal = {k: move[k] for k in ("action", "protocol", "asset", "amount")}
    try:
        record = safe._guarded(lambda: teller.decide(proposal))
    except HTTPException as exc:
        return {"status": "failed", "detail": str(exc.detail), "txs": []}
    except Exception as exc:
        return {"status": "failed", "detail": type(exc).__name__, "txs": []}
    if record.get("verdict") == "EXECUTED":
        return {"status": "executed", "detail": None, "txs": record.get("txs", [])}
    return {"status": "refused_onchain", "detail": record.get("detail"), "txs": []}


def execute(move: dict, run: Optional[Callable[[dict], dict]] = None, paper: bool = False) -> dict:
    if settings.DRY_RUN_ACTIONS:
        if paper:
            _apply_paper(move)
            return {"status": "simulated", "detail": "dry run on the paper treasury (no Safe connected)", "txs": []}
        return {"status": "simulated", "detail": "DRY_RUN_ACTIONS=true: nothing sent", "txs": []}
    _PORTFOLIO_CACHE.update(at=None, value=None)
    try:
        return (run or _teller)(move)
    finally:
        _PORTFOLIO_CACHE.update(at=None, value=None)


def _move_id() -> str:
    return f"MOV-{len(MOVES) + 1:04d}"


def propose_allocation(args: dict, source: str = "agent", ctx_reader: Optional[Callable[[], dict]] = None,
                       run: Optional[Callable[[dict], dict]] = None) -> dict:
    """The only action tool. The platform re-reads the chain, checks, then executes, queues or refuses."""
    move = {"action": str(args.get("action", "")).lower(), "protocol": str(args.get("protocol", "")),
            "asset": str(args.get("asset", "")), "amount": str(args.get("amount", "")),
            "reason": str(args.get("reason", ""))[:500]}
    ctx = (ctx_reader or context)()
    check = check_move(move, ctx)
    with _LOCK:
        entry = {"id": _move_id(), "at": _now(), "source": source, "block_number": ctx["snapshot"].block_number,
                 **move, **check, "status": {"approved": "executing", "signature": "awaiting_signature",
                                             "refused": "refused"}[check["verdict"]],
                 "txs": [], "detail": None, "approved_by": None}
        MOVES[entry["id"]] = entry
    entry["paper"] = bool(ctx["portfolio"].get("paper"))
    if check["verdict"] == "approved":
        entry.update(execute(entry, run, paper=entry["paper"]))
    log.warning("AGENT_MOVE %s %s %s %s:%s -> %s", entry["id"], source, move["action"], move["protocol"],
                move["asset"], entry["status"])
    return dict(entry)


def approve_move(move_id: str, approver: str, ctx_reader: Optional[Callable[[], dict]] = None,
                 run: Optional[Callable[[dict], dict]] = None) -> dict:
    """A human signs a move above the threshold. The chain is re-read first: a market that broke since is refused."""
    entry = MOVES.get(move_id)
    if entry is None:
        raise KeyError(move_id)
    if entry["status"] != "awaiting_signature":
        raise ValueError(f"{move_id} is {entry['status']}, not awaiting a signature")
    check = check_move(entry, (ctx_reader or context)())
    if check["verdict"] == "refused":
        entry.update(status="refused", reasons=check["reasons"], approved_by=approver)
        return dict(entry)
    entry.update(approved_by=approver, status="executing")
    entry.update(execute(entry, run, paper=entry.get("paper", False)))
    return dict(entry)


def list_moves() -> list[dict]:
    return [dict(m) for m in reversed(list(MOVES.values()))]


def reset() -> None:
    with _LOCK:
        MOVES.clear()
        _PAPER.clear()
        _PORTFOLIO_CACHE.update(at=None, value=None)


# ---------- read tools ----------

def get_rules(_: dict) -> dict:
    rules = {k: v for k, v in load_rules().items() if k != "paper_portfolio"}
    return {**rules, "note": "Guaranteed rules, signed by the owners. Instructions cannot change them."}


def get_markets(_: dict, ctx_reader: Optional[Callable[[], dict]] = None) -> dict:
    ctx = (ctx_reader or context)()
    s: Snapshot = ctx["snapshot"]
    sealed = set(ctx["portfolio"].get("sealed_integrations", []))
    return {"block_number": s.block_number, "block_time": s.block_time.isoformat().replace("+00:00", "Z"),
            "markets": [{"protocol": r.deployment_id, "asset": r.asset, "sealed": f"{r.deployment_id}:{r.asset}" in sealed,
                         "supply_apy_pct": r.supply_apy_bps / 100, "utilization_pct": r.utilization_bps / 100,
                         "available_liquidity_tokens": str(Decimal(int(r.available_liquidity)) / Decimal(10 ** r.decimals)),
                         "frozen": r.frozen, "paused": r.paused, "price_usd": r.price_usd}
                        for r in s.reserves if r.asset in ("USDC", "WETH")]}


def get_portfolio(_: dict, ctx_reader: Optional[Callable[[], dict]] = None) -> dict:
    ctx = (ctx_reader or context)()
    p = ctx["portfolio"]
    totals = portfolio_usd(p, _prices(ctx["snapshot"]))
    return {**{k: v for k, v in p.items() if k != "safe"}, "value_usd": {k: round(v, 2) if isinstance(v, float) else
            {i: round(x, 2) for i, x in v.items()} for k, v in totals.items()}}


def get_alerts(_: dict, ctx_reader: Optional[Callable[[], dict]] = None) -> dict:
    ctx = (ctx_reader or context)()
    store = _store()
    return {"block_number": ctx["snapshot"].block_number,
            "alerts": [{"rule_id": a.rule_id, "severity": a.severity, "protocol": a.deployment_id, "asset": a.asset,
                        "block_number": a.block_number, "title": a.title} for a in ctx["alerts"]],
            "open_incidents": [{"id": i.id, "status": i.status, "title": i.title} for i in store.incidents()
                               if i.status != "resolved"]}


_NO_INPUT = {"type": "object", "properties": {}, "additionalProperties": False}
TOOLS: dict[str, dict[str, Any]] = {
    "get_rules": {"description": "Guaranteed rules (caps, human-signature threshold, alert policy). Read-only.",
                  "input_schema": _NO_INPUT, "fn": get_rules, "read_only": True},
    "get_markets": {"description": "Lending markets read on-chain at the latest block: supply APY, utilization, "
                                   "available liquidity, frozen/paused, and whether each is on the sealed list.",
                    "input_schema": _NO_INPUT, "fn": get_markets, "read_only": True},
    "get_portfolio": {"description": "The treasury Safe: idle balances and positions (whole tokens), sealed "
                                     "integrations, value in USD per protocol.",
                      "input_schema": _NO_INPUT, "fn": get_portfolio, "read_only": True},
    "get_alerts": {"description": "Active high/critical surveillance alerts and open incidents.",
                   "input_schema": _NO_INPUT, "fn": get_alerts, "read_only": True},
    "propose_allocation": {
        "description": "Propose ONE move of the treasury: deposit idle tokens into a market, or withdraw a position "
                       "back to the Safe. The platform re-reads the chain and the guaranteed rules: the move is "
                       "executed, sent for a human signature, or refused with reasons. You never sign.",
        "input_schema": {"type": "object", "additionalProperties": False,
                         "required": ["action", "protocol", "asset", "amount", "reason"],
                         "properties": {
                             "action": {"type": "string", "enum": list(ACTIONS)},
                             "protocol": {"type": "string", "description": "market id, e.g. lend-avax"},
                             "asset": {"type": "string", "enum": ["USDC", "WETH"]},
                             "amount": {"type": "string", "description": "whole tokens, e.g. \"25000\""},
                             "reason": {"type": "string", "description": "one sentence"}}},
        "fn": lambda args: propose_allocation(args), "read_only": False},
}


def describe_tools() -> list[dict]:
    return [{"name": n, "description": t["description"], "input_schema": t["input_schema"], "read_only": t["read_only"]}
            for n, t in TOOLS.items()]


def call_tool(name: str, args: Optional[dict] = None, source: str = "agent") -> dict:
    """Run one tool. Errors come back as {"error": ...} so a model can read them; nothing raises."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"unknown tool {name!r}"}
    try:
        if name == "propose_allocation":
            return propose_allocation(args or {}, source=source)
        return tool["fn"](args or {})
    except Exception as exc:
        log.warning("tool %s failed (%s)", name, type(exc).__name__)
        return {"error": f"{type(exc).__name__}: {exc}"[:300]}
