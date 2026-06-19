"""dispositivos mobile auth

Revision ID: 006
Revises: 005
Create Date: 2026-06-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "empresas",
        "pin",
        existing_type=sa.String(length=20),
        type_=sa.String(length=128),
        existing_nullable=True,
    )

    op.create_table(
        "device_pairing_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("empresa_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pin_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_device_pairing_sessions_empresa_id",
        "device_pairing_sessions",
        ["empresa_id"],
        unique=False,
    )

    op.create_table(
        "dispositivos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("empresa_id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paired_by_user_id", sa.UUID(), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_dispositivos_empresa_id", "dispositivos", ["empresa_id"], unique=False)

    op.add_column("invoices", sa.Column("device_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_invoices_device_id",
        "invoices",
        "dispositivos",
        ["device_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_invoices_device_id", "invoices", ["device_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_invoices_device_id", table_name="invoices")
    op.drop_constraint("fk_invoices_device_id", "invoices", type_="foreignkey")
    op.drop_column("invoices", "device_id")

    op.drop_index("ix_dispositivos_empresa_id", table_name="dispositivos")
    op.drop_table("dispositivos")

    op.drop_index("ix_device_pairing_sessions_empresa_id", table_name="device_pairing_sessions")
    op.drop_table("device_pairing_sessions")

    op.alter_column(
        "empresas",
        "pin",
        existing_type=sa.String(length=128),
        type_=sa.String(length=20),
        existing_nullable=True,
    )
