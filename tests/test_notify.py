from unittest.mock import MagicMock, patch

from src.backend import notify
from src.backend.config import settings


def test_port_465_uses_ssl_without_starttls_and_logs_in(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.hostinger.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 465)
    monkeypatch.setattr(settings, "SMTP_USER", "alerts@example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "pw")
    monkeypatch.setattr(settings, "ALERT_EMAIL_TO", "me@example.com")
    with patch("src.backend.notify.smtplib.SMTP_SSL") as ssl_cls, patch("src.backend.notify.smtplib.SMTP") as plain_cls:
        client = ssl_cls.return_value
        client.__enter__.return_value = client
        notify._send_blocking(notify.build_message("subject", "body"))
    ssl_cls.assert_called_once_with("smtp.hostinger.com", 465, timeout=15)
    plain_cls.assert_not_called()
    client.starttls.assert_not_called()
    client.login.assert_called_once_with("alerts@example.com", "pw")
    client.send_message.assert_called_once()


def test_port_587_uses_starttls(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_STARTTLS", True)
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "ALERT_EMAIL_TO", "me@example.com")
    with patch("src.backend.notify.smtplib.SMTP") as plain_cls:
        client = plain_cls.return_value
        client.__enter__.return_value = client
        notify._send_blocking(notify.build_message("s", "b"))
    client.starttls.assert_called_once()
    client.login.assert_not_called()


def test_not_configured_means_in_app_only(monkeypatch):
    import asyncio

    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "ALERT_EMAIL_TO", "")
    assert not notify.email_configured()
    assert asyncio.run(notify.send_email("s", "b")) == "in-app only"


def test_hostinger_token_sends_through_the_api_from_the_first_mailbox(monkeypatch):
    import asyncio
    import sys
    import types

    sent = {}
    fake = types.ModuleType("hostinger_mail_api")
    fake.Configuration = lambda access_token: ("cfg", access_token)

    class Client:
        def __init__(self, cfg): self.cfg = cfg
        def __enter__(self): return self
        def __exit__(self, *a): return False

    fake.ApiClient = Client
    box = types.SimpleNamespace(resource_id="ACfirst")
    fake.AccountApi = lambda c: types.SimpleNamespace(
        get_current_account=lambda: types.SimpleNamespace(data=types.SimpleNamespace(mailboxes=[box])))
    fake.V1SendRequest = lambda **kw: kw
    fake.SendApi = lambda c: types.SimpleNamespace(send_email=lambda mailbox, req: sent.update(mailbox=mailbox, req=req))
    monkeypatch.setitem(sys.modules, "hostinger_mail_api", fake)
    monkeypatch.setattr(settings, "HOSTINGER_MAIL_API_TOKEN", "tok")
    monkeypatch.setattr(settings, "HOSTINGER_MAILBOX_ID", "")
    monkeypatch.setattr(settings, "ALERT_EMAIL_TO", "me@example.com")
    monkeypatch.setattr(settings, "SMTP_HOST", "")

    assert notify.email_configured()
    status = asyncio.run(notify.send_email("Subject", "Body"))
    assert status == "emailed to me@example.com (Hostinger)"
    assert sent["mailbox"] == "ACfirst" and sent["req"] == {"to": ["me@example.com"], "subject": "Subject", "text": "Body"}


def test_a_token_without_a_recipient_stays_in_app_only(monkeypatch):
    import asyncio

    monkeypatch.setattr(settings, "HOSTINGER_MAIL_API_TOKEN", "tok")
    monkeypatch.setattr(settings, "ALERT_EMAIL_TO", "")
    assert not notify.email_configured()
    assert asyncio.run(notify.send_email("s", "b")) == "in-app only"
