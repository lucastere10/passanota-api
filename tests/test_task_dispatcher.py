import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.cloud_tasks import CloudTasksError
from app.schemas.tasks import SendEmailTask
from app.services.task_dispatcher import dispatch_email_task, dispatch_invoice_processing


def _swallow_coro(coro):
    coro.close()
    return MagicMock()


@pytest.mark.asyncio
async def test_dispatch_invoice_processing_runs_inline_when_disabled():
    invoice_id = uuid.uuid4()

    with (
        patch("app.services.task_dispatcher.settings.cloud_tasks_enabled", False),
        patch("app.services.task_dispatcher.settings.app_role", "all"),
        patch("app.services.task_dispatcher.asyncio.create_task", side_effect=_swallow_coro) as create_task,
    ):
        await dispatch_invoice_processing(invoice_id)
        create_task.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_email_task_enqueues_when_enabled():
    task = SendEmailTask(type="magic_link", email="user@example.com")

    with (
        patch("app.services.task_dispatcher.settings.cloud_tasks_enabled", True),
        patch(
            "app.services.task_dispatcher.enqueue_email_task",
            new_callable=AsyncMock,
        ) as enqueue,
    ):
        await dispatch_email_task(task)
        enqueue.assert_awaited_once_with(task)


@pytest.mark.asyncio
async def test_dispatch_invoice_http_role_skips_inline_on_enqueue_failure():
    invoice_id = uuid.uuid4()

    with (
        patch("app.services.task_dispatcher.settings.cloud_tasks_enabled", True),
        patch("app.services.task_dispatcher.settings.app_role", "http"),
        patch(
            "app.services.task_dispatcher.enqueue_invoice_processing",
            new_callable=AsyncMock,
            side_effect=CloudTasksError("fail"),
        ),
        patch("app.services.task_dispatcher.asyncio.create_task") as create_task,
    ):
        await dispatch_invoice_processing(invoice_id)
        create_task.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_invoice_http_role_skips_inline_when_tasks_disabled():
    invoice_id = uuid.uuid4()

    with (
        patch("app.services.task_dispatcher.settings.cloud_tasks_enabled", False),
        patch("app.services.task_dispatcher.settings.app_role", "http"),
        patch("app.services.task_dispatcher.asyncio.create_task") as create_task,
    ):
        await dispatch_invoice_processing(invoice_id)
        create_task.assert_not_called()
