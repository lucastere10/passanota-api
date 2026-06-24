from decimal import Decimal

import pytest

from app.schemas.extraction import ExtractedInvoice, ExtractedItem
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
