"""DORA initial notification draft as PDF (backend/dora_pdf.py), offline."""
from backend.dora_pdf import _section_items, render_pdf
from backend.tests.test_t5_factories import run_reacted_incident


def test_pdf_renders_scenario_incident(monkeypatch):
    incident, _ = run_reacted_incident(monkeypatch)
    pdf = render_pdf(incident)
    assert pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")
    assert len(pdf) > 4000
    assert _section_items(incident.dora.report_markdown, 7)  # third parties listed in the markdown report


def test_pdf_requires_dora(monkeypatch):
    incident, _ = run_reacted_incident(monkeypatch)
    import pytest
    with pytest.raises(ValueError):
        render_pdf(incident.model_copy(update={"dora": None}))
