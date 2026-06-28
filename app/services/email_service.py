from app.config import get_settings
from app.integrations.resend import send_email
from app.services.email_templates import (
    interest_content,
    invite_content,
    magic_link_content,
)


async def send_magic_link_email(email: str, link: str) -> None:
    html_body, text_body = magic_link_content(link)
    await send_email(
        to=email,
        subject="Seu link de acesso — PassaNota",
        html=html_body,
        text=text_body,
    )


async def send_invite_email(email: str, link: str, empresa_nome: str, role: str) -> None:
    role_label = "Gestor" if role == "gestor" else "Operador"
    html_body, text_body = invite_content(link, empresa_nome, role_label)
    await send_email(
        to=email,
        subject=f"Convite para {empresa_nome} — PassaNota",
        html=html_body,
        text=text_body,
    )


async def send_interest_notification(email: str, nome: str | None, mensagem: str | None) -> None:
    settings = get_settings()
    if not settings.platform_admin_notify_email:
        return
    html_body, text_body = interest_content(email, nome, mensagem)
    await send_email(
        to=settings.platform_admin_notify_email,
        subject="Novo interesse na plataforma — PassaNota",
        html=html_body,
        text=text_body,
    )
