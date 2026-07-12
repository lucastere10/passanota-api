import httpx

from app.config import get_settings


class ResendError(Exception):
    pass


async def send_email(
    *,
    to: str | list[str],
    subject: str,
    html: str,
    text: str | None = None,
) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        raise ResendError("RESEND_API_KEY is not configured")

    recipients = [to] if isinstance(to, str) else to
    payload: dict[str, object] = {
        "from": settings.email_from,
        "to": recipients,
        "subject": subject,
        "html": html,
    }
    if text is not None:
        payload["text"] = text

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        raise ResendError(f"Resend API error ({response.status_code}): {response.text}")
