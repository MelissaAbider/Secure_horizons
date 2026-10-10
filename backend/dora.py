"""DORA classification (RTS (EU) 2024/1772 Art. 8 and 9), deadlines (Regulation (EU) 2025/301) and the
initial notification draft (TASKS.md T5 1 to 5). Pure functions, no I/O except load_profile and the CLI.

python -m backend.dora demo                          offline: incident and report for the scenario
python -m backend.dora report --id INC-… --api URL   writes data/reports/<id>.md from the running backend
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import NamedTuple

import yaml

from backend import settings
from backend.models import Alert, DoraCriteria, DoraDeadlines, Incident

logger = logging.getLogger("t5.dora")

T_9_1 = "9(1) clients, financial counterparts and transactions"
T_9_2 = "9(2) reputational impact"
T_9_3 = "9(3) duration and service downtime"
T_9_4 = "9(4) geographical spread"
T_9_5A = "9(5)(a) data losses"
T_9_5B = "9(5)(b) malicious unauthorised access"
T_9_6 = "9(6) economic impact"

PROFILE_KEYS = ["entity_name", "entity_type", "clients_count", "client_member_states", "critical_services",
                "usd_to_eur", "reputational_impact", "data_losses", "malicious_unauthorised_access"]
HUMAN_REVIEW = "This classification is a proposal. It must be reviewed and submitted by an authorised person."
REPORT_TITLE = "# DORA initial notification (draft, human review required)"


def load_profile(path: Path | None = None) -> dict:
    path = path or settings.CONFIG_DIR / "dora_profile.yaml"
    profile = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in PROFILE_KEYS:
        if key not in profile:
            raise ValueError(f"dora_profile: missing {key}")
    return profile


# ---------- Classification ----------

class Classification(NamedTuple):
    thresholds_met: list[str]
    is_major: bool
    legal_basis: str


def short_label(threshold: str) -> str:
    """'9(5)(a) data losses' -> '9(5)'; '9(1) clients…' -> '9(1)'."""
    return re.match(r"\d\(\d\)", threshold).group(0)


def _criteria_list(met: list[str]) -> list[str]:
    distinct: list[str] = []
    for t in met:
        if short_label(t) not in distinct:
            distinct.append(short_label(t))
    return distinct


def classify(c: DoraCriteria) -> Classification:
    met: list[str] = []
    if (c.clients_affected_pct > 10 or c.clients_affected_count > 100_000 or c.counterparts_affected_pct > 30
            or c.transactions_affected_value_pct > 10 or c.transactions_affected_count_pct > 10
            or c.relevant_clients_affected):
        met.append(T_9_1)
    if c.reputational_impact:
        met.append(T_9_2)
    if c.duration_hours > 24 or c.critical_service_downtime_hours > 2:
        met.append(T_9_3)
    if c.member_states_affected >= 2:
        met.append(T_9_4)
    if c.data_losses:
        met.append(T_9_5A)
    if c.malicious_unauthorised_access:
        met.append(T_9_5B)
    if c.economic_impact_eur > 100_000:
        met.append(T_9_6)

    distinct = _criteria_list(met)
    n = len(distinct)
    short = ", ".join(distinct) or "none"
    prefix = "RTS (EU) 2024/1772 Art. 8(1)"
    if not c.critical_services_affected:
        return Classification(met, False, f"{prefix}: not major, no critical service affected.")
    if T_9_5B in met:
        return Classification(met, True, f"{prefix}(a): critical services affected and malicious unauthorised "
                                          "access (Art. 9(5)(b)) identified.")
    if n >= 2:
        return Classification(met, True, f"{prefix}(b): critical services affected and {n} materiality thresholds "
                                          f"of Art. 9 met ({short}).")
    noun = "threshold" if n == 1 else "thresholds"
    return Classification(met, False, f"{prefix}: not major, critical services affected but only {n} materiality "
                                       f"{noun} of Art. 9 met ({short}).")


# ---------- Facts -> criteria ----------

@dataclass(frozen=True)
class IncidentFacts:
    exposure_usd: float
    total_treasury_usd: float
    at_risk_usd: float
    aware_at: datetime
    end_at: datetime
    deposits_paused_hours: float


def compute_criteria(f: IncidentFacts, profile: dict) -> DoraCriteria:
    pct = round(min(100.0, f.exposure_usd / f.total_treasury_usd * 100), 2) if f.total_treasury_usd else 0.0
    return DoraCriteria(
        critical_services_affected=bool(profile["critical_services"]) and f.exposure_usd > 0,
        clients_affected_pct=pct,
        clients_affected_count=round(profile["clients_count"] * pct / 100),
        transactions_affected_value_pct=0.0,
        counterparts_affected_pct=0.0,
        transactions_affected_count_pct=0.0,
        relevant_clients_affected=False,
        duration_hours=round(max(0.0, (f.end_at - f.aware_at).total_seconds() / 3600), 4),
        critical_service_downtime_hours=round(max(0.0, f.deposits_paused_hours), 4),
        member_states_affected=len(profile["client_member_states"]) if pct > 0 else 0,
        reputational_impact=bool(profile["reputational_impact"]),
        data_losses=bool(profile["data_losses"]),
        malicious_unauthorised_access=bool(profile["malicious_unauthorised_access"]),
        economic_impact_eur=round(f.at_risk_usd * profile["usd_to_eur"], 2),
    )


# ---------- Deadlines ----------

def deadlines(aware_at: datetime, classified_at: datetime, initial_submitted_at: datetime | None = None) -> DoraDeadlines:
    initial = min(classified_at + timedelta(hours=4), aware_at + timedelta(hours=24))
    intermediate = (initial_submitted_at or initial) + timedelta(hours=72)
    return DoraDeadlines(initial_notification_due=initial, intermediate_report_due=intermediate,
                         final_report_due=intermediate + timedelta(days=30))  # "one month" approximated as 30 days


# ---------- Formatting ----------

def iso(dt: datetime | None) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else "not available"


def fmt_usd(value: float) -> str:
    return f"{value:,.0f}"


def fmt_tokens(amount: int | str, decimals: int) -> str:
    """Base units -> whole tokens, 2 decimals max, no useless zeros: 150000000000000000000 -> '150'."""
    q = (Decimal(int(amount)) / (Decimal(10) ** decimals)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    text = f"{q:,.2f}".rstrip("0").rstrip(".")
    return text


def _yes(flag: bool) -> str:
    return "yes" if flag else "no"


def _criteria_rows(c: DoraCriteria) -> list[tuple[str, str, str, bool]]:
    return [
        ("9(1) clients affected (%)", f"{c.clients_affected_pct:.2f} %", "> 10 %", c.clients_affected_pct > 10),
        ("9(1) clients affected (count)", f"{c.clients_affected_count:,}", "> 100,000", c.clients_affected_count > 100_000),
        ("9(1) financial counterparts affected (%)", f"{c.counterparts_affected_pct:.2f} %", "> 30 %",
         c.counterparts_affected_pct > 30),
        ("9(1) transactions affected (value %)", f"{c.transactions_affected_value_pct:.2f} %", "> 10 %",
         c.transactions_affected_value_pct > 10),
        ("9(1) transactions affected (count %)", f"{c.transactions_affected_count_pct:.2f} %", "> 10 %",
         c.transactions_affected_count_pct > 10),
        ("9(1) relevant clients affected", _yes(c.relevant_clients_affected), "yes", c.relevant_clients_affected),
        ("9(2) reputational impact", _yes(c.reputational_impact), "yes", c.reputational_impact),
        ("9(3) duration", f"{c.duration_hours:.2f} h", "> 24 h", c.duration_hours > 24),
        ("9(3) critical service downtime", f"{c.critical_service_downtime_hours:.2f} h", "> 2 h",
         c.critical_service_downtime_hours > 2),
        ("9(4) member states affected", str(c.member_states_affected), ">= 2", c.member_states_affected >= 2),
        ("9(5)(a) data losses", _yes(c.data_losses), "yes", c.data_losses),
        ("9(5)(b) malicious unauthorised access", _yes(c.malicious_unauthorised_access), "yes",
         c.malicious_unauthorised_access),
        ("9(6) economic impact", f"{c.economic_impact_eur:,.2f} EUR", "> 100,000 EUR", c.economic_impact_eur > 100_000),
    ]


def template_description(incident: Incident, alert: Alert | None = None) -> str:
    if alert is not None:
        raised = f"{alert.rule_id} ({alert.severity}): {alert.explanation}"
    else:
        first = next((e.text for e in incident.timeline if e.kind == "alert"), f"an alert ({incident.severity}).")
        raised = first if first.endswith(".") else first + "."
    return (f"At {iso(incident.detected_at)} the monitoring platform raised {raised} Automated controls paused new "
            f"deposits and withdrew {fmt_usd(incident.saved_usd)} USD to the treasury vault. Exposure at detection: "
            f"{fmt_usd(incident.exposure_usd)} USD; value still at risk: {fmt_usd(incident.at_risk_usd)} USD. "
            f"Current status: {incident.status}.")


def render_report(incident: Incident, description: str | None = None, profile: dict | None = None,
                  third_parties: list[str] | None = None, alert: Alert | None = None) -> str:
    if incident.dora is None:
        raise ValueError(f"incident {incident.id} has no DORA assessment")
    profile = profile or load_profile()
    d = incident.dora
    text = description if description is not None else template_description(incident, alert)
    if "Description" in d.ai_drafted_sections:
        text += " _(AI-drafted, review required)_"

    lines = [REPORT_TITLE, "", "## 1. General information", "",
             f"- Entity: {profile['entity_name']}",
             f"- Entity type: {profile['entity_type']}",
             f"- Incident reference: {incident.id}",
             f"- Incident title: {incident.title}",
             f"- Detection (aware at): {iso(d.aware_at)}",
             f"- Classification (classified at): {iso(d.classified_at)}",
             f"- Status: {incident.status}" + (f" (contained at {iso(incident.contained_at)})"
                                                if incident.contained_at else ""),
             f"- Exposure at detection: {fmt_usd(incident.exposure_usd)} USD; withdrawn to the vault: "
             f"{fmt_usd(incident.saved_usd)} USD; still at risk: {fmt_usd(incident.at_risk_usd)} USD",
             "", "## 2. Classification proposal", "",
             f"**{'Major' if d.is_major else 'Not major'}** incident. {d.legal_basis}",
             "", "## 3. Description", "", text,
             "", "## 4. Classification criteria (RTS 2024/1772 Art. 9)", "",
             "| Criterion | Value | Threshold | Met |", "|---|---|---|---|"]
    lines += [f"| {name} | {value} | {threshold} | {_yes(met)} |" for name, value, threshold, met in _criteria_rows(d.criteria)]
    lines += ["", f"Thresholds met: {', '.join(short_label(t) for t in d.thresholds_met) or 'none'}.",
              "", "## 5. Actions taken", ""]
    actions = [e for e in incident.timeline if e.kind == "action" and " failed: " not in e.text]
    if actions:
        lines += [f"- {e.text}" + (f" (tx {e.ref})" if e.ref and e.ref.startswith("0x") else "") for e in actions]
    else:
        lines.append("- No automated action executed.")
    lines += ["", "## 6. Deadlines (Regulation (EU) 2025/301)", "", "| Report | Due (UTC) |", "|---|---|",
              f"| Initial notification | {iso(d.deadlines.initial_notification_due)} |",
              f"| Intermediate report | {iso(d.deadlines.intermediate_report_due)} |",
              f"| Final report | {iso(d.deadlines.final_report_due)} |",
              "", "## 7. Third parties involved", ""]
    lines += [f"- {dep}" for dep in (third_parties or ["oracle"])]
    lines += ["", "## 8. Human review", "", HUMAN_REVIEW, ""]
    if d.submitted:
        lines.append(f"Status: submitted by {d.submitted_by} at {iso(d.submitted_at)}.")
    else:
        lines.append("Status: not submitted.")
    return "\n".join(lines) + "\n"


# ---------- CLI ----------

def _demo_inputs():
    """R1 decision and alert: from the T4 dry-run evidence file if it exists and is consistent, else the factories."""
    import json

    from backend.models import Decision
    from backend.tests.test_t5_factories import make_alert_r1, make_decision_r1

    path = settings.DATA_DIR / "evidence" / "DEC-fuji-45201812-1.json"
    if path.exists():
        ev = json.loads(path.read_text(encoding="utf-8"))
        decision = Decision.model_validate(ev["decision"])
        alerts = [Alert.model_validate(a) for a in ev["inputs"]["alerts"]]
        drift = abs((decision.created_at - min(a.detected_at for a in alerts)).total_seconds())
        if drift <= 600:
            return decision, alerts, f"T4 evidence {path}"
        print(f"warning: {path.name} was created at {iso(decision.created_at)} (wall clock) but its alert is dated "
              f"{iso(alerts[0].detected_at)} (scenario clock); using the scenario decision instead.", file=sys.stderr)
    return make_decision_r1(), [make_alert_r1()], "scenario factories"


def cmd_demo() -> int:
    from backend.incidents import IncidentManager
    from backend.tests.test_t5_factories import FORGED_BLOCK, FakeStore, make_reacted_series, run_series

    settings.BEDROCK_MODEL_ID = ""  # offline: template description, no AWS call
    decision, alerts, source = _demo_inputs()
    store = FakeStore()
    run_series(IncidentManager(store, llm_async=False), make_reacted_series(), at={FORGED_BLOCK: ([decision], alerts)})
    incidents = store.incidents()
    if not incidents:
        print("no incident opened")
        return 1
    i = incidents[0]
    print(f"INCIDENT {i.id} {i.status} saved_usd={fmt_usd(i.saved_usd)} at_risk_usd={fmt_usd(i.at_risk_usd)} "
          f"major={i.dora.is_major} thresholds={', '.join(short_label(t) for t in i.dora.thresholds_met)} "
          f"(decision {decision.id} from {source})")
    print()
    print(i.dora.report_markdown)
    return 0


def cmd_report(incident_id: str, api: str) -> int:
    import urllib.error
    import urllib.request

    url = f"{api.rstrip('/')}/api/incidents/{incident_id}/report.md"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 (local API)
            md = resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as e:
        print(f"cannot get {url}: {e}. Is the backend running (make backend)?")
        return 1
    out = settings.DATA_DIR / "reports" / f"{incident_id}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(md)
    print(f"written: {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.dora")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    report = sub.add_parser("report")
    report.add_argument("--id", required=True)
    report.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args(argv)
    if args.command == "demo":
        return cmd_demo()
    return cmd_report(args.id, args.api)


if __name__ == "__main__":
    sys.exit(main())
