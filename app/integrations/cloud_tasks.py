import json
import logging
from uuid import UUID

from google.cloud import tasks_v2

from app.config import get_settings
from app.schemas.tasks import ProcessInvoiceTask, SendEmailTask

logger = logging.getLogger(__name__)


class CloudTasksError(Exception):
    pass


def _task_handler_url(path: str) -> str:
    settings = get_settings()
    base = settings.task_handler_base_url.rstrip("/")
    if not base:
        raise CloudTasksError("TASK_HANDLER_BASE_URL is not configured")
    return f"{base}{path}"


def _create_http_task(*, queue: str, path: str, payload: dict) -> None:
    settings = get_settings()
    if not settings.gcp_project:
        raise CloudTasksError("GCP_PROJECT is not configured")
    if not settings.cloud_tasks_service_account:
        raise CloudTasksError("CLOUD_TASKS_SERVICE_ACCOUNT is not configured")

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(settings.gcp_project, settings.gcp_location, queue)
    url = _task_handler_url(path)
    body = json.dumps(payload).encode()

    task = tasks_v2.Task(
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=url,
            headers={"Content-Type": "application/json"},
            body=body,
            oidc_token=tasks_v2.OidcToken(
                service_account_email=settings.cloud_tasks_service_account,
                audience=url,
            ),
        )
    )

    client.create_task(request={"parent": parent, "task": task})
    logger.info("Enqueued Cloud Task queue=%s path=%s", queue, path)


async def enqueue_invoice_processing(invoice_id: UUID) -> None:
    settings = get_settings()
    payload = ProcessInvoiceTask(invoice_id=invoice_id).model_dump(mode="json")
    _create_http_task(
        queue=settings.cloud_tasks_invoice_queue,
        path="/internal/tasks/process-invoice",
        payload=payload,
    )


async def enqueue_email_task(task: SendEmailTask) -> None:
    settings = get_settings()
    _create_http_task(
        queue=settings.cloud_tasks_email_queue,
        path="/internal/tasks/send-email",
        payload=task.model_dump(mode="json"),
    )
