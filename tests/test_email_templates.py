from app.services.email_templates import (
    BENEFITS_ITEMS,
    BRAND_TAGLINE,
    MAGIC_LINK_EXPIRY_LABEL,
    interest_content,
    invite_content,
    magic_link_content,
)


def test_magic_link_html_has_premium_saas_layout():
    html_body, text_body = magic_link_content("https://app.passanota.com/auth/confirm?token=abc")

    assert "PassaNOTA" in html_body
    assert "/N" in html_body
    assert BRAND_TAGLINE in html_body
    assert "Cada nota fiscal registrada." in html_body
    assert 'name="color-scheme" content="light dark"' in html_body
    assert "prefers-color-scheme: dark" in html_body
    assert "max-width:620px" in html_body
    assert "padding:48px 44px" in html_body
    assert "#f7f4f1" in html_body
    assert "#1a1a1d" in html_body
    assert "#232327" in html_body
    assert "#0c4f4a" in html_body
    assert "border-radius:12px" in html_body
    assert "box-shadow:" in html_body
    assert "Acesse sua conta" in html_body
    assert "Entrar no PassaNOTA" in html_body
    assert "O que você pode fazer" in html_body
    for item in BENEFITS_ITEMS:
        assert item in html_body
    assert "Se o botão não funcionar" in html_body
    assert f"Este link expira em {MAGIC_LINK_EXPIRY_LABEL}." in html_body
    assert "ignore esta mensagem com segurança" in html_body
    assert "https://app.passanota.com/auth/confirm?token=abc" in html_body
    assert html_body.strip().startswith("<!DOCTYPE html>")

    assert "https://app.passanota.com/auth/confirm?token=abc" in text_body
    assert "<" not in text_body
    assert "O que você pode fazer" in text_body
    assert f"Este link expira em {MAGIC_LINK_EXPIRY_LABEL}." in text_body


def test_invite_html_escapes_user_content():
    html_body, text_body = invite_content(
        "https://app.passanota.com/auth/confirm?token=xyz",
        "<script>alert(1)</script>",
        "Gestor",
    )

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_body
    assert "<script>alert(1)</script>" not in html_body
    assert "Você foi convidado" in html_body
    assert "Aceitar convite" in html_body
    assert "Este link expira em 7 dias." in html_body
    assert "O que você pode fazer" in html_body
    assert "Se o botão não funcionar" in html_body

    assert "<script>alert(1)</script>" in text_body
    assert "Gestor" in text_body
    assert "https://app.passanota.com/auth/confirm?token=xyz" in text_body


def test_interest_content_includes_optional_fields():
    html_body, text_body = interest_content(
        "user@example.com",
        "Maria Silva",
        "Quero saber mais sobre o produto.",
    )

    assert "Novo interesse na plataforma" in html_body
    assert "/N" in html_body
    assert BRAND_TAGLINE in html_body
    assert "user@example.com" in html_body
    assert "Maria Silva" in html_body
    assert "Quero saber mais sobre o produto." in html_body
    assert "O que você pode fazer" not in html_body
    assert "Se o botão não funcionar" not in html_body
    assert "Notificação interna da plataforma." in html_body

    assert "user@example.com" in text_body
    assert "Maria Silva" in text_body
    assert "Quero saber mais sobre o produto." in text_body
    assert "<" not in text_body


def test_interest_content_without_optional_fields():
    html_body, text_body = interest_content("solo@example.com", None, None)

    assert "solo@example.com" in html_body
    assert "Nome" not in html_body
    assert "Mensagem" not in html_body

    assert "solo@example.com" in text_body
    assert "Nome:" not in text_body
