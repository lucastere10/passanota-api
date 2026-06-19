from app.config import get_settings
from app.integrations.resend import send_email


def _magic_link_email_html(link: str) -> str:
    return f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2>PassaNota</h2>
      <p>Clique no botão abaixo para acessar sua conta:</p>
      <p><a href="{link}" style="display:inline-block;padding:12px 24px;background:#0d9488;color:#fff;text-decoration:none;border-radius:6px;">Entrar na plataforma</a></p>
      <p style="color:#666;font-size:14px;">Se você não solicitou este e-mail, ignore-o.</p>
    </div>
    """


def _invite_email_html(link: str, empresa_nome: str, role_label: str) -> str:
    return f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2>Convite PassaNota</h2>
      <p>Você foi convidado para participar da empresa <strong>{empresa_nome}</strong> como <strong>{role_label}</strong>.</p>
      <p>Clique no botão abaixo para aceitar o convite e finalizar seu cadastro:</p>
      <p><a href="{link}" style="display:inline-block;padding:12px 24px;background:#0d9488;color:#fff;text-decoration:none;border-radius:6px;">Aceitar convite</a></p>
      <p style="color:#666;font-size:14px;">Este link expira em 7 dias.</p>
    </div>
    """


def _interest_email_html(email: str, nome: str | None, mensagem: str | None) -> str:
    nome_line = f"<p><strong>Nome:</strong> {nome}</p>" if nome else ""
    msg_line = f"<p><strong>Mensagem:</strong> {mensagem}</p>" if mensagem else ""
    return f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2>Novo interesse na PassaNota</h2>
      <p><strong>E-mail:</strong> {email}</p>
      {nome_line}
      {msg_line}
    </div>
    """


async def send_magic_link_email(email: str, link: str) -> None:
    await send_email(
        to=email,
        subject="Seu link de acesso — PassaNota",
        html=_magic_link_email_html(link),
    )


async def send_invite_email(email: str, link: str, empresa_nome: str, role: str) -> None:
    role_label = "Gestor" if role == "gestor" else "Operador"
    await send_email(
        to=email,
        subject=f"Convite para {empresa_nome} — PassaNota",
        html=_invite_email_html(link, empresa_nome, role_label),
    )


async def send_interest_notification(email: str, nome: str | None, mensagem: str | None) -> None:
    settings = get_settings()
    if not settings.platform_admin_notify_email:
        return
    await send_email(
        to=settings.platform_admin_notify_email,
        subject="Novo interesse na plataforma — PassaNota",
        html=_interest_email_html(email, nome, mensagem),
    )
