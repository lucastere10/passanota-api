"""empresas, funcionarios and invoice tenancy

Revision ID: 003
Revises: 002
Create Date: 2026-06-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "empresas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("cnpj", sa.String(length=14), nullable=True),
        sa.Column("pin", sa.String(length=20), nullable=True),
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
    op.create_index(op.f("ix_empresas_cnpj"), "empresas", ["cnpj"], unique=True)

    op.create_table(
        "funcionarios",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("empresa_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "admin", "gestor", name="funcionario_role"),
            nullable=False,
        ),
        sa.Column("nome", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    )
    op.create_index(op.f("ix_funcionarios_empresa_id"), "funcionarios", ["empresa_id"], unique=False)
    op.create_index(op.f("ix_funcionarios_user_id"), "funcionarios", ["user_id"], unique=False)
    op.create_index(
        "uq_funcionarios_empresa_user",
        "funcionarios",
        ["empresa_id", "user_id"],
        unique=True,
    )

    op.add_column("invoices", sa.Column("empresa_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_invoices_empresa_id"), "invoices", ["empresa_id"], unique=False)
    op.create_foreign_key(
        "fk_invoices_empresa_id_empresas",
        "invoices",
        "empresas",
        ["empresa_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_invoices_empresa_id_empresas", "invoices", type_="foreignkey")
    op.drop_index(op.f("ix_invoices_empresa_id"), table_name="invoices")
    op.drop_column("invoices", "empresa_id")

    op.drop_index("uq_funcionarios_empresa_user", table_name="funcionarios")
    op.drop_index(op.f("ix_funcionarios_user_id"), table_name="funcionarios")
    op.drop_index(op.f("ix_funcionarios_empresa_id"), table_name="funcionarios")
    op.drop_table("funcionarios")
    op.execute("DROP TYPE IF EXISTS funcionario_role")

    op.drop_index(op.f("ix_empresas_cnpj"), table_name="empresas")
    op.drop_table("empresas")
