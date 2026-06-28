from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.dashboard_service import DashboardService


def _make_row(**kwargs):
    return SimpleNamespace(**kwargs)


@pytest.mark.asyncio
async def test_spend_by_category_includes_slug():
    service = DashboardService()
    db = AsyncMock()
    rows = [
        _make_row(label="Alimentação", slug="alimentacao", amount=Decimal("100"), count=5),
        _make_row(label="Outros", slug="outros", amount=Decimal("50"), count=2),
    ]
    result_mock = MagicMock()
    result_mock.all.return_value = rows
    db.execute = AsyncMock(return_value=result_mock)

    response = await service.spend_by_category(db, empresa_id=uuid4())

    assert len(response.items) == 2
    assert response.items[0].slug == "alimentacao"
    assert response.items[0].label == "Alimentação"


@pytest.mark.asyncio
async def test_spend_over_time_by_category_groups_segments():
    service = DashboardService()
    db = AsyncMock()
    bucket = datetime(2026, 6, 1, tzinfo=timezone.utc)
    rows = [
        _make_row(
            bucket=bucket,
            category_name="Alimentação",
            category_slug="alimentacao",
            amount=Decimal("80"),
        ),
        _make_row(
            bucket=bucket,
            category_name="Bebidas",
            category_slug="bebidas",
            amount=Decimal("20"),
        ),
    ]
    result_mock = MagicMock()
    result_mock.__iter__ = MagicMock(return_value=iter(rows))
    db.execute = AsyncMock(return_value=result_mock)

    response = await service.spend_over_time_by_category(db, empresa_id=uuid4())

    assert len(response.points) == 1
    assert response.points[0].date == "2026-06-01"
    assert len(response.points[0].segments) == 2
    assert "Alimentação" in response.categories
    assert "Bebidas" in response.categories


@pytest.mark.asyncio
async def test_top_emitters_by_category_stacked():
    service = DashboardService()
    db = AsyncMock()
    emitter_id = uuid4()

    top_rows = [_make_row(id=emitter_id, label="Mercado X", total=Decimal("150"))]
    segment_rows = [
        _make_row(
            emitter_id=emitter_id,
            category_name="Alimentação",
            category_slug="alimentacao",
            amount=Decimal("100"),
        ),
        _make_row(
            emitter_id=emitter_id,
            category_name="Bebidas",
            category_slug="bebidas",
            amount=Decimal("50"),
        ),
    ]

    top_result = MagicMock()
    top_result.all.return_value = top_rows
    segment_result = MagicMock()
    segment_result.__iter__ = MagicMock(return_value=iter(segment_rows))
    db.execute = AsyncMock(side_effect=[top_result, segment_result])

    response = await service.top_emitters_by_category(db, empresa_id=uuid4())

    assert len(response.items) == 1
    assert response.items[0].label == "Mercado X"
    assert len(response.items[0].segments) == 2
    assert response.items[0].segments[0].label == "Alimentação"


@pytest.mark.asyncio
async def test_top_emitters_empty_by_category():
    service = DashboardService()
    db = AsyncMock()
    top_result = MagicMock()
    top_result.all.return_value = []
    db.execute = AsyncMock(return_value=top_result)

    response = await service.top_emitters_by_category(db, empresa_id=uuid4())

    assert response.items == []
    assert response.categories == []
