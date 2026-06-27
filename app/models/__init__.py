import enum
import uuid
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"


class InvoiceSource(str, enum.Enum):
    PHOTO_AI = "photo_ai"


class FuncionarioRole(str, enum.Enum):
    GESTOR = "gestor"
    OPERADOR = "operador"


class ConviteRole(str, enum.Enum):
    GESTOR = "gestor"
    OPERADOR = "operador"


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    cnpj: Mapped[str | None] = mapped_column(String(14), unique=True, nullable=True, index=True)
    pin: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    funcionarios: Mapped[list["Funcionario"]] = relationship(back_populates="empresa")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="empresa")
    convites: Mapped[list["Convite"]] = relationship(back_populates="empresa")
    dispositivos: Mapped[list["Dispositivo"]] = relationship(back_populates="empresa")
    device_pairing_sessions: Mapped[list["DevicePairingSession"]] = relationship(
        back_populates="empresa"
    )


class PlatformAdmin(Base):
    __tablename__ = "platform_admins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    nome: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Convite(Base):
    __tablename__ = "convites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[ConviteRole] = mapped_column(
        Enum(
            ConviteRole,
            name="convite_role",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    empresa: Mapped["Empresa"] = relationship(back_populates="convites")


class Funcionario(Base):
    __tablename__ = "funcionarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    role: Mapped[FuncionarioRole] = mapped_column(
        Enum(
            FuncionarioRole,
            name="funcionario_role",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    nome: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    empresa: Mapped["Empresa"] = relationship(back_populates="funcionarios")

    __table_args__ = (Index("uq_funcionarios_empresa_user", "empresa_id", "user_id", unique=True),)


class DevicePairingSession(Base):
    __tablename__ = "device_pairing_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pin_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    empresa: Mapped["Empresa"] = relationship(back_populates="device_pairing_sessions")


class Dispositivo(Base):
    __tablename__ = "dispositivos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paired_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    empresa: Mapped["Empresa"] = relationship(back_populates="dispositivos")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="dispositivo")


class Emitter(Base):
    __tablename__ = "emitters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cnpj: Mapped[str | None] = mapped_column(String(14), nullable=True, index=True)
    trade_name: Mapped[str | None] = mapped_column(String(255))
    legal_name: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    uf: Mapped[str | None] = mapped_column(String(2))
    address: Mapped[dict | None] = mapped_column(JSONB)

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="emitter")

    __table_args__ = (
        Index(
            "uq_emitters_cnpj_not_null",
            "cnpj",
            unique=True,
            postgresql_where="cnpj IS NOT NULL",
        ),
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    embedding = mapped_column(Vector(384), nullable=True)

    items: Mapped[list["InvoiceItem"]] = relationship(back_populates="category")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=True, index=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dispositivos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    emitter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emitters.id"), nullable=True, index=True
    )
    access_key: Mapped[str | None] = mapped_column(String(44), nullable=True, index=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    model: Mapped[int] = mapped_column(Integer, default=65, nullable=False)
    series: Mapped[str | None] = mapped_column(String(10))
    number: Mapped[str | None] = mapped_column(String(20))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    qr_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(50))
    source_type: Mapped[InvoiceSource] = mapped_column(
        Enum(
            InvoiceSource,
            name="invoice_source",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=InvoiceSource.PHOTO_AI,
        nullable=False,
    )
    photo_original_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_processed_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(
            InvoiceStatus,
            name="invoice_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=InvoiceStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    empresa: Mapped["Empresa | None"] = relationship(back_populates="invoices")
    dispositivo: Mapped["Dispositivo | None"] = relationship(back_populates="invoices")
    emitter: Mapped["Emitter | None"] = relationship(back_populates="invoices")
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "uq_invoices_access_key_not_null",
            "access_key",
            unique=True,
            postgresql_where="access_key IS NOT NULL",
        ),
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_code: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    ncm: Mapped[str | None] = mapped_column(String(20))
    ean: Mapped[str | None] = mapped_column(String(20))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    unit: Mapped[str | None] = mapped_column(String(10))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    embedding = mapped_column(Vector(384), nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="items")
    category: Mapped["Category | None"] = relationship(back_populates="items")

    __table_args__ = (
        Index(
            "ix_invoice_items_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
