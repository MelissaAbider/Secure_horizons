"""E-mail the DORA initial notification draft (PDF) to a person (T5). SMTP only (e.g. Gmail with an app password).

This sends a DRAFT to a human for review. It is NOT the submission to the regulator (POST /api/incidents/{id}/submit).
Configuration, read from the environment (.env) at call time; the password is never logged or returned:
  SMTP_HOST (default smtp.gmail.com), SMTP_PORT (default 587, STARTTLS), SMTP_USER, SMTP_PASSWORD,
  MAIL_FROM (default SMTP_USER), MAIL_ALLOWED_RECIPIENTS: comma list of addresses and/or @domains allowed to receive.
"""
from __future__ import annotations

import logging
import os
import re
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

from backend.dora import fmt_usd, iso, short_label
from backend.models import Incident

logger = logging.getLogger("t5.mailer")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
RATE_LIMIT = 3          # e-mails
RATE_WINDOW_S = 60.0    # per minute, whole process
_sent: list[float] = []
_lock = threading.Lock()


class MailError(Exception):
    """status: HTTP-like code for the caller (400 bad address, 403 not allowed, 429 rate limit, 503 not configured,
    502 SMTP failure)."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def _cfg() -> dict:
    user = os.environ.get("SMTP_USER", "").strip()
    return {
        "host": os.environ.get("SMTP_HOST", "").strip() or "smtp.gmail.com",
        "port": int(os.environ.get("SMTP_PORT", "").strip() or 587),
        "user": user,
        "password": os.environ.get("SMTP_PASSWORD", "").replace(" ", ""),  # Gmail shows app passwords in groups of 4
        "from": os.environ.get("MAIL_FROM", "").strip() or user,
        "allowed": [x.strip().lower() for x in os.environ.get("MAIL_ALLOWED_RECIPIENTS", "").split(",") if x.strip()],
    }


def configured() -> bool:
    c = _cfg()
    return bool(c["user"] and c["password"] and c["allowed"])


def recipient_allowed(address: str, allowed: list[str]) -> bool:
    a = address.lower()
    return any(a == x or (x.startswith("@") and a.endswith(x)) for x in allowed)


def build_message(incident: Incident, pdf: bytes, to: str, sender: str) -> EmailMessage:
    d = incident.dora
    msg = EmailMessage()
    msg["Subject"] = f"[DRAFT] DORA initial notification - {incident.id} - human review required"
    msg["From"] = sender
    msg["To"] = to
    thresholds = ", ".join(short_label(t) for t in d.thresholds_met) if d else "n/a"
    msg.set_content(
        f"Secure Horizons - DORA initial notification draft for {incident.id}\n\n"
        f"Incident: {incident.title}\nStatus: {incident.status}\nSeverity: {incident.severity}\n"
        f"Exposure at detection: {fmt_usd(incident.exposure_usd)} USD\n"
        f"Withdrawn to the vault: {fmt_usd(incident.saved_usd)} USD\n"
        f"Still at risk: {fmt_usd(incident.at_risk_usd)} USD\n"
        f"Classification proposal: {'MAJOR' if d and d.is_major else 'not major'} ({thresholds})\n"
        f"Initial notification due: {iso(d.deadlines.initial_notification_due) if d else 'n/a'}\n\n"
        "The attached PDF is a DRAFT prepared by the monitoring platform. It has NOT been sent to any authority.\n"
        "An authorised person must review it and submit it.\n\n"
        "Synthetic data - hackathon demo.\n")
    msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=f"{incident.id}-DORA-draft.pdf")
    return msg


def send_report(incident: Incident, to: str, pdf: bytes, smtp_factory=None) -> dict:
    """Validate, rate-limit, then send. Raises MailError; never leaks the password."""
    to = (to or "").strip()
    if not EMAIL_RE.match(to) or len(to) > 254:
        raise MailError(400, "invalid e-mail address")
    c = _cfg()
    if not (c["user"] and c["password"]):
        raise MailError(503, "e-mail not configured: set SMTP_USER and SMTP_PASSWORD in .env")
    if not c["allowed"]:
        raise MailError(503, "no allowed recipients: set MAIL_ALLOWED_RECIPIENTS in .env")
    if not recipient_allowed(to, c["allowed"]):
        raise MailError(403, "this address is not in MAIL_ALLOWED_RECIPIENTS")
    with _lock:
        now = time.monotonic()
        _sent[:] = [t for t in _sent if now - t < RATE_WINDOW_S]
        if len(_sent) >= RATE_LIMIT:
            raise MailError(429, f"rate limit: at most {RATE_LIMIT} e-mails per minute")
        _sent.append(now)
    msg = build_message(incident, pdf, to, c["from"])
    factory = smtp_factory or smtplib.SMTP
    try:
        with factory(c["host"], c["port"], timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(c["user"], c["password"])
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise MailError(502, "SMTP login refused: check SMTP_USER / SMTP_PASSWORD (Gmail app password)") from None
    except (smtplib.SMTPException, OSError) as e:
        logger.warning("SMTP send failed: %s", type(e).__name__)
        raise MailError(502, f"SMTP error: {type(e).__name__}") from None
    logger.info("DORA draft %s e-mailed to %s", incident.id, to)
    return {"sent_to": to, "incident_id": incident.id, "subject": msg["Subject"]}


def main(argv: list[str] | None = None) -> int:
    """make dora-email TO=you@example.com : e-mail the offline scenario PDF (same as make dora-pdf-demo)."""
    import argparse
    import sys

    from backend import settings  # noqa: F401  (loads .env)
    from backend.dora_pdf import _demo_incident, render_pdf

    parser = argparse.ArgumentParser(prog="python -m backend.mailer")
    parser.add_argument("--to", required=True)
    args = parser.parse_args(argv)
    incident = _demo_incident()
    try:
        r = send_report(incident, args.to, render_pdf(incident))
    except MailError as e:
        print(f"NOT SENT ({e.status}): {e.detail}", file=sys.stderr)
        return 1
    print(f"SENT {r['incident_id']} to {r['sent_to']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
