"""DORA initial notification draft as a PDF (T5, from the T4/T5 branch). Same content as the markdown report
(backend/dora.py): 8 sections, criteria of RTS (EU) 2024/1772 Art. 9, deadlines of Regulation (EU) 2025/301, plus the
timeline as annex. A draft only: the classification is a proposal, a human reviews and submits.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

from backend import settings
from backend.dora import HUMAN_REVIEW, _criteria_rows, fmt_usd, iso, load_profile, short_label
from backend.models import Incident

# Core PDF fonts are Latin-1: map the few non-Latin-1 characters the report uses.
_ASCII = {"→": "->", "≥": ">=", "≤": "<=", "—": "-", "–": "-", "…": "...", "’": "'", "“": '"', "”": '"', "€": "EUR",
          "·": "-", "✓": "v", "✅": "", "⏳": "", "🚨": ""}
NAVY, GREY, LINE = (17, 26, 46), (95, 105, 120), (215, 220, 228)
RED, GREEN, AMBER = (198, 40, 40), (27, 122, 58), (161, 92, 0)


def _t(text) -> str:
    s = str(text if text is not None else "")
    for k, v in _ASCII.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def _section_items(markdown: str, number: int) -> list[str]:
    """Bullet lines of '## <number>.' in the markdown report (used for section 7, third parties)."""
    m = re.search(rf"^## {number}\..*?$(.*?)(?=^## |\Z)", markdown, flags=re.M | re.S)
    return [ln[2:].strip() for ln in (m.group(1).splitlines() if m else []) if ln.startswith("- ")]


def _description(markdown: str) -> str:
    m = re.search(r"^## 3\. Description\s*$(.*?)(?=^## |\Z)", markdown, flags=re.M | re.S)
    return " ".join(m.group(1).split()) if m else ""


class _Doc(FPDF):
    def __init__(self, incident: Incident):
        super().__init__(format="A4")
        self.incident = incident
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(16, 16, 16)
        self.set_title(_t(f"DORA initial notification draft - {incident.id}"))
        self.set_author("Secure Horizons (generated draft)")

    def header(self):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 210, 11, style="F")
        self.set_xy(16, 3)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)
        self.cell(120, 5, _t(f"Secure Horizons - DORA initial notification - {self.incident.id}"))
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, "DRAFT - human review required", align="R")
        self.set_text_color(0, 0, 0)
        self.set_y(17)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 5, _t(f"Generated {iso(datetime.now(timezone.utc))} - synthetic data - "
                           f"page {self.page_no()}/{{nb}}"), align="C")
        self.set_text_color(0, 0, 0)

    def h2(self, text: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*NAVY)
        self.cell(0, 7, _t(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*LINE)
        self.line(16, self.get_y(), 194, self.get_y())
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def para(self, text: str, size: float = 10, style: str = ""):
        self.set_font("Helvetica", style, size)
        self.multi_cell(0, 5, _t(text), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def kv(self, rows: list[tuple[str, str]]):
        self.set_fill_color(244, 246, 249)
        self.set_draw_color(*LINE)
        with self.table(col_widths=(55, 123), text_align=("LEFT", "LEFT"), first_row_as_headings=False,
                        borders_layout="HORIZONTAL_LINES", line_height=5.5,
                        cell_fill_color=(244, 246, 249), cell_fill_mode="COLUMNS") as table:
            for k, v in rows:
                r = table.row()
                self.set_font("Helvetica", "B", 9)
                r.cell(_t(k))
                self.set_font("Helvetica", "", 9)
                r.cell(_t(v))

    def grid(self, head: list[str], rows: list[list[str]], widths: tuple, size: float = 8.5):
        self.set_font("Helvetica", "", size)
        self.set_fill_color(244, 246, 249)
        self.set_draw_color(*LINE)
        heading = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=NAVY)
        with self.table(col_widths=widths, line_height=5, headings_style=heading, borders_layout="HORIZONTAL_LINES",
                        text_align="LEFT", cell_fill_color=(244, 246, 249), cell_fill_mode="ROWS") as table:
            h = table.row()
            for c in head:
                h.cell(_t(c))
            for row in rows:
                r = table.row()
                for c in row:
                    r.cell(_t(c))

    def badge(self, text: str, color: tuple):
        self.set_fill_color(*color)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)
        self.cell(self.get_string_width(_t(text)) + 8, 8, _t(text), fill=True, align="C")
        self.set_text_color(0, 0, 0)


def render_pdf(incident: Incident, profile: dict | None = None) -> bytes:
    if incident.dora is None:
        raise ValueError(f"incident {incident.id} has no DORA assessment")
    profile = profile or load_profile()
    d = incident.dora
    md = d.report_markdown or ""
    pdf = _Doc(incident)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 17)
    pdf.cell(0, 9, "DORA initial notification", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(0, 5, _t("Draft prepared by the monitoring platform under Regulation (EU) 2022/2554 (DORA) Art. 19. "
                            "Classification per Delegated Regulation (EU) 2024/1772, content and deadlines per "
                            "Delegated Regulation (EU) 2025/301. Not sent: an authorised person must review and submit."),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)
    pdf.badge("MAJOR INCIDENT" if d.is_major else "NOT MAJOR", RED if d.is_major else GREEN)
    pdf.cell(4)
    pdf.badge(incident.status.upper(), AMBER if incident.status == "open" else GREEN)
    pdf.cell(4)
    pdf.badge("SUBMITTED" if d.submitted else "NOT SUBMITTED", GREEN if d.submitted else GREY)
    pdf.ln(11)

    pdf.h2("1. General information")
    pdf.kv([
        ("Entity", profile["entity_name"]), ("Entity type", profile["entity_type"]),
        ("Incident reference", incident.id), ("Incident title", incident.title),
        ("Severity", incident.severity),
        ("Detection (aware at)", iso(d.aware_at)), ("Classification (classified at)", iso(d.classified_at)),
        ("Status", incident.status + (f" (contained at {iso(incident.contained_at)})" if incident.contained_at else "")),
        ("Exposure at detection", f"{fmt_usd(incident.exposure_usd)} USD"),
        ("Withdrawn to the vault", f"{fmt_usd(incident.saved_usd)} USD"),
        ("Still at risk", f"{fmt_usd(incident.at_risk_usd)} USD"),
    ])

    pdf.h2("2. Classification proposal")
    pdf.para(f"{'Major' if d.is_major else 'Not major'} incident. {d.legal_basis}", style="B")
    pdf.para("Thresholds met: " + (", ".join(short_label(t) for t in d.thresholds_met) or "none") + ".")

    pdf.h2("3. Description")
    desc = _description(md)
    pdf.para(desc.replace("_(AI-drafted, review required)_", "(AI-drafted, review required)"))
    if d.ai_drafted_sections:
        pdf.para(f"AI-drafted sections, human review required: {', '.join(d.ai_drafted_sections)}.", 9, "I")

    pdf.h2("4. Classification criteria (RTS 2024/1772 Art. 9)")
    pdf.grid(["Criterion", "Value", "Threshold", "Met"],
             [[n, v, th, "YES" if met else "no"] for n, v, th, met in _criteria_rows(d.criteria)], (80, 38, 38, 22))

    pdf.h2("5. Actions taken")
    actions = [e for e in incident.timeline if e.kind == "action"]
    if actions:
        pdf.grid(["Time (UTC)", "Action", "Reference"],
                 [[iso(e.at), e.text, (e.ref[:18] + "...") if e.ref and len(e.ref) > 21 else (e.ref or "")]
                  for e in sorted(actions, key=lambda e: e.at)], (36, 104, 38))
    else:
        pdf.para("No automated action executed.")

    pdf.h2("6. Deadlines (Regulation (EU) 2025/301)")
    pdf.grid(["Report", "Due (UTC)", "Rule"], [
        ["Initial notification", iso(d.deadlines.initial_notification_due),
         "earlier of classification + 4 h and awareness + 24 h"],
        ["Intermediate report", iso(d.deadlines.intermediate_report_due), "initial notification + 72 h"],
        ["Final report", iso(d.deadlines.final_report_due), "intermediate report + 1 month (30 days)"],
    ], (44, 44, 90))

    pdf.h2("7. Third parties involved")
    pdf.para(", ".join(_section_items(md, 7)) or "none")

    pdf.h2("8. Human review")
    pdf.para(HUMAN_REVIEW)
    if d.submitted:
        pdf.para(f"Submitted by {d.submitted_by} at {iso(d.submitted_at)}.", style="B")
    else:
        pdf.para("Status: not submitted.")
        pdf.ln(2)
        pdf.para("Reviewed by: ______________________    Date: ____________    Signature: ______________________")

    pdf.add_page()
    pdf.h2("Annex - incident timeline")
    pdf.grid(["Time (UTC)", "Kind", "Event"],
             [[iso(e.at), e.kind, e.text] for e in sorted(incident.timeline, key=lambda e: (e.at, e.block_number or 0))],
             (36, 20, 122), size=8)
    return bytes(pdf.output())


def write_pdf(incident: Incident, out: Path | None = None) -> Path:
    out = out or settings.DATA_DIR / "reports" / f"{incident.id}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(render_pdf(incident))
    return out
