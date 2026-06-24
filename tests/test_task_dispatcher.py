import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.tasks import SendEmailTask
from app.services.task_dispatcher import dispatch_email_task, dispatch_invoice_processing


@pytest.mark.asyncio
async def test_dispatch_invoice_processing_runs_inline_when_disabled():
    invoice_id = uuid.uuid4()

    with (
        patch("app.services.task_dispatcher.settings.cloud_tasks_enabled", False),
        patch("app.services.task_dispatcher.asyncio.create_task") as create_task,
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
