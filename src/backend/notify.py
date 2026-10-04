"""Email delivery for alerts, over SMTP. Does nothing (and says so) when SMTP is not configured."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from src.backend.config import settings

logger = logging.getLogger(__name__)


def email_configured() -> bool:
    """Alerts can be emailed: a recipient is set and either the Hostinger API token or SMTP is."""
    return bool(settings.ALERT_EMAIL_TO and (settings.HOSTINGER_MAIL_API_TOKEN or settings.SMTP_HOST))


def build_message(subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER or settings.ALERT_EMAIL_TO
    msg["To"] = settings.ALERT_EMAIL_TO
    msg.set_content(body)
    return msg


def _send_blocking(msg: EmailMessage) -> None:
    """Port 465 is SSL from the first byte (Hostinger's default); other ports use STARTTLS when enabled."""
    if settings.SMTP_PORT == 465:
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
    else:
        smtp = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
    with smtp:
        if settings.SMTP_PORT != 465 and settings.SMTP_STARTTLS:
            smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


def _send_hostinger_blocking(subject: str, body: str) -> None:
    """Send through Hostinger's Agentic Mail API from the token's mailbox."""
    import hostinger_mail_api as hostinger

    config = hostinger.Configuration(access_token=settings.HOSTINGER_MAIL_API_TOKEN)
    with hostinger.ApiClient(config) as client:
        mailbox = settings.HOSTINGER_MAILBOX_ID
        if not mailbox:
            boxes = hostinger.AccountApi(client).get_current_account().data.mailboxes
            if not boxes:
                raise RuntimeError("the Hostinger token has no mailbox")
            mailbox = boxes[0].resource_id
        hostinger.SendApi(client).send_email(
            mailbox, hostinger.V1SendRequest(to=[settings.ALERT_EMAIL_TO], subject=subject, text=body)
        )


async def send_email(subject: str, body: str) -> str:
    """Send one email and return a short delivery status for the alert record."""
    if not email_configured():
        return "in-app only"
    try:
        if settings.HOSTINGER_MAIL_API_TOKEN:
            await asyncio.to_thread(_send_hostinger_blocking, subject, body)
            return f"emailed to {settings.ALERT_EMAIL_TO} (Hostinger)"
        await asyncio.to_thread(_send_blocking, build_message(subject, body))
        return f"emailed to {settings.ALERT_EMAIL_TO}"
    except Exception as e:  # never let a mail problem stop the scanner
        logger.warning(f"Alert email failed: {e}")
        return f"email failed: {str(e)[:120]}"
