"""T5-01 to T5-12: DORA classification, deadlines, facts and report (TASKS.md T5 2 to 5)."""
import re
from datetime import datetime, timezone

import pytest

from backend import dora
from backend.dora import (
    T_9_1, T_9_2, T_9_3, T_9_4, T_9_5A, T_9_5B, T_9_6, IncidentFacts, classify, compute_criteria, deadlines,
    load_profile,
)
from backend.models import DoraCriteria
from backend.tests.test_t5_factories import run_reacted_incident


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def criteria(**changes) -> DoraCriteria:
    base = dict(critical_services_affected=True, clients_affected_pct=0.0, clients_affected_count=0,
                transactions_affected_value_pct=0.0, counterparts_affected_pct=0.0,
                transactions_affected_count_pct=0.0, relevant_clients_affected=False, duration_hours=0.0,
                critical_service_downtime_hours=0.0, member_states_affected=0, reputational_impact=False,
                data_losses=False, malicious_unauthorised_access=False, economic_impact_eur=0.0)
    base.update(changes)
    return DoraCriteria(**base)


ALL_MET = dict(clients_affected_pct=50.0, reputational_impact=True, duration_hours=48.0, member_states_affected=3,
               data_losses=True, malicious_unauthorised_access=True, economic_impact_eur=500000.0)


def test_no_critical_service_never_major():
    result = classify(criteria(critical_services_affected=False, **ALL_MET))
    assert result.is_major is False
    assert result.thresholds_met == [T_9_1, T_9_2, T_9_3, T_9_4, T_9_5A, T_9_5B, T_9_6]
    assert "not major, no critical service" in result.legal_basis


def test_single_threshold_not_major():
    result = classify(criteria(clients_affected_pct=15.0))
    assert result.thresholds_met == [T_9_1]
    assert result.is_major is False
    assert result.legal_basis == ("RTS (EU) 2024/1772 Art. 8(1): not major, critical services affected but only "
                                  "1 materiality threshold of Art. 9 met (9(1)).")


def test_malicious_access_alone_major():
    result = classify(criteria(malicious_unauthorised_access=True))
    assert result.thresholds_met == [T_9_5B]
    assert result.is_major is True
    assert "Art. 8(1)(a)" in result.legal_basis


PAIRS = {
    "9(2)+9(4)": dict(reputational_impact=True, member_states_affected=2),
    "9(3)+9(6)": dict(duration_hours=30.0, economic_impact_eur=200000.0),
    "9(1)+9(4)": dict(clients_affected_pct=100.0, member_states_affected=2),
    "9(1)+9(6)": dict(clients_affected_count=200000, economic_impact_eur=150000.0),
    "9(5)a+9(2)": dict(data_losses=True, reputational_impact=True),
    "9(3)+9(4)": dict(critical_service_downtime_hours=3.0, member_states_affected=2),
}


@pytest.mark.parametrize("name", PAIRS)
def test_two_thresholds_major(name):
    result = classify(criteria(**PAIRS[name]))
    assert result.is_major is True
    assert "Art. 8(1)(b)" in result.legal_basis
    assert "2 materiality thresholds" in result.legal_basis


BOUNDS = [
    ("clients_affected_pct", 10.0, 10.01, T_9_1),
    ("clients_affected_count", 100000, 100001, T_9_1),
    ("duration_hours", 24.0, 24.01, T_9_3),
    ("critical_service_downtime_hours", 2.0, 2.01, T_9_3),
    ("member_states_affected", 1, 2, T_9_4),
    ("economic_impact_eur", 100000.0, 100000.01, T_9_6),
    ("counterparts_affected_pct", 30.0, 30.01, T_9_1),
    ("transactions_affected_count_pct", 10.0, 10.01, T_9_1),
    ("transactions_affected_value_pct", 10.0, 10.01, T_9_1),
    ("relevant_clients_affected", False, True, T_9_1),
]


@pytest.mark.parametrize("field,below,above,label", BOUNDS, ids=[b[0] for b in BOUNDS])
def test_boundaries(field, below, above, label):
    assert label not in classify(criteria(**{field: below})).thresholds_met
    assert label in classify(criteria(**{field: above})).thresholds_met


def test_criterion_counts_once():
    result = classify(criteria(clients_affected_pct=50.0, clients_affected_count=200000))
    assert result.thresholds_met == [T_9_1]
    assert result.is_major is False
    both = classify(criteria(data_losses=True, malicious_unauthorised_access=True))
    assert both.thresholds_met == [T_9_5A, T_9_5B]
    assert both.is_major is True  # via 9(5)(b), Art. 8(1)(a)
    only_data = classify(criteria(data_losses=True, clients_affected_pct=0.0))
    assert only_data.is_major is False
    assert "1 materiality threshold" in only_data.legal_basis


def test_deadlines_nominal():
    d = deadlines(utc("2026-10-11T08:00:26Z"), utc("2026-10-11T08:02:26Z"))
    assert d.initial_notification_due == utc("2026-10-11T12:02:26Z")
    assert d.intermediate_report_due == utc("2026-10-14T12:02:26Z")
    assert d.final_report_due == utc("2026-11-13T12:02:26Z")
    assert d.model_dump(mode="json")["initial_notification_due"] == "2026-10-11T12:02:26Z"


def test_deadlines_24h_cap():
    d = deadlines(utc("2026-10-11T00:00:00Z"), utc("2026-10-11T22:00:00Z"))
    assert d.initial_notification_due == utc("2026-10-12T00:00:00Z")


def test_deadlines_after_submission():
    d = deadlines(utc("2026-10-11T08:00:26Z"), utc("2026-10-11T08:02:26Z"), utc("2026-10-11T10:00:00Z"))
    assert d.intermediate_report_due == utc("2026-10-14T10:00:00Z")
    assert d.final_report_due == utc("2026-11-13T10:00:00Z")


def _facts(at_risk: float) -> IncidentFacts:
    return IncidentFacts(exposure_usd=1325000.0, total_treasury_usd=1325000.0, at_risk_usd=at_risk,
                         aware_at=utc("2026-10-11T08:00:26Z"), end_at=utc("2026-10-11T08:01:04Z"),
                         deposits_paused_hours=0.04)


def test_scenario_facts():
    c = compute_criteria(_facts(0.0), load_profile())
    assert (c.clients_affected_pct, c.clients_affected_count, c.member_states_affected, c.economic_impact_eur) == \
        (100.0, 1200, 2, 0.0)
    assert (c.counterparts_affected_pct, c.transactions_affected_count_pct, c.relevant_clients_affected) == \
        (0.0, 0.0, False)
    result = classify(c)
    assert result.thresholds_met == [T_9_1, T_9_4]
    assert result.is_major is True


def test_counterfactual_facts():
    c = compute_criteria(_facts(375000.0), load_profile())
    assert c.economic_impact_eur == 345000.0
    assert classify(c).thresholds_met == [T_9_1, T_9_4, T_9_6]


TITLES = ["## 1. General information", "## 2. Classification proposal", "## 3. Description",
          "## 4. Classification criteria (RTS 2024/1772 Art. 9)", "## 5. Actions taken",
          "## 6. Deadlines (Regulation (EU) 2025/301)", "## 7. Third parties involved", "## 8. Human review"]


def test_report_markdown(monkeypatch):
    incident, _ = run_reacted_incident(monkeypatch)
    md = incident.dora.report_markdown
    assert md.splitlines()[0] == "# DORA initial notification (draft, human review required)"
    positions = [md.index(t) for t in TITLES]
    assert positions == sorted(positions)
    assert "1,325,000 USD" in md
    assert "INC-20261011-001" in md
    assert "150 WETH" in md
    assert not re.search(r"\bNone\b|\bnan\b|TODO|\{[a-z_]+\}", md)
    assert dora.render_report(incident).startswith("# DORA initial notification")
