"""Backfill OpenAI embeddings after migration 011 (vector 512).

Run after `alembic upgrade head` with LLM_PROVIDER_API_KEY set:

    uv run python scripts/reembed.py
    uv run python scripts/reembed.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.models import Category, InvoiceItem
from app.services.encode_client import EncodeClientError, encode_texts

logger = logging.getLogger(__name__)

ITEM_BATCH_SIZE = 100


def _category_text(category: Category) -> str:
    parts = [category.name, category.slug]
    if category.keywords:
        parts.extend(category.keywords)
    return " ".join(part for part in parts if part)


async def reembed_categories(*, dry_run: bool) -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Category))
        categories = list(result.scalars().all())
        if not categories:
            logger.info("No categories to embed")
            return 0

        texts = [_category_text(category) for category in categories]
        logger.info("Embedding %d categories", len(categories))
        if dry_run:
            return len(categories)

        vectors = await encode_texts(texts)
        for category, vector in zip(categories, vectors, strict=True):
            category.embedding = vector
        await db.commit()
        return len(categories)


async def reembed_items(*, dry_run: bool) -> int:
    if dry_run:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(func.count()).select_from(InvoiceItem).where(InvoiceItem.embedding.is_(None))
            )
            count = result.scalar_one()
            logger.info("Would embed %d invoice items", count)
            return count

    total = 0
    while True:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(InvoiceItem)
                .where(InvoiceItem.embedding.is_(None))
                .order_by(InvoiceItem.id)
                .limit(ITEM_BATCH_SIZE)
            )
            items = list(result.scalars().all())
            if not items:
                break

            texts = [item.description for item in items]
            logger.info("Embedding %d invoice items (offset %d)", len(items), total)

            vectors = await encode_texts(texts)
            for item, vector in zip(items, vectors, strict=True):
                item.embedding = vector
            await db.commit()
            total += len(items)
    return total


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill OpenAI embeddings (512-d)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        categories = await reembed_categories(dry_run=args.dry_run)
        items = await reembed_items(dry_run=args.dry_run)
    except EncodeClientError:
        logger.exception("Embedding backfill failed")
        raise SystemExit(1) from None

    logger.info("Done. categories=%d items=%d dry_run=%s", categories, items, args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
