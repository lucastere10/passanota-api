from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models import ConviteRole
from app.services.invite_service import InviteService


def _convite(**kwargs):
    defaults = {
        "id": uuid4(),
        "empresa_id": uuid4(),
        "role": ConviteRole.GESTOR,
        "accepted_at": None,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "email": "user@example.com",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_accept_invite_idempotent_for_existing_member():
    service = InviteService()
    db = AsyncMock()
    user_id = uuid4()
    convite = _convite()
    existing = SimpleNamespace(
        id=uuid4(),
        empresa_id=convite.empresa_id,
        user_id=user_id,
        nome="João",
    )

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing
    db.execute = AsyncMock(return_value=result_mock)

    funcionario = await service.accept_invite(db, convite, user_id, "João Silva")

    assert funcionario is existing
    assert funcionario.nome == "João Silva"
    assert convite.accepted_at is not None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_accept_invite_creates_new_member():
    service = InviteService()
    db = AsyncMock()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    convite = _convite()
    user_id = uuid4()
    funcionario = await service.accept_invite(db, convite, user_id, "Maria")

    assert funcionario.nome == "Maria"
    assert funcionario.user_id == user_id
    assert convite.accepted_at is not None
    db.add.assert_called_once()
