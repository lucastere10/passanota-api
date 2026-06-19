import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.supabase import generate_magic_link
from app.models import Convite, Empresa, Funcionario, PlatformAdmin
from app.schemas.auth_api import (
    AuthMeResponse,
    EmpresaMembership,
    PendingInvite,
    UserProfile,
)
from app.services.email_service import send_interest_notification, send_magic_link_email
from app.services.invite_service import invite_service


def _normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    async def can_request_magic_link(self, db: AsyncSession, email: str) -> bool:
        normalized = _normalize_email(email)
        settings = get_settings()

        if settings.platform_admin_email and normalized == _normalize_email(settings.platform_admin_email):
            return True

        admin_result = await db.execute(
            select(PlatformAdmin.id).where(PlatformAdmin.email == normalized).limit(1)
        )
        if admin_result.scalar_one_or_none():
            return True

        pending = await invite_service.get_pending_by_email(db, normalized)
        if pending:
            return True

        convite_accepted = await db.execute(
            select(Convite.id).where(Convite.email == normalized, Convite.accepted_at.is_not(None)).limit(1)
        )
        if convite_accepted.scalar_one_or_none():
            return True

        return False

    async def send_magic_link(self, db: AsyncSession, email: str) -> None:
        normalized = _normalize_email(email)
        settings = get_settings()

        if not await self.can_request_magic_link(db, normalized):
            return

        redirect_to = f"{settings.frontend_url.rstrip('/')}/auth/confirm"
        link = await generate_magic_link(normalized, redirect_to)
        await send_magic_link_email(normalized, link)

    async def ensure_platform_admin_bootstrap(
        self, db: AsyncSession, user_id: uuid.UUID, email: str | None
    ) -> PlatformAdmin | None:
        if not email:
            return None

        normalized = _normalize_email(email)
        settings = get_settings()

        result = await db.execute(select(PlatformAdmin).where(PlatformAdmin.user_id == user_id))
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        if settings.platform_admin_email and normalized == _normalize_email(settings.platform_admin_email):
            admin = PlatformAdmin(user_id=user_id, email=normalized)
            db.add(admin)
            await db.flush()
            await db.commit()
            return admin

        return None

    async def get_me(self, db: AsyncSession, user_id: uuid.UUID, email: str | None) -> AuthMeResponse:
        await self.ensure_platform_admin_bootstrap(db, user_id, email)

        admin_result = await db.execute(select(PlatformAdmin).where(PlatformAdmin.user_id == user_id))
        platform_admin = admin_result.scalar_one_or_none()
        is_platform_admin = platform_admin is not None

        func_result = await db.execute(
            select(Funcionario, Empresa)
            .join(Empresa, Empresa.id == Funcionario.empresa_id)
            .where(Funcionario.user_id == user_id, Funcionario.is_active.is_(True))
        )
        memberships = func_result.all()
        empresas = [
            EmpresaMembership(
                id=empresa.id,
                nome=empresa.nome,
                role=funcionario.role.value,
                funcionario_id=funcionario.id,
                funcionario_nome=funcionario.nome,
            )
            for funcionario, empresa in memberships
        ]

        pending_invite = None
        if email:
            convite = await invite_service.get_pending_by_email(db, email)
            if convite:
                empresa = await db.get(Empresa, convite.empresa_id)
                pending_invite = PendingInvite(
                    id=convite.id,
                    empresa_id=convite.empresa_id,
                    empresa_nome=empresa.nome if empresa else "",
                    role=convite.role.value,
                )

        profile_complete = (len(empresas) > 0 or is_platform_admin) and pending_invite is None

        display_nome = None
        if platform_admin and platform_admin.nome:
            display_nome = platform_admin.nome
        elif empresas and empresas[0].funcionario_nome:
            display_nome = empresas[0].funcionario_nome

        return AuthMeResponse(
            user=UserProfile(id=user_id, email=email, nome=display_nome),
            is_platform_admin=is_platform_admin,
            empresas=empresas,
            pending_invite=pending_invite,
            profile_complete=profile_complete,
        )

    async def complete_profile(
        self, db: AsyncSession, user_id: uuid.UUID, email: str | None, nome: str
    ) -> AuthMeResponse:
        if not email:
            raise ValueError("E-mail não disponível na sessão")

        convite = await invite_service.get_pending_by_email(db, email)
        if not convite:
            raise ValueError("Nenhum convite pendente encontrado")

        await invite_service.accept_invite(db, convite, user_id, nome)
        await db.commit()
        return await self.get_me(db, user_id, email)

    async def submit_interest(
        self, email: str, nome: str | None, mensagem: str | None
    ) -> None:
        await send_interest_notification(email, nome, mensagem)


auth_service = AuthService()
