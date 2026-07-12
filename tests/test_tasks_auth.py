from unittest.mock import MagicMock, patch

from app.tasks_auth import task_oidc_audience


def test_task_oidc_audience_uses_task_handler_base_url():
    request = MagicMock()
    request.url.path = "/internal/tasks/process-invoice"

    with patch("app.tasks_auth.get_settings") as get_settings:
        get_settings.return_value.task_handler_base_url = (
            "https://passanota-api-elokeq3cta-uc.a.run.app"
        )
        assert (
            task_oidc_audience(request)
            == "https://passanota-api-elokeq3cta-uc.a.run.app/internal/tasks/process-invoice"
        )


def test_task_oidc_audience_falls_back_to_https_when_base_url_missing():
    request = MagicMock()
    request.url.path = "/internal/tasks/send-email"
    request.url.replace.return_value = (
        "https://passanota-api.example.run.app/internal/tasks/send-email"
    )

    with patch("app.tasks_auth.get_settings") as get_settings:
        get_settings.return_value.task_handler_base_url = ""
        assert (
            task_oidc_audience(request)
            == "https://passanota-api.example.run.app/internal/tasks/send-email"
        )
        request.url.replace.assert_called_once_with(scheme="https")
