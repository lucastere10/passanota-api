"""remove api_keys table and api_key_id from invoices

Revision ID: 002
Revises: 001
Create Date: 2026-06-10

"""

from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_invoices_api_key_id"), table_name="invoices")
    op.drop_constraint("invoices_api_key_id_fkey", "invoices", type_="foreignkey")
    op.drop_column("invoices", "api_key_id")
    op.drop_table("api_keys")


def downgrade() -> None:
    import sqlalchemy as sa

    op.create_table(
        "api_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("invoices", sa.Column("api_key_id", sa.UUID(), nullable=True))
    op.create_foreign_key("invoices_api_key_id_fkey", "invoices", "api_keys", ["api_key_id"], ["id"])
    op.create_index(op.f("ix_invoices_api_key_id"), "invoices", ["api_key_id"], unique=False)
    op.alter_column("invoices", "api_key_id", nullable=False)
