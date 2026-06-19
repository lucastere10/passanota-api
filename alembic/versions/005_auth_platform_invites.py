"""platform admins, convites, operador role

Revision ID: 005
Revises: 004
Create Date: 2026-06-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE funcionario_role ADD VALUE IF NOT EXISTS 'operador'")
    op.execute("UPDATE funcionarios SET role = 'gestor' WHERE role IN ('owner', 'admin')")

    op.create_table(
        "platform_admins",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_platform_admins_user_id"), "platform_admins", ["user_id"], unique=True)
    op.create_index(op.f("ix_platform_admins_email"), "platform_admins", ["email"], unique=True)

    op.create_table(
        "convites",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("empresa_id", sa.UUID(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("gestor", "operador", name="convite_role"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_user_id", sa.UUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_convites_email"), "convites", ["email"], unique=False)
    op.create_index(op.f("ix_convites_empresa_id"), "convites", ["empresa_id"], unique=False)
    op.create_index(op.f("ix_convites_token_hash"), "convites", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_convites_token_hash"), table_name="convites")
    op.drop_index(op.f("ix_convites_empresa_id"), table_name="convites")
    op.drop_index(op.f("ix_convites_email"), table_name="convites")
    op.drop_table("convites")
    op.execute("DROP TYPE IF EXISTS convite_role")

    op.drop_index(op.f("ix_platform_admins_email"), table_name="platform_admins")
    op.drop_index(op.f("ix_platform_admins_user_id"), table_name="platform_admins")
    op.drop_table("platform_admins")
