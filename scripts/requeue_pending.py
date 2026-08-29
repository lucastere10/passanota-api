"""Re-enqueue invoices stuck in pending (e.g. after a worker crash or schema mismatch).

    uv run python scripts/requeue_pending.py
    uv run python scripts/requeue_pending.py --inline
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Invoice, InvoiceStatus
from app.services.task_dispatcher import dispatch_invoice_processing
from app.services.task_worker import run_process_invoice_task

logger = logging.getLogger(__name__)


async def _pending_ids() -> list[UUID]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Invoice.id).where(Invoice.status == InvoiceStatus.PENDING))
        return list(result.scalars().all())


async def main() -> None:
    parser = argparse.ArgumentParser(description="Requeue pending invoices")
    parser.add_argument(
        "--inline",
        action="store_true",
        help="Process in this process instead of Cloud Tasks",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    invoice_ids = await _pending_ids()
    if not invoice_ids:
        logger.info("No pending invoices")
        return

    logger.info("Requeueing %d pending invoice(s)", len(invoice_ids))
    for invoice_id in invoice_ids:
        if args.inline:
            await run_process_invoice_task(invoice_id)
        else:
            await dispatch_invoice_processing(invoice_id)
        logger.info("Requeued %s", invoice_id)


if __name__ == "__main__":
    asyncio.run(main())
