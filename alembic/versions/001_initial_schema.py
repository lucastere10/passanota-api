"""initial schema with pgvector

Revision ID: 001
Revises:
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "api_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "emitters",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=True),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("address", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_emitters_cnpj"), "emitters", ["cnpj"], unique=True)

    op.create_table(
        "invoices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("api_key_id", sa.UUID(), nullable=False),
        sa.Column("emitter_id", sa.UUID(), nullable=True),
        sa.Column("access_key", sa.String(length=44), nullable=False),
        sa.Column("uf", sa.String(length=2), nullable=False),
        sa.Column("model", sa.Integer(), nullable=False),
        sa.Column("series", sa.String(length=10), nullable=True),
        sa.Column("number", sa.String(length=20), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("discount_amount", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("qr_url", sa.Text(), nullable=False),
        sa.Column("protocol", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "parsed", "failed", name="invoice_status"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"]),
        sa.ForeignKeyConstraint(["emitter_id"], ["emitters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_key"),
    )
    op.create_index(op.f("ix_invoices_access_key"), "invoices", ["access_key"], unique=True)
    op.create_index(op.f("ix_invoices_api_key_id"), "invoices", ["api_key_id"], unique=False)
    op.create_index(op.f("ix_invoices_emitter_id"), "invoices", ["emitter_id"], unique=False)
    op.create_index(op.f("ix_invoices_issued_at"), "invoices", ["issued_at"], unique=False)
    op.create_index(op.f("ix_invoices_status"), "invoices", ["status"], unique=False)
    op.create_index(op.f("ix_invoices_uf"), "invoices", ["uf"], unique=False)

    op.create_table(
        "invoice_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(length=50), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("ncm", sa.String(length=20), nullable=True),
        sa.Column("ean", sa.String(length=20), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column("unit", sa.String(length=10), nullable=True),
        sa.Column("unit_price", sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column("total_price", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invoice_items_category_id"), "invoice_items", ["category_id"], unique=False)
    op.create_index(op.f("ix_invoice_items_invoice_id"), "invoice_items", ["invoice_id"], unique=False)
    op.create_index(
        "ix_invoice_items_embedding_hnsw",
        "invoice_items",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    categories = [
        ("Alimentação", "alimentacao"),
        ("Bebidas", "bebidas"),
        ("Higiene", "higiene"),
        ("Limpeza", "limpeza"),
        ("Vestuário", "vestuario"),
        ("Outros", "outros"),
    ]
    for name, slug in categories:
        op.execute(
            sa.text(
                "INSERT INTO categories (id, name, slug) VALUES (gen_random_uuid(), :name, :slug)"
            ).bindparams(name=name, slug=slug)
        )


def downgrade() -> None:
    op.drop_index("ix_invoice_items_embedding_hnsw", table_name="invoice_items")
    op.drop_index(op.f("ix_invoice_items_invoice_id"), table_name="invoice_items")
    op.drop_index(op.f("ix_invoice_items_category_id"), table_name="invoice_items")
    op.drop_table("invoice_items")
    op.drop_index(op.f("ix_invoices_uf"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_status"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_issued_at"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_emitter_id"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_api_key_id"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_access_key"), table_name="invoices")
    op.drop_table("invoices")
    op.drop_index(op.f("ix_emitters_cnpj"), table_name="emitters")
    op.drop_table("emitters")
    op.drop_table("categories")
    op.drop_table("api_keys")
    op.execute("DROP TYPE IF EXISTS invoice_status")
    op.execute("DROP EXTENSION IF EXISTS vector")
