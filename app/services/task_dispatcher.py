import asyncio
import logging
from uuid import UUID

from app.config import get_settings
from app.integrations.cloud_tasks import CloudTasksError, enqueue_email_task, enqueue_invoice_processing
from app.schemas.tasks import SendEmailTask

logger = logging.getLogger(__name__)
settings = get_settings()


def _schedule_background_task(coro, *, label: str) -> None:
    task = asyncio.create_task(coro)

    def _on_done(done: asyncio.Task) -> None:
        if done.cancelled():
            logger.warning("Background task cancelled: %s", label)
            return
        exc = done.exception()
        if exc:
            logger.error("Background task failed: %s", label, exc_info=exc)

    task.add_done_callback(_on_done)
    logger.info("Scheduled background task: %s", label)


async def dispatch_invoice_processing(invoice_id: UUID) -> None:
    from app.services.task_worker import run_process_invoice_task

    if settings.cloud_tasks_enabled:
        try:
            await enqueue_invoice_processing(invoice_id)
            logger.info(
                "Invoice %s enqueued to Cloud Tasks (processing runs on %s)",
                invoice_id,
                settings.task_handler_base_url or "TASK_HANDLER_BASE_URL",
            )
        except CloudTasksError:
            logger.exception("Failed to enqueue invoice %s, running inline", invoice_id)
            _schedule_background_task(
                run_process_invoice_task(invoice_id),
                label=f"process_invoice:{invoice_id}",
            )
        return

    logger.info("Invoice %s scheduled for inline processing", invoice_id)
    _schedule_background_task(
        run_process_invoice_task(invoice_id),
        label=f"process_invoice:{invoice_id}",
    )


async def dispatch_email_task(task: SendEmailTask) -> None:
    from app.services.task_worker import run_send_email_task

    if settings.cloud_tasks_enabled:
        try:
            await enqueue_email_task(task)
        except CloudTasksError:
            logger.exception("Failed to enqueue email task type=%s, running inline", task.type)
            _schedule_background_task(
                run_send_email_task(task),
                label=f"send_email:{task.type}",
            )
        return

    _schedule_background_task(
        run_send_email_task(task),
        label=f"send_email:{task.type}",
    )
