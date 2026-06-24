import asyncio
import logging
from uuid import UUID

from app.config import get_settings
from app.integrations.cloud_tasks import CloudTasksError, enqueue_email_task, enqueue_invoice_processing
from app.schemas.tasks import SendEmailTask

logger = logging.getLogger(__name__)
settings = get_settings()


async def dispatch_invoice_processing(invoice_id: UUID) -> None:
    from app.services.task_worker import run_process_invoice_task

    if settings.cloud_tasks_enabled:
        try:
            await enqueue_invoice_processing(invoice_id)
        except CloudTasksError:
            logger.exception("Failed to enqueue invoice %s, running inline", invoice_id)
            asyncio.create_task(run_process_invoice_task(invoice_id))
        return

    asyncio.create_task(run_process_invoice_task(invoice_id))


async def dispatch_email_task(task: SendEmailTask) -> None:
    from app.services.task_worker import run_send_email_task

    if settings.cloud_tasks_enabled:
        try:
            await enqueue_email_task(task)
        except CloudTasksError:
            logger.exception("Failed to enqueue email task type=%s, running inline", task.type)
            asyncio.create_task(run_send_email_task(task))
        return

    asyncio.create_task(run_send_email_task(task))
