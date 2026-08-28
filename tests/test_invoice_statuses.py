from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models import InvoiceStatus
from app.routers.invoices import _parse_status_ids
from app.services.invoice_service import InvoiceService


@pytest.mark.asyncio
async def test_list_statuses_returns_id_and_status():
    service = InvoiceService()
    db = AsyncMock()
    invoice_id = uuid4()
    empresa_id = uuid4()
    result_mock = MagicMock()
    result_mock.all.return_value = [SimpleNamespace(id=invoice_id, status=InvoiceStatus.PENDING)]
    db.execute = AsyncMock(return_value=result_mock)

    rows = await service.list_statuses(db, [invoice_id], empresa_id=empresa_id)

    assert len(rows) == 1
    assert rows[0].id == invoice_id
    assert rows[0].status == InvoiceStatus.PENDING
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_statuses_empty_ids_skips_query():
    service = InvoiceService()
    db = AsyncMock()

    rows = await service.list_statuses(db, [], empresa_id=uuid4())

    assert rows == []
    db.execute.assert_not_called()


def test_parse_status_ids_rejects_invalid_and_too_many():
    first = uuid4()
    second = uuid4()
    assert _parse_status_ids(f"{first},{second}") == [first, second]

    with pytest.raises(HTTPException) as empty:
        _parse_status_ids(" , ")
    assert empty.value.status_code == 422

    with pytest.raises(HTTPException) as invalid:
        _parse_status_ids("not-a-uuid")
    assert invalid.value.status_code == 422

    too_many = ",".join(str(uuid4()) for _ in range(21))
    with pytest.raises(HTTPException) as overflow:
        _parse_status_ids(too_many)
    assert overflow.value.status_code == 422
