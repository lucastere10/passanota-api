from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.services.admin_service import (
    DEFAULT_MONTHLY_INVOICE_LIMIT,
    AdminService,
    EmpresaClearDataError,
    EmpresaNotFoundError,
    month_start_utc,
)

EMPRESA_ID = UUID("00000000-0000-0000-0000-000000000001")


def test_month_start_utc():
    ref = datetime(2026, 6, 15, 14, 30, tzinfo=timezone.utc)
    start = month_start_utc(ref)
    assert start == datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_default_monthly_limit_constant():
    assert DEFAULT_MONTHLY_INVOICE_LIMIT == 200


@pytest.mark.asyncio
async def test_get_empresa_usage_unlimited():
    service = AdminService()
    empresa = SimpleNamespace(id="00000000-0000-0000-0000-000000000001", monthly_invoice_limit=None)
    db = AsyncMock()

    async def fake_count(db, empresa_id, *, month_start=None):
        return 5 if month_start is not None else 42

    service.count_invoices_for_empresa = fake_count  # type: ignore[method-assign]

    usage = await service.get_empresa_usage(db, empresa)

    assert usage["invoices_this_month"] == 5
    assert usage["invoices_total"] == 42
    assert usage["is_unlimited"] is True
    assert usage["limit_reached"] is False
    assert usage["usage_percentage"] is None


@pytest.mark.asyncio
async def test_get_empresa_usage_limit_reached():
    service = AdminService()
    empresa = SimpleNamespace(id="00000000-0000-0000-0000-000000000001", monthly_invoice_limit=200)
    db = AsyncMock()

    async def fake_count(db, empresa_id, *, month_start=None):
        return 200 if month_start is not None else 500

    service.count_invoices_for_empresa = fake_count  # type: ignore[method-assign]

    usage = await service.get_empresa_usage(db, empresa)

    assert usage["limit_reached"] is True
    assert usage["usage_percentage"] == 100.0


@pytest.mark.asyncio
async def test_assert_empresa_can_capture_suspended():
    service = AdminService()
    empresa = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        is_active=False,
        monthly_invoice_limit=200,
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=empresa)

    with pytest.raises(ValueError, match="suspensa"):
        await service.assert_empresa_can_capture(db, empresa.id)


@pytest.mark.asyncio
async def test_assert_empresa_can_capture_quota_exceeded():
    service = AdminService()
    empresa = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        is_active=True,
        monthly_invoice_limit=200,
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=empresa)
    service.get_empresa_usage = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "limit_reached": True,
            "invoices_this_month": 200,
            "monthly_invoice_limit": 200,
        }
    )

    with pytest.raises(ValueError, match="Limite mensal"):
        await service.assert_empresa_can_capture(db, empresa.id)


def test_admin_empresa_update_validates_negative_limit():
    from app.schemas.admin import AdminEmpresaUpdate

    with pytest.raises(ValueError):
        AdminEmpresaUpdate(monthly_invoice_limit=-1)


def _make_suspended_empresa(**overrides):
    defaults = {
        "id": EMPRESA_ID,
        "nome": "Empresa Teste",
        "is_active": False,
        "pin": "hashed-pin",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _mock_delete_result(count: int) -> MagicMock:
    result = MagicMock()
    result.rowcount = count
    return result


@pytest.mark.asyncio
async def test_clear_empresa_data_not_found():
    service = AdminService()
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)

    with pytest.raises(EmpresaNotFoundError):
        await service.clear_empresa_data(db, EMPRESA_ID, confirm_nome="Empresa Teste")


@pytest.mark.asyncio
async def test_clear_empresa_data_rejects_active_empresa():
    service = AdminService()
    db = AsyncMock()
    db.get = AsyncMock(return_value=_make_suspended_empresa(is_active=True))

    with pytest.raises(EmpresaClearDataError, match="suspensa"):
        await service.clear_empresa_data(db, EMPRESA_ID, confirm_nome="Empresa Teste")


@pytest.mark.asyncio
async def test_clear_empresa_data_rejects_wrong_confirm_nome():
    service = AdminService()
    db = AsyncMock()
    db.get = AsyncMock(return_value=_make_suspended_empresa())

    with pytest.raises(EmpresaClearDataError, match="nome de confirmação"):
        await service.clear_empresa_data(db, EMPRESA_ID, confirm_nome="Nome Errado")


@pytest.mark.asyncio
@patch("app.services.admin_service.invoice_photo_storage.clear_empresa_prefix", new_callable=AsyncMock)
async def test_clear_empresa_data_success(mock_clear_storage):
    mock_clear_storage.return_value = 4
    service = AdminService()
    empresa = _make_suspended_empresa()
    db = AsyncMock()
    db.get = AsyncMock(return_value=empresa)
    db.execute = AsyncMock(
        side_effect=[
            _mock_delete_result(10),
            _mock_delete_result(2),
            _mock_delete_result(1),
            _mock_delete_result(3),
            _mock_delete_result(5),
        ]
    )
    db.commit = AsyncMock()

    result = await service.clear_empresa_data(db, EMPRESA_ID, confirm_nome="Empresa Teste")

    assert result == {
        "invoices_deleted": 10,
        "funcionarios_deleted": 5,
        "convites_deleted": 3,
        "dispositivos_deleted": 2,
        "pairing_sessions_deleted": 1,
        "storage_objects_deleted": 4,
    }
    assert empresa.pin is None
    db.commit.assert_awaited_once()
    mock_clear_storage.assert_awaited_once_with(EMPRESA_ID)


@pytest.mark.asyncio
@patch("app.services.admin_service.invoice_photo_storage.clear_empresa_prefix", new_callable=AsyncMock)
async def test_clear_empresa_data_idempotent_empty_empresa(mock_clear_storage):
    mock_clear_storage.return_value = 0
    service = AdminService()
    empresa = _make_suspended_empresa()
    db = AsyncMock()
    db.get = AsyncMock(return_value=empresa)
    db.execute = AsyncMock(side_effect=[_mock_delete_result(0)] * 5)
    db.commit = AsyncMock()

    result = await service.clear_empresa_data(db, EMPRESA_ID, confirm_nome="Empresa Teste")

    assert all(value == 0 for value in result.values())
    db.commit.assert_awaited_once()
