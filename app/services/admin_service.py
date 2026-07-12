import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Convite,
    ConviteRole,
    DevicePairingSession,
    Dispositivo,
    Empresa,
    Funcionario,
    FuncionarioRole,
    Invoice,
    PlatformAdmin,
)
from app.services.image.storage import invoice_photo_storage

DEFAULT_MONTHLY_INVOICE_LIMIT = 200


class EmpresaNotFoundError(Exception):
    pass


class EmpresaClearDataError(Exception):
    pass


def month_start_utc(reference: datetime | None = None) -> datetime:
    now = reference or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class AdminService:
    async def count_invoices_for_empresa(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        *,
        month_start: datetime | None = None,
    ) -> int:
        filters = [Invoice.empresa_id == empresa_id]
        if month_start is not None:
            filters.append(Invoice.created_at >= month_start)

        result = await db.execute(select(func.count()).select_from(Invoice).where(*filters))
        return int(result.scalar_one())

    async def get_empresa_usage(self, db: AsyncSession, empresa: Empresa) -> dict:
        start = month_start_utc()
        invoices_this_month = await self.count_invoices_for_empresa(
            db, empresa.id, month_start=start
        )
        invoices_total = await self.count_invoices_for_empresa(db, empresa.id)
        limit = empresa.monthly_invoice_limit
        is_unlimited = limit is None
        limit_reached = not is_unlimited and invoices_this_month >= limit
        usage_percentage = None
        if not is_unlimited and limit > 0:
            usage_percentage = round((invoices_this_month / limit) * 100, 1)

        return {
            "invoices_total": invoices_total,
            "invoices_this_month": invoices_this_month,
            "monthly_invoice_limit": limit,
            "is_unlimited": is_unlimited,
            "limit_reached": limit_reached,
            "usage_percentage": usage_percentage,
        }

    async def assert_empresa_can_capture(self, db: AsyncSession, empresa_id: uuid.UUID) -> Empresa:
        empresa = await db.get(Empresa, empresa_id)
        if not empresa:
            raise ValueError("Empresa não encontrada")
        if not empresa.is_active:
            raise ValueError("Empresa suspensa. Entre em contato com o administrador.")

        usage = await self.get_empresa_usage(db, empresa)
        if usage["limit_reached"]:
            limit = empresa.monthly_invoice_limit
            raise ValueError(
                f"Limite mensal de notas atingido ({limit}). Contate o administrador."
            )
        return empresa

    async def revoke_empresa_devices(self, db: AsyncSession, empresa_id: uuid.UUID) -> None:
        result = await db.execute(
            select(Dispositivo).where(
                Dispositivo.empresa_id == empresa_id,
                Dispositivo.is_active.is_(True),
            )
        )
        for device in result.scalars().all():
            device.is_active = False

    async def get_gestor_info(
        self, db: AsyncSession, empresa_id: uuid.UUID, now: datetime | None = None
    ) -> tuple[str | None, str | None, bool]:
        now = now or datetime.now(timezone.utc)

        convite_result = await db.execute(
            select(Convite)
            .where(Convite.empresa_id == empresa_id, Convite.role == ConviteRole.GESTOR)
            .order_by(Convite.created_at.desc())
            .limit(1)
        )
        convite = convite_result.scalar_one_or_none()
        gestor_email = convite.email if convite else None
        gestor_convite_pendente = (
            convite is not None
            and convite.accepted_at is None
            and convite.expires_at > now
        )

        func_result = await db.execute(
            select(Funcionario)
            .where(
                Funcionario.empresa_id == empresa_id,
                Funcionario.role == FuncionarioRole.GESTOR,
                Funcionario.is_active.is_(True),
            )
            .order_by(Funcionario.created_at.asc())
            .limit(1)
        )
        gestor = func_result.scalar_one_or_none()
        gestor_nome = gestor.nome if gestor else None

        return gestor_email, gestor_nome, gestor_convite_pendente

    async def count_funcionarios(self, db: AsyncSession, empresa_id: uuid.UUID) -> int:
        result = await db.execute(
            select(func.count())
            .select_from(Funcionario)
            .where(Funcionario.empresa_id == empresa_id, Funcionario.is_active.is_(True))
        )
        return int(result.scalar_one())

    async def count_active_devices(self, db: AsyncSession, empresa_id: uuid.UUID) -> int:
        result = await db.execute(
            select(func.count())
            .select_from(Dispositivo)
            .where(Dispositivo.empresa_id == empresa_id, Dispositivo.is_active.is_(True))
        )
        return int(result.scalar_one())

    async def build_empresa_list_item(
        self, db: AsyncSession, empresa: Empresa, now: datetime | None = None
    ) -> dict:
        now = now or datetime.now(timezone.utc)
        gestor_email, gestor_nome, gestor_convite_pendente = await self.get_gestor_info(
            db, empresa.id, now
        )
        usage = await self.get_empresa_usage(db, empresa)
        return {
            "id": empresa.id,
            "nome": empresa.nome,
            "cnpj": empresa.cnpj,
            "is_active": empresa.is_active,
            "created_at": empresa.created_at,
            "gestor_email": gestor_email,
            "gestor_nome": gestor_nome,
            "gestor_convite_pendente": gestor_convite_pendente,
            "invoices_total": usage["invoices_total"],
            "invoices_this_month": usage["invoices_this_month"],
            "monthly_invoice_limit": empresa.monthly_invoice_limit,
            "funcionarios_count": await self.count_funcionarios(db, empresa.id),
            "dispositivos_ativos_count": await self.count_active_devices(db, empresa.id),
        }

    async def get_platform_overview(self, db: AsyncSession) -> dict:
        now = datetime.now(timezone.utc)
        start = month_start_utc(now)

        empresas_total = await db.scalar(select(func.count()).select_from(Empresa)) or 0
        empresas_active = (
            await db.scalar(
                select(func.count()).select_from(Empresa).where(Empresa.is_active.is_(True))
            )
            or 0
        )
        invoices_total = await db.scalar(select(func.count()).select_from(Invoice)) or 0
        invoices_this_month = (
            await db.scalar(
                select(func.count()).select_from(Invoice).where(Invoice.created_at >= start)
            )
            or 0
        )
        devices_active = (
            await db.scalar(
                select(func.count())
                .select_from(Dispositivo)
                .where(Dispositivo.is_active.is_(True))
            )
            or 0
        )
        platform_admins = (
            await db.scalar(select(func.count()).select_from(PlatformAdmin)) or 0
        )
        gestores_active = (
            await db.scalar(
                select(func.count())
                .select_from(Funcionario)
                .where(
                    Funcionario.role == FuncionarioRole.GESTOR,
                    Funcionario.is_active.is_(True),
                )
            )
            or 0
        )
        operadores_active = (
            await db.scalar(
                select(func.count())
                .select_from(Funcionario)
                .where(
                    Funcionario.role == FuncionarioRole.OPERADOR,
                    Funcionario.is_active.is_(True),
                )
            )
            or 0
        )
        funcionarios_inactive = (
            await db.scalar(
                select(func.count())
                .select_from(Funcionario)
                .where(Funcionario.is_active.is_(False))
            )
            or 0
        )

        pending_gestor = (
            await db.scalar(
                select(func.count())
                .select_from(Convite)
                .where(
                    Convite.role == ConviteRole.GESTOR,
                    Convite.accepted_at.is_(None),
                    Convite.expires_at > now,
                )
            )
            or 0
        )
        pending_operador = (
            await db.scalar(
                select(func.count())
                .select_from(Convite)
                .where(
                    Convite.role == ConviteRole.OPERADOR,
                    Convite.accepted_at.is_(None),
                    Convite.expires_at > now,
                )
            )
            or 0
        )

        top_result = await db.execute(
            select(Empresa.nome, func.count(Invoice.id).label("count"))
            .join(Invoice, Invoice.empresa_id == Empresa.id)
            .where(Invoice.created_at >= start)
            .group_by(Empresa.id, Empresa.nome)
            .order_by(func.count(Invoice.id).desc())
            .limit(5)
        )
        top_empresas_month = [
            {"nome": row.nome, "invoices_this_month": int(row.count)}
            for row in top_result.all()
        ]

        return {
            "empresas_total": empresas_total,
            "empresas_active": empresas_active,
            "empresas_inactive": empresas_total - empresas_active,
            "invoices_total": invoices_total,
            "invoices_this_month": invoices_this_month,
            "devices_active": devices_active,
            "platform_admins": platform_admins,
            "gestores_active": gestores_active,
            "operadores_active": operadores_active,
            "funcionarios_inactive": funcionarios_inactive,
            "convites_pendentes_gestor": pending_gestor,
            "convites_pendentes_operador": pending_operador,
            "top_empresas_month": top_empresas_month,
        }

    async def clear_empresa_data(
        self,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        *,
        confirm_nome: str,
    ) -> dict[str, int]:
        empresa = await db.get(Empresa, empresa_id)
        if not empresa:
            raise EmpresaNotFoundError()

        if empresa.is_active:
            raise EmpresaClearDataError(
                "A empresa deve estar suspensa antes de limpar os dados."
            )

        if confirm_nome.strip() != empresa.nome.strip():
            raise EmpresaClearDataError(
                "O nome de confirmação não corresponde ao nome da empresa."
            )

        invoice_result = await db.execute(
            delete(Invoice).where(Invoice.empresa_id == empresa_id)
        )
        invoices_deleted = invoice_result.rowcount or 0

        dispositivos_result = await db.execute(
            delete(Dispositivo).where(Dispositivo.empresa_id == empresa_id)
        )
        dispositivos_deleted = dispositivos_result.rowcount or 0

        pairing_result = await db.execute(
            delete(DevicePairingSession).where(DevicePairingSession.empresa_id == empresa_id)
        )
        pairing_sessions_deleted = pairing_result.rowcount or 0

        convites_result = await db.execute(
            delete(Convite).where(Convite.empresa_id == empresa_id)
        )
        convites_deleted = convites_result.rowcount or 0

        funcionarios_result = await db.execute(
            delete(Funcionario).where(Funcionario.empresa_id == empresa_id)
        )
        funcionarios_deleted = funcionarios_result.rowcount or 0

        empresa.pin = None
        await db.commit()

        storage_objects_deleted = await invoice_photo_storage.clear_empresa_prefix(empresa_id)

        return {
            "invoices_deleted": invoices_deleted,
            "funcionarios_deleted": funcionarios_deleted,
            "convites_deleted": convites_deleted,
            "dispositivos_deleted": dispositivos_deleted,
            "pairing_sessions_deleted": pairing_sessions_deleted,
            "storage_objects_deleted": storage_objects_deleted,
        }


admin_service = AdminService()
