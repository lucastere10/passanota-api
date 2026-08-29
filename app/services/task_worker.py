import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.integrations.resend import ResendError
from app.integrations.supabase import SupabaseAuthError, SupabaseConfigError, generate_magic_link
from app.models import Convite, Invoice, InvoiceStatus
from app.schemas.tasks import SendEmailTask
from app.services.email_service import (
    send_interest_notification,
    send_magic_link_email,
)
from app.services.image.preprocessor import preprocess_image
from app.services.image.storage import StorageError, invoice_photo_storage
from app.services.vision import VisionExtractorError, get_vision_extractor

logger = logging.getLogger(__name__)
settings = get_settings()


class TaskWorker:
    async def process_invoice(self, db: AsyncSession, invoice_id: uuid.UUID) -> None:
        from app.services.invoice_service import invoice_service

        logger.info("Invoice %s: processing started", invoice_id)

        invoice = await invoice_service.get_by_id(db, invoice_id)
        if not invoice:
            logger.warning("Invoice %s not found for processing", invoice_id)
            return

        if invoice.status != InvoiceStatus.PENDING:
            logger.info("Invoice %s already processed (status=%s)", invoice_id, invoice.status)
            return

        invoice.processing_started_at = datetime.now(timezone.utc)
        await db.commit()

        if not invoice.photo_original_path:
            await self._fail_invoice(
                db, invoice, invoice_id, "Original photo not found in storage"
            )
            return

        logger.info("Invoice %s: downloading original photo", invoice_id)
        try:
            image_bytes = await invoice_photo_storage.download(invoice.photo_original_path)
        except StorageError as exc:
            await self._fail_invoice(db, invoice, invoice_id, str(exc))
            return

        logger.info("Invoice %s: preprocessing image (%d bytes)", invoice_id, len(image_bytes))
        try:
            preprocess_result = await asyncio.to_thread(preprocess_image, image_bytes)
        except Exception as exc:
            await self._fail_invoice(db, invoice, invoice_id, f"Preprocess failed: {exc}")
            return

        _, processed_path = invoice_photo_storage.build_paths(invoice.id, invoice.empresa_id)
        try:
            await invoice_photo_storage.upload(
                processed_path,
                preprocess_result.processed_bytes,
                preprocess_result.content_type,
            )
            invoice.photo_processed_path = processed_path
            await db.commit()
        except StorageError as exc:
            logger.warning("Invoice %s: processed photo upload skipped: %s", invoice_id, exc)

        logger.info("Invoice %s: running vision extraction (provider=%s)", invoice_id, settings.llm_provider)
        try:
            extractor = get_vision_extractor()
            extraction_result = await extractor.extract(
                preprocess_result.processed_bytes,
                preprocess_result.content_type,
            )
            invoice.ai_raw_response = extraction_result.raw_response
            invoice.ai_model = extraction_result.model
            invoice.extracted_at = datetime.now(timezone.utc)
            await invoice_service.populate_from_extraction(
                db, invoice, extraction_result.invoice
            )
            logger.info(
                "Invoice %s: extracted %d items",
                invoice_id,
                len(extraction_result.invoice.itens),
            )
            await db.execute(
                text("SELECT normalize_invoice_items(:invoice_id)"),
                {"invoice_id": invoice.id},
            )
            invoice.status = InvoiceStatus.PARSED
            invoice.error_message = None
        except (VisionExtractorError, ValueError) as exc:
            await self._fail_invoice(db, invoice, invoice_id, str(exc))
            return
        except Exception as exc:
            logger.exception("Invoice %s: unexpected extraction error", invoice_id)
            await self._fail_invoice(db, invoice, invoice_id, f"Extraction failed: {exc}")
            return

        await db.commit()
        logger.info("Invoice %s: processing finished status=%s", invoice_id, invoice.status)

    async def _fail_invoice(
        self,
        db: AsyncSession,
        invoice: Invoice,
        invoice_id: uuid.UUID,
        message: str,
    ) -> None:
        await db.rollback()
        failed = await db.get(Invoice, invoice_id)
        if failed is None:
            logger.error("Invoice %s not found after failure", invoice_id)
            return
        failed.status = InvoiceStatus.FAILED
        failed.error_message = message[:2000]
        await db.commit()
        logger.error("Invoice %s: processing failed — %s", invoice_id, message)


    async def send_email(self, db: AsyncSession, task: SendEmailTask) -> None:
        if task.type == "magic_link":
            if not task.email:
                raise ValueError("email is required for magic_link tasks")
            redirect_to = f"{settings.frontend_url.rstrip('/')}/auth/confirm"
            link = await generate_magic_link(task.email, redirect_to)
            await send_magic_link_email(task.email, link)
            return

        if task.type == "invite":
            if not task.convite_id:
                raise ValueError("convite_id is required for invite tasks")
            convite = await db.get(Convite, task.convite_id)
            if not convite:
                logger.warning("Convite %s not found for email task", task.convite_id)
                return
            from app.services.invite_service import invite_service

            await invite_service.send_invite_email_for_convite(db, convite)
            convite.email_sent_at = datetime.now(timezone.utc)
            await db.commit()
            return

        if task.type == "interest":
            if not task.email:
                raise ValueError("email is required for interest tasks")
            await send_interest_notification(task.email, task.nome, task.mensagem)
            return

        raise ValueError(f"Unknown email task type: {task.type}")


task_worker = TaskWorker()


async def run_process_invoice_task(invoice_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await task_worker.process_invoice(db, invoice_id)
        except Exception as exc:
            logger.exception("Unhandled error processing invoice %s", invoice_id)
            await db.rollback()
            invoice = await db.get(Invoice, invoice_id)
            if invoice and invoice.status == InvoiceStatus.PENDING:
                invoice.status = InvoiceStatus.FAILED
                invoice.error_message = f"Processing failed: {exc}"
                await db.commit()


async def run_send_email_task(task: SendEmailTask) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await task_worker.send_email(db, task)
        except (ResendError, SupabaseConfigError, SupabaseAuthError, ValueError):
            logger.exception("Email task failed type=%s", task.type)
            raise
