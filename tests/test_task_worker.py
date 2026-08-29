import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models import Invoice, InvoiceSource, InvoiceStatus
from app.schemas.tasks import ProcessInvoiceTask, SendEmailTask
from app.services.task_worker import TaskWorker


@pytest.mark.asyncio
async def test_process_invoice_skips_non_pending():
    worker = TaskWorker()
    db = AsyncMock()
    invoice_id = uuid.uuid4()
    invoice = Invoice(
        id=invoice_id,
        source_type=InvoiceSource.PHOTO_AI,
        status=InvoiceStatus.PARSED,
    )

    with patch(
        "app.services.invoice_service.invoice_service.get_by_id",
        AsyncMock(return_value=invoice),
    ):
        await worker.process_invoice(db, invoice_id)

    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_invoice_fails_without_original_photo():
    worker = TaskWorker()
    db = AsyncMock()
    invoice_id = uuid.uuid4()
    invoice = Invoice(
        id=invoice_id,
        source_type=InvoiceSource.PHOTO_AI,
        status=InvoiceStatus.PENDING,
        photo_original_path=None,
    )

    with patch(
        "app.services.invoice_service.invoice_service.get_by_id",
        AsyncMock(return_value=invoice),
    ):
        db.get = AsyncMock(return_value=invoice)
        await worker.process_invoice(db, invoice_id)

    assert invoice.status == InvoiceStatus.FAILED
    assert invoice.error_message == "Original photo not found in storage"
    db.rollback.assert_awaited()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_fail_invoice_rollbacks_aborted_transaction():
    worker = TaskWorker()
    db = AsyncMock()
    invoice_id = uuid.uuid4()
    invoice = Invoice(
        id=invoice_id,
        source_type=InvoiceSource.PHOTO_AI,
        status=InvoiceStatus.PENDING,
    )
    db.get = AsyncMock(return_value=invoice)

    await worker._fail_invoice(db, invoice, invoice_id, "expected 384 dimensions, not 512")

    db.rollback.assert_awaited_once()
    db.get.assert_awaited_once_with(Invoice, invoice_id)
    assert invoice.status == InvoiceStatus.FAILED
    assert "384" in invoice.error_message
    db.commit.assert_awaited()
    worker = TaskWorker()
    db = AsyncMock()
    task = SendEmailTask(type="magic_link", email=None)

    with pytest.raises(ValueError, match="email is required"):
        await worker.send_email(db, task)


def test_process_invoice_task_schema():
    invoice_id = uuid.uuid4()
    payload = ProcessInvoiceTask(invoice_id=invoice_id)
    assert payload.invoice_id == invoice_id


def test_send_email_task_schema():
    convite_id = uuid.uuid4()
    task = SendEmailTask(type="invite", convite_id=convite_id)
    assert task.type == "invite"
    assert task.convite_id == convite_id
