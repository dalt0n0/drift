"""
Notification dispatch: Slack webhook, SMTP email, HTTP webhook.
Called from routers via BackgroundTasks (non-blocking).
"""
import asyncio
import logging
from typing import Any

import httpx
import aiosmtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("drift.notifications")


async def dispatch_finding_notification(finding: Any, event: str) -> None:
    """Fire Slack + email for critical/high findings on create."""
    if event != "created":
        return
    if finding.severity not in ("critical", "high"):
        return

    title = f"[{finding.severity.upper()}] {finding.title}"
    body = (
        f"Finding: {finding.code}\n"
        f"Severity: {finding.severity}\n"
        f"Target: {finding.target_id}\n"
        f"Summary: {finding.summary[:200]}"
    )
    await asyncio.gather(
        _send_slack(title, body),
        _send_email(
            subject=f"Drift — {title}",
            body=body,
            to=settings.SMTP_FROM,  # notify the team's shared inbox
        ),
        return_exceptions=True,
    )


async def _send_slack(title: str, body: str, webhook_url: str | None = None) -> None:
    """
    webhook_url: If None, look up from DB integration config (not implemented here;
    pass explicitly from callers that have DB access).
    """
    if not webhook_url:
        return  # No webhook configured

    payload = {
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": title}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"```{body}```"}},
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
    except Exception as exc:
        logger.error("Slack notification failed: %s", exc)


async def send_slack(webhook_url: str, title: str, body: str) -> None:
    await _send_slack(title, body, webhook_url)


async def send_email(to: str, subject: str, body: str) -> None:
    await _send_email(to=to, subject=subject, body=body)


async def _send_email(to: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        return  # SMTP not configured

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        smtp = aiosmtplib.SMTP(
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            use_tls=False,
            start_tls=settings.SMTP_TLS,
        )
        await smtp.connect()
        if settings.SMTP_USER:
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASS)
        await smtp.send_message(msg)
        await smtp.quit()
    except Exception as exc:
        logger.error("Email notification failed: %s", exc)


async def send_webhook(url: str, payload: dict) -> None:
    """POST arbitrary JSON to a webhook URL."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
    except Exception as exc:
        logger.error("Webhook notification failed: %s", exc)
