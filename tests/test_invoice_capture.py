from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models import Invoice, InvoiceItem, InvoiceSource, InvoiceStatus
from app.schemas.extraction import ExtractedInvoice, ExtractedItem
from app.services.encode_client import EncodeClientError
from app.services.invoice_service import InvoiceService


@pytest.mark.asyncio
async def test_parse_date_formats():
    assert InvoiceService._parse_date("2026-06-10") is not None
    assert InvoiceService._parse_date("10/06/2026") is not None
    assert InvoiceService._parse_date("invalid") is None


def test_extracted_invoice_validation():
    invoice = ExtractedInvoice(
        fornecedor="BH",
        data="2026-06-10",
        itens=[ExtractedItem(descricao="COCA COLA 2L", valor=Decimal("12.99"))],
        total=Decimal("12.99"),
    )
    assert invoice.fornecedor == "BH"
    assert len(invoice.itens) == 1


def test_extracted_item_categoria_normalization():
    item = ExtractedItem(
        descricao="ARROZ",
        valor=Decimal("10.00"),
        categoria="Alimentacao",
    )
    assert item.categoria == "alimentacao"

    invalid = ExtractedItem(
        descricao="ITEM",
        valor=Decimal("1.00"),
        categoria="invalida",
    )
    assert invalid.categoria is None


def test_extracted_invoice_cnpj_normalization():
    invoice = ExtractedInvoice(
        cnpj="12.345.678/0001-99",
        itens=[],
    )
    assert invoice.cnpj == "12345678000199"

    invalid = ExtractedInvoice(cnpj="123", itens=[])
    assert invalid.cnpj is None


def test_compute_adjusted_confidence_penalizes_total_mismatch():
    extracted = ExtractedInvoice(
        confianca=0.9,
        total=Decimal("100.00"),
        itens=[
            ExtractedItem(descricao="A", valor=Decimal("40.00"), categoria="alimentacao"),
            ExtractedItem(descricao="B", valor=Decimal("40.00"), categoria="bebidas"),
        ],
    )
    adjusted = InvoiceService.compute_adjusted_confidence(
        extracted,
        outros_count=0,
        unmapped_count=0,
    )
    assert adjusted == 0.75


def test_compute_adjusted_confidence_penalizes_weak_categories():
    extracted = ExtractedInvoice(
        confianca=0.85,
        total=Decimal("30.00"),
        itens=[
            ExtractedItem(descricao="A", valor=Decimal("10.00"), categoria="outros"),
            ExtractedItem(descricao="B", valor=Decimal("10.00"), categoria="outros"),
            ExtractedItem(descricao="C", valor=Decimal("10.00"), categoria="alimentacao"),
        ],
    )
    adjusted = InvoiceService.compute_adjusted_confidence(
        extracted,
        outros_count=2,
        unmapped_count=0,
    )
    assert adjusted == 0.75


def test_compute_adjusted_confidence_high_when_consistent():
    extracted = ExtractedInvoice(
        confianca=0.92,
        total=Decimal("20.00"),
        itens=[
            ExtractedItem(descricao="A", valor=Decimal("10.00"), categoria="alimentacao"),
            ExtractedItem(descricao="B", valor=Decimal("10.00"), categoria="bebidas"),
        ],
    )
    adjusted = InvoiceService.compute_adjusted_confidence(
        extracted,
        outros_count=0,
        unmapped_count=0,
    )
    assert adjusted == 0.92


@pytest.mark.asyncio
async def test_populate_from_extraction_saves_items_when_embed_fails():
    service = InvoiceService()
    db = AsyncMock()
    invoice = Invoice(
        id=uuid4(),
        source_type=InvoiceSource.PHOTO_AI,
        status=InvoiceStatus.PENDING,
    )
    extracted = ExtractedInvoice(
        itens=[
            ExtractedItem(
                descricao="Arroz",
                valor=Decimal("10.00"),
                categoria="alimentacao",
            )
        ],
    )
    category_id = uuid4()

    with (
        patch.object(
            service,
            "_load_category_slug_map",
            AsyncMock(return_value={"alimentacao": category_id}),
        ),
        patch(
            "app.services.invoice_service.encode_texts",
            AsyncMock(side_effect=EncodeClientError("down")),
        ),
    ):
        await service.populate_from_extraction(db, invoice, extracted)

    added = db.add.call_args[0][0]
    assert isinstance(added, InvoiceItem)
    assert added.description == "Arroz"
    assert added.embedding is None
    assert added.category_id == category_id

