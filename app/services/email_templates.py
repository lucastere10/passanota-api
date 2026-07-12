from __future__ import annotations

import html
from dataclasses import dataclass

from app.config import get_settings

FONT_STACK = 'Helvetica, "Helvetica Neue", Arial, sans-serif'
PRIMARY = "#0c4f4a"
PRIMARY_FOREGROUND = "#fcfaf8"
EMAIL_MAX_WIDTH = "620px"
CARD_PADDING = "48px 44px"

# Alinhar com Supabase Auth → OTP expiry no dashboard.
MAGIC_LINK_EXPIRY_LABEL = "15 minutos"
INVITE_EXPIRY_LABEL = "7 dias"

BRAND_TAGLINE = "Controle de custos via notas fiscais"
BRAND_HEADLINE_LINE1 = "Cada nota fiscal registrada."
BRAND_HEADLINE_LINE2 = "Cada gasto sob controle."
BRAND_SIGNATURE = f"PassaNOTA — {BRAND_TAGLINE}"

BENEFITS_ITEMS = (
    "Fotografar notas fiscais",
    "Extração automática dos dados",
    "Acompanhar despesas",
    "Descobrir para onde o dinheiro da empresa está indo",
)

BTN_SHADOW = "0 1px 2px rgba(0,0,0,0.06), 0 4px 12px rgba(12,79,74,0.18)"


@dataclass(frozen=True)
class EmailColors:
    background: str
    card: str
    foreground: str
    muted: str
    surface: str
    border: str


EMAIL_COLORS_LIGHT = EmailColors(
    background="#f7f4f1",
    card="#fcfaf8",
    foreground="#1a1a1f",
    muted="#5c5a55",
    surface="#f0ece8",
    border="#e8e4de",
)

EMAIL_COLORS_DARK = EmailColors(
    background="#1a1a1d",
    card="#1a1a1d",
    foreground="#e8e7e3",
    muted="#9a9892",
    surface="#232327",
    border="#2e2e32",
)

LIGHT = EMAIL_COLORS_LIGHT
DARK = EMAIL_COLORS_DARK


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def _dark_mode_styles() -> str:
    return f"""
  :root {{
    color-scheme: light dark;
    supported-color-schemes: light dark;
  }}
  @media (prefers-color-scheme: dark) {{
    .email-bg {{ background-color: {DARK.background} !important; }}
    .email-card {{ background-color: {DARK.card} !important; border-color: {DARK.border} !important; }}
    .email-text {{ color: {DARK.foreground} !important; }}
    .email-muted {{ color: {DARK.muted} !important; }}
    .email-brand {{ color: {DARK.foreground} !important; }}
    .email-title {{ color: {DARK.foreground} !important; }}
    .email-surface {{ background-color: {DARK.surface} !important; }}
    .email-surface-label {{ color: {DARK.muted} !important; }}
    .email-surface-value {{ color: {DARK.foreground} !important; }}
    .email-field-label {{ color: {DARK.muted} !important; }}
    .email-field-value {{ color: {DARK.foreground} !important; }}
    .email-divider {{ border-color: {DARK.border} !important; }}
    .email-fallback {{ color: {DARK.muted} !important; }}
    .email-fallback-url {{ color: {DARK.foreground} !important; }}
    .email-benefits-title {{ color: {DARK.foreground} !important; }}
    .email-benefit-item {{ color: {DARK.foreground} !important; }}
    .email-tagline {{ color: {DARK.muted} !important; }}
    .email-headline {{ color: {DARK.foreground} !important; }}
  }}
  """


def render_brand_header() -> str:
    return f"""
    <div style="text-align:center;padding:40px 24px 28px;">
      <div style="margin-bottom:16px;">
        <span class="email-monogram"
              style="font-family:{FONT_STACK};font-size:32px;font-weight:700;color:{PRIMARY};">/N</span>
      </div>
      <div style="margin-bottom:12px;">
        <span class="email-brand"
              style="font-family:{FONT_STACK};font-size:26px;font-weight:700;letter-spacing:-0.02em;color:{LIGHT.foreground};">
          PassaNOTA
        </span>
      </div>
      <p class="email-tagline"
         style="margin:0 0 10px;font-family:{FONT_STACK};font-size:12px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{LIGHT.muted};">
        {BRAND_TAGLINE}
      </p>
      <p class="email-headline"
         style="margin:0;font-family:{FONT_STACK};font-size:15px;line-height:1.55;color:{LIGHT.foreground};">
        {BRAND_HEADLINE_LINE1}<br>{BRAND_HEADLINE_LINE2}
      </p>
    </div>
    """


def render_divider() -> str:
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0;">
      <tr>
        <td class="email-divider" style="border-top:1px solid {LIGHT.border};font-size:0;line-height:0;">&nbsp;</td>
      </tr>
    </table>
    """


def render_cta_button(label: str, href: str) -> str:
    safe_label = _escape(label)
    safe_href = _escape(href)
    return f"""
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:28px 0 8px;">
      <tr>
        <td align="center">
          <a href="{safe_href}" class="email-btn"
             style="display:inline-block;padding:16px 36px;background-color:{PRIMARY};color:{PRIMARY_FOREGROUND};font-family:{FONT_STACK};font-size:16px;font-weight:700;letter-spacing:-0.01em;text-decoration:none;border-radius:12px;box-shadow:{BTN_SHADOW};">
            {safe_label}
          </a>
        </td>
      </tr>
    </table>
    """


def render_fallback_link(link: str) -> str:
    safe_link = _escape(link)
    return f"""
    <div style="text-align:center;margin-top:8px;">
      <p class="email-fallback"
         style="margin:0 0 8px;font-family:{FONT_STACK};font-size:13px;line-height:1.5;color:{LIGHT.muted};">
        Se o botão não funcionar, copie e cole este link:
      </p>
      <p class="email-fallback-url"
         style="margin:0;font-family:{FONT_STACK};font-size:13px;line-height:1.5;color:{LIGHT.foreground};word-break:break-all;">
        {safe_link}
      </p>
    </div>
    """


def render_benefits_block(items: tuple[str, ...] = BENEFITS_ITEMS) -> str:
    rows = ""
    for item in items:
        safe_item = _escape(item)
        rows += f"""
        <tr>
          <td class="email-benefit-item"
              style="padding:6px 0;font-family:{FONT_STACK};font-size:14px;line-height:1.5;color:{LIGHT.foreground};text-align:left;">
            <span style="color:{PRIMARY};font-weight:700;">✓</span>&nbsp;&nbsp;{safe_item}
          </td>
        </tr>
        """

    return f"""
    <div style="text-align:center;">
      <p class="email-benefits-title"
         style="margin:0 0 16px;font-family:{FONT_STACK};font-size:15px;font-weight:600;color:{LIGHT.foreground};">
        O que você pode fazer
      </p>
      <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:360px;margin:0 auto;">
        {rows}
      </table>
    </div>
    """


def render_saas_footer(*, expiry_line: str | None, disclaimer: str) -> str:
    expiry_block = ""
    if expiry_line:
        safe_expiry = _escape(expiry_line)
        expiry_block = f"""
        <p class="email-text"
           style="margin:0 0 12px;font-family:{FONT_STACK};font-size:13px;line-height:1.5;color:{LIGHT.foreground};text-align:center;">
          {safe_expiry}
        </p>
        """

    safe_disclaimer = _escape(disclaimer)
    return f"""
    <tr>
      <td align="center" style="padding:8px 24px 16px;">
        {render_divider()}
        {expiry_block}
        <p class="email-muted"
           style="margin:0 0 16px;font-family:{FONT_STACK};font-size:13px;line-height:1.55;color:{LIGHT.muted};text-align:center;">
          {safe_disclaimer}
        </p>
        <p class="email-brand"
           style="margin:0;font-family:{FONT_STACK};font-size:13px;font-weight:600;color:{LIGHT.foreground};text-align:center;">
          PassaNOTA
        </p>
        <p class="email-muted"
           style="margin:4px 0 0;font-family:{FONT_STACK};font-size:12px;line-height:1.5;color:{LIGHT.muted};text-align:center;">
          {BRAND_TAGLINE}
        </p>
      </td>
    </tr>
    """


def render_email_html(
    *,
    title: str,
    preheader: str,
    body_html: str,
    footer_html: str | None = None,
    expiry_line: str | None = None,
    disclaimer: str | None = None,
) -> str:
    safe_title = _escape(title)
    safe_preheader = _escape(preheader)

    footer_block = ""
    if footer_html is not None or expiry_line is not None or disclaimer is not None:
        footer_block = render_saas_footer(
            expiry_line=expiry_line,
            disclaimer=disclaimer or footer_html or "",
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>{safe_title}</title>
  <style>
  {_dark_mode_styles()}
  </style>
</head>
<body class="email-bg" style="margin:0;padding:0;background-color:{LIGHT.background};">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">
    {safe_preheader}
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="email-bg"
         style="background-color:{LIGHT.background};">
    <tr>
      <td align="center" style="padding:24px 16px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:{EMAIL_MAX_WIDTH};">
          <tr>
            <td align="center">
              {render_brand_header()}
            </td>
          </tr>
          <tr>
            <td style="padding:0 8px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     class="email-card"
                     style="background-color:{LIGHT.card};border:1px solid {LIGHT.border};border-radius:10px;">
                <tr>
                  <td align="center" style="padding:{CARD_PADDING};">
                    <h1 class="email-title"
                        style="margin:0 0 24px;font-family:{FONT_STACK};font-size:22px;font-weight:600;line-height:1.3;color:{LIGHT.foreground};text-align:center;">
                      {safe_title}
                    </h1>
                    {body_html}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          {footer_block}
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _plain_brand_header() -> str:
    return (
        f"PassaNOTA\n{BRAND_TAGLINE}\n"
        f"{BRAND_HEADLINE_LINE1}\n{BRAND_HEADLINE_LINE2}"
    )


def _plain_brand_footer(*, expiry_line: str | None = None, disclaimer: str | None = None) -> str:
    lines: list[str] = ["", "—"]
    if expiry_line:
        lines.append(expiry_line)
    if disclaimer:
        lines.append(disclaimer)
    lines.extend(["PassaNOTA", BRAND_TAGLINE])
    settings = get_settings()
    lines.append(settings.frontend_url)
    return "\n".join(lines)


def _plain_benefits() -> str:
    items = "\n".join(f"✓ {item}" for item in BENEFITS_ITEMS)
    return f"\nO que você pode fazer\n{items}"


def _plain_fallback(link: str) -> str:
    return f"\nSe o botão não funcionar, copie e cole este link:\n{link}"


def _body_text(content: str, *, margin_bottom: str = "0") -> str:
    return f"""
    <p class="email-text"
       style="margin:0 0 {margin_bottom};font-family:{FONT_STACK};font-size:15px;line-height:1.65;color:{LIGHT.foreground};text-align:center;">
      {content}
    </p>
    """


def _body_text_multi(paragraphs: list[str]) -> str:
    parts = []
    for i, paragraph in enumerate(paragraphs):
        margin = "16px" if i < len(paragraphs) - 1 else "0"
        parts.append(_body_text(paragraph, margin_bottom=margin))
    return "".join(parts)


def _render_invite_surface(empresa_nome: str, role_label: str) -> str:
    safe_empresa = _escape(empresa_nome)
    safe_role = _escape(role_label)
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" cellpadding="0" cellspacing="0"
                 class="email-surface"
                 style="background-color:{LIGHT.surface};border-radius:8px;">
            <tr>
              <td style="padding:24px 32px;text-align:center;">
                <p class="email-surface-label"
                   style="margin:0 0 4px;font-family:{FONT_STACK};font-size:12px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{LIGHT.muted};">
                  Empresa
                </p>
                <p class="email-surface-value"
                   style="margin:0 0 16px;font-family:{FONT_STACK};font-size:16px;font-weight:600;line-height:1.4;color:{LIGHT.foreground};">
                  {safe_empresa}
                </p>
                <p class="email-surface-label"
                   style="margin:0 0 4px;font-family:{FONT_STACK};font-size:12px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{LIGHT.muted};">
                  Papel
                </p>
                <p class="email-surface-value"
                   style="margin:0;font-family:{FONT_STACK};font-size:16px;font-weight:600;line-height:1.4;color:{LIGHT.foreground};">
                  {safe_role}
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    """


def magic_link_content(link: str) -> tuple[str, str]:
    body_html = (
        _body_text_multi(
            [
                "Entre na sua conta para continuar utilizando o PassaNOTA.",
                "Fotografe notas fiscais pelo computador ou celular.",
                (
                    "Nós extraímos automaticamente os dados e transformamos cada compra "
                    "em visibilidade sobre os custos da sua empresa."
                ),
            ]
        )
        + render_cta_button("Entrar no PassaNOTA", link)
        + render_divider()
        + render_benefits_block()
        + render_divider()
        + render_fallback_link(link)
    )

    disclaimer = "Se você não solicitou este acesso, ignore esta mensagem com segurança."
    expiry = f"Este link expira em {MAGIC_LINK_EXPIRY_LABEL}."

    html_out = render_email_html(
        title="Acesse sua conta",
        preheader="Seu link de acesso à PassaNota está pronto.",
        body_html=body_html,
        expiry_line=expiry,
        disclaimer=disclaimer,
    )

    text_out = (
        f"{_plain_brand_header()}\n\n"
        "Acesse sua conta\n\n"
        "Entre na sua conta para continuar utilizando o PassaNOTA.\n\n"
        "Fotografe notas fiscais pelo computador ou celular.\n\n"
        "Nós extraímos automaticamente os dados e transformamos cada compra "
        "em visibilidade sobre os custos da sua empresa.\n\n"
        f"{link}"
        f"{_plain_benefits()}"
        f"{_plain_fallback(link)}"
        f"{_plain_brand_footer(expiry_line=expiry, disclaimer=disclaimer)}"
    )

    return html_out, text_out


def invite_content(link: str, empresa_nome: str, role_label: str) -> tuple[str, str]:
    body_html = (
        _body_text(
            "Você foi convidado para participar de uma empresa na PassaNOTA.",
            margin_bottom="0",
        )
        + _render_invite_surface(empresa_nome, role_label)
        + _body_text(
            "Clique no botão abaixo para aceitar o convite e finalizar seu cadastro.",
            margin_bottom="0",
        )
        + render_cta_button("Aceitar convite", link)
        + render_divider()
        + render_benefits_block()
        + render_divider()
        + render_fallback_link(link)
    )

    disclaimer = "Se você não solicitou este convite, ignore esta mensagem com segurança."
    expiry = f"Este link expira em {INVITE_EXPIRY_LABEL}."

    html_out = render_email_html(
        title="Você foi convidado",
        preheader=f"Convite para {empresa_nome} como {role_label}.",
        body_html=body_html,
        expiry_line=expiry,
        disclaimer=disclaimer,
    )

    text_out = (
        f"{_plain_brand_header()}\n\n"
        "Você foi convidado\n\n"
        "Você foi convidado para participar de uma empresa na PassaNOTA.\n\n"
        f"Empresa: {empresa_nome}\n"
        f"Papel: {role_label}\n\n"
        f"{link}"
        f"{_plain_benefits()}"
        f"{_plain_fallback(link)}"
        f"{_plain_brand_footer(expiry_line=expiry, disclaimer=disclaimer)}"
    )

    return html_out, text_out


def interest_content(email: str, nome: str | None, mensagem: str | None) -> tuple[str, str]:
    safe_email = _escape(email)

    fields_html = f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 auto;">
      <tr>
        <td align="center">
          <table role="presentation" cellpadding="0" cellspacing="0"
                 class="email-surface"
                 style="background-color:{LIGHT.surface};border-radius:8px;">
            <tr>
              <td style="padding:24px 32px;text-align:center;">
                <p class="email-surface-label"
                   style="margin:0 0 4px;font-family:{FONT_STACK};font-size:12px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{LIGHT.muted};">
                  E-mail
                </p>
                <p class="email-surface-value"
                   style="margin:0;font-family:{FONT_STACK};font-size:16px;font-weight:600;line-height:1.4;color:{LIGHT.foreground};word-break:break-all;">
                  {safe_email}
                </p>
    """

    text_lines = [f"E-mail: {email}"]

    if nome:
        safe_nome = _escape(nome)
        fields_html += f"""
                <p class="email-surface-label"
                   style="margin:16px 0 4px;font-family:{FONT_STACK};font-size:12px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{LIGHT.muted};">
                  Nome
                </p>
                <p class="email-surface-value"
                   style="margin:0;font-family:{FONT_STACK};font-size:16px;font-weight:600;line-height:1.4;color:{LIGHT.foreground};">
                  {safe_nome}
                </p>
        """
        text_lines.append(f"Nome: {nome}")

    if mensagem:
        safe_mensagem = _escape(mensagem)
        fields_html += f"""
                <p class="email-surface-label"
                   style="margin:16px 0 4px;font-family:{FONT_STACK};font-size:12px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{LIGHT.muted};">
                  Mensagem
                </p>
                <p class="email-surface-value"
                   style="margin:0;font-family:{FONT_STACK};font-size:16px;font-weight:600;line-height:1.4;color:{LIGHT.foreground};">
                  {safe_mensagem}
                </p>
        """
        text_lines.append(f"Mensagem: {mensagem}")

    fields_html += """
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    """

    html_out = render_email_html(
        title="Novo interesse na plataforma",
        preheader=f"Novo interesse registrado: {email}",
        body_html=fields_html,
        expiry_line=None,
        disclaimer="Notificação interna da plataforma.",
    )

    text_out = (
        f"{_plain_brand_header()}\n\n"
        "Novo interesse na plataforma\n\n"
        + "\n".join(text_lines)
        + _plain_brand_footer(disclaimer="Notificação interna da plataforma.")
    )

    return html_out, text_out
