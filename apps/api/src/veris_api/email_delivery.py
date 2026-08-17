from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import quote

import httpx

from veris_api.config import Settings, get_settings


class EmailDeliveryError(RuntimeError):
    pass


def action_url(purpose: str, token: str, *, settings: Settings | None = None) -> str:
    runtime = settings or get_settings()
    route = "verify" if purpose == "verify_email" else "reset-password"
    return f"{runtime.public_base_url.rstrip('/')}/{route}#token={quote(token)}"


def _message(purpose: str, url: str) -> tuple[str, str, str]:
    if purpose == "verify_email":
        subject = "Verify your Thesos account"
        heading = "Complete your archive access"
        body = "This link verifies the email address used to register for the Thesos private alpha."
    else:
        subject = "Reset your Thesos password"
        heading = "Reset your archive access"
        body = "This link lets you choose a new Thesos password. It expires after 30 minutes."
    text = f"{heading}\n\n{body}\n\n{url}\n\nIf you did not request this, ignore this message."
    markup = (
        f"<h1>{html.escape(heading)}</h1><p>{html.escape(body)}</p>"
        f'<p><a href="{html.escape(url, quote=True)}">Continue to Thesos</a></p>'
        "<p>If you did not request this, ignore this message.</p>"
    )
    return subject, text, markup


async def send_action_email(
    recipient: str,
    purpose: str,
    token: str,
    *,
    settings: Settings | None = None,
) -> None:
    runtime = settings or get_settings()
    url = action_url(purpose, token, settings=runtime)
    subject, text, markup = _message(purpose, url)
    if runtime.email_delivery == "file":
        directory = Path(runtime.development_mail_directory)
        directory.mkdir(parents=True, exist_ok=True)
        safe_recipient = recipient.replace("@", "_at_").replace(".", "_")
        destination = directory / f"{purpose}-{safe_recipient}.html"
        destination.write_text(
            f"<!-- {text} -->\n{markup}",
            encoding="utf-8",
        )
        return

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {runtime.resend_api_key}"},
            json={
                "from": runtime.email_from,
                "to": [recipient],
                "subject": subject,
                "text": text,
                "html": markup,
            },
        )
    if response.status_code >= 300:
        raise EmailDeliveryError(f"Transactional email failed with status {response.status_code}")
