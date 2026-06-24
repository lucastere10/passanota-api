import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session
from app.tasks_auth import verify_cloud_tasks_request
from app.schemas.tasks import ProcessInvoiceTask, SendEmailTask
from app.services.task_worker import task_worker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/tasks", tags=["internal-tasks"])


@router.post("/process-invoice", status_code=status.HTTP_204_NO_CONTENT)
async def process_invoice_task(
    payload: ProcessInvoiceTask,
    request: Request,
    _auth: None = Depends(verify_cloud_tasks_request),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    retry_count = request.headers.get("X-CloudTasks-TaskRetryCount", "0")
    logger.info(
        "Processing invoice task invoice_id=%s retry=%s",
        payload.invoice_id,
        retry_count,
    )
    await task_worker.process_invoice(db, payload.invoice_id)


@router.post("/send-email", status_code=status.HTTP_204_NO_CONTENT)
async def send_email_task(
    payload: SendEmailTask,
    request: Request,
    _auth: None = Depends(verify_cloud_tasks_request),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    retry_count = request.headers.get("X-CloudTasks-TaskRetryCount", "0")
    logger.info(
        "Processing email task type=%s retry=%s",
        payload.type,
        retry_count,
    )
    await task_worker.send_email(db, payload)
