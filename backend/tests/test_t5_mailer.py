"""E-mailing the DORA draft (backend/mailer.py). No network: smtplib is replaced by a fake."""
import pytest

from backend import mailer
from backend.tests.test_t5_factories import run_reacted_incident


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context):
        self.tls = True

    def login(self, user, password):
        self.user = user

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture
def smtp_env(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setenv("MAIL_ALLOWED_RECIPIENTS", "me@example.com,@team.example")
    monkeypatch.setattr(mailer, "_sent", [])
    FakeSMTP.sent = []


def test_sends_pdf_attachment(smtp_env, monkeypatch):
    incident, _ = run_reacted_incident(monkeypatch)
    r = mailer.send_report(incident, "me@example.com", b"%PDF-1.3 fake", smtp_factory=FakeSMTP)
    assert r["sent_to"] == "me@example.com"
    (msg,) = FakeSMTP.sent
    assert msg["Subject"].startswith("[DRAFT] DORA initial notification - INC-20261011-001")
    (att,) = list(msg.iter_attachments())
    assert att.get_filename() == "INC-20261011-001-DORA-draft.pdf" and att.get_content_type() == "application/pdf"
    assert "NOT been sent to any authority" in msg.get_body(("plain",)).get_content()


@pytest.mark.parametrize("to,status", [("not-an-email", 400), ("stranger@evil.example", 403)])
def test_rejects(smtp_env, monkeypatch, to, status):
    incident, _ = run_reacted_incident(monkeypatch)
    with pytest.raises(mailer.MailError) as e:
        mailer.send_report(incident, to, b"%PDF", smtp_factory=FakeSMTP)
    assert e.value.status == status and FakeSMTP.sent == []


def test_domain_allow_and_rate_limit(smtp_env, monkeypatch):
    incident, _ = run_reacted_incident(monkeypatch)
    for _ in range(mailer.RATE_LIMIT):
        mailer.send_report(incident, "anyone@team.example", b"%PDF", smtp_factory=FakeSMTP)
    with pytest.raises(mailer.MailError) as e:
        mailer.send_report(incident, "anyone@team.example", b"%PDF", smtp_factory=FakeSMTP)
    assert e.value.status == 429 and len(FakeSMTP.sent) == mailer.RATE_LIMIT


def test_not_configured(monkeypatch):
    for k in ("SMTP_USER", "SMTP_PASSWORD", "MAIL_ALLOWED_RECIPIENTS"):
        monkeypatch.delenv(k, raising=False)
    incident, _ = run_reacted_incident(monkeypatch)
    with pytest.raises(mailer.MailError) as e:
        mailer.send_report(incident, "me@example.com", b"%PDF", smtp_factory=FakeSMTP)
    assert e.value.status == 503 and not mailer.configured()
