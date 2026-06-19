"""photo ai invoices schema

Revision ID: 004
Revises: 003
Create Date: 2026-06-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "alimentacao": [
        "arroz", "feijao", "pao", "leite", "queijo", "carne", "frango",
        "macarrao", "farinha", "acucar", "sal", "oleo", "manteiga", "iogurte",
    ],
    "bebidas": [
        "coca", "cola", "pepsi", "cerveja", "agua", "suco", "refrigerante",
        "guarana", "sprite", "fanta", "energetico", "vinho", "whisky",
    ],
    "higiene": [
        "sabonete", "shampoo", "condicionador", "pasta", "escova", "desodorante",
        "papel higienico", "absorvente", "fralda", "creme",
    ],
    "limpeza": [
        "detergente", "sabao", "amaciante", "desinfetante", "agua sanitaria",
        "esponja", "pano", "limpa", "alvejante", "multiuso",
    ],
    "vestuario": [
        "camisa", "calca", "bermuda", "tenis", "sapato", "meia", "cueca",
        "sutia", "vestido", "jaqueta", "blusa",
    ],
    "outros": [],
}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    op.execute("CREATE TYPE invoice_source AS ENUM ('photo_ai')")

    # invoices: 001 criou índice único + constraint com nomes distintos
    op.execute("ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_access_key_key")
    op.execute("DROP INDEX IF EXISTS ix_invoices_access_key")

    op.alter_column("invoices", "access_key", existing_type=sa.String(44), nullable=True)
    op.alter_column("invoices", "qr_url", existing_type=sa.Text(), nullable=True)
    op.alter_column("invoices", "uf", existing_type=sa.String(2), nullable=True)

    op.add_column(
        "invoices",
        sa.Column(
            "source_type",
            sa.Enum("photo_ai", name="invoice_source", create_type=False),
            nullable=False,
            server_default="photo_ai",
        ),
    )
    op.add_column("invoices", sa.Column("photo_original_path", sa.Text(), nullable=True))
    op.add_column("invoices", sa.Column("photo_processed_path", sa.Text(), nullable=True))
    op.add_column("invoices", sa.Column("ai_raw_response", sa.dialects.postgresql.JSONB(), nullable=True))
    op.add_column("invoices", sa.Column("ai_model", sa.String(100), nullable=True))
    op.add_column(
        "invoices",
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "uq_invoices_access_key_not_null",
        "invoices",
        ["access_key"],
        unique=True,
        postgresql_where=sa.text("access_key IS NOT NULL"),
    )
    op.create_index(op.f("ix_invoices_access_key"), "invoices", ["access_key"], unique=False)

    # emitters: 001 criou apenas índice único ix_emitters_cnpj (sem constraint nomeada)
    op.execute("DROP INDEX IF EXISTS ix_emitters_cnpj")
    op.alter_column("emitters", "cnpj", existing_type=sa.String(14), nullable=True)
    op.create_index(
        "uq_emitters_cnpj_not_null",
        "emitters",
        ["cnpj"],
        unique=True,
        postgresql_where=sa.text("cnpj IS NOT NULL"),
    )
    op.create_index(op.f("ix_emitters_cnpj"), "emitters", ["cnpj"], unique=False)

    op.add_column(
        "categories",
        sa.Column("keywords", sa.ARRAY(sa.Text()), nullable=True),
    )
    op.add_column("categories", sa.Column("embedding", Vector(384), nullable=True))

    for slug, keywords in CATEGORY_KEYWORDS.items():
        if keywords:
            op.execute(
                sa.text(
                    "UPDATE categories SET keywords = :keywords WHERE slug = :slug"
                ).bindparams(keywords=keywords, slug=slug)
            )

    _create_assign_category_id_function()
    _create_normalize_invoice_items_function()


def _create_assign_category_id_function() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION assign_category_id(
            p_description text,
            p_embedding vector DEFAULT NULL
        )
        RETURNS uuid
        LANGUAGE plpgsql
        STABLE
        AS $$
        DECLARE
            v_desc text;
            v_category_id uuid;
        BEGIN
            v_desc := upper(trim(coalesce(p_description, '')));

            IF v_desc = '' THEN
                SELECT id INTO v_category_id FROM categories WHERE slug = 'outros' LIMIT 1;
                RETURN v_category_id;
            END IF;

            SELECT c.id INTO v_category_id
            FROM categories c
            WHERE c.keywords IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM unnest(c.keywords) AS kw
                  WHERE v_desc ILIKE '%' || kw || '%'
              )
            ORDER BY length(
                (SELECT kw FROM unnest(c.keywords) AS kw
                 WHERE v_desc ILIKE '%' || kw || '%'
                 ORDER BY length(kw) DESC LIMIT 1)
            ) DESC
            LIMIT 1;

            IF v_category_id IS NOT NULL THEN
                RETURN v_category_id;
            END IF;

            IF p_embedding IS NOT NULL THEN
                SELECT c.id INTO v_category_id
                FROM categories c
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> p_embedding
                LIMIT 1;

                IF v_category_id IS NOT NULL THEN
                    RETURN v_category_id;
                END IF;
            END IF;

            SELECT id INTO v_category_id FROM categories WHERE slug = 'outros' LIMIT 1;
            RETURN v_category_id;
        END;
        $$
        """
    )


def _create_normalize_invoice_items_function() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION normalize_invoice_items(p_invoice_id uuid)
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_total numeric(15, 2);
        BEGIN
            UPDATE invoice_items
            SET description = upper(trim(description))
            WHERE invoice_id = p_invoice_id;

            UPDATE invoice_items ii
            SET category_id = assign_category_id(ii.description, ii.embedding)
            WHERE ii.invoice_id = p_invoice_id;

            SELECT coalesce(sum(total_price), 0) INTO v_total
            FROM invoice_items
            WHERE invoice_id = p_invoice_id;

            UPDATE invoices
            SET total_amount = CASE
                WHEN total_amount IS NULL OR total_amount = 0 THEN v_total
                ELSE total_amount
            END,
            updated_at = now()
            WHERE id = p_invoice_id;
        END;
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS normalize_invoice_items(uuid)")
    op.execute("DROP FUNCTION IF EXISTS assign_category_id(text, vector)")

    op.drop_column("categories", "embedding")
    op.drop_column("categories", "keywords")

    op.drop_index(op.f("ix_emitters_cnpj"), table_name="emitters")
    op.drop_index("uq_emitters_cnpj_not_null", table_name="emitters")
    op.create_index(op.f("ix_emitters_cnpj"), "emitters", ["cnpj"], unique=True)
    op.alter_column("emitters", "cnpj", existing_type=sa.String(14), nullable=False)

    op.drop_column("invoices", "extracted_at")
    op.drop_column("invoices", "ai_model")
    op.drop_column("invoices", "ai_raw_response")
    op.drop_column("invoices", "photo_processed_path")
    op.drop_column("invoices", "photo_original_path")
    op.drop_column("invoices", "source_type")

    op.alter_column("invoices", "uf", existing_type=sa.String(2), nullable=False)
    op.alter_column("invoices", "qr_url", existing_type=sa.Text(), nullable=False)
    op.alter_column("invoices", "access_key", existing_type=sa.String(44), nullable=False)

    op.drop_index(op.f("ix_invoices_access_key"), table_name="invoices")
    op.drop_index("uq_invoices_access_key_not_null", table_name="invoices")
    op.create_index(op.f("ix_invoices_access_key"), "invoices", ["access_key"], unique=True)
    op.create_unique_constraint("invoices_access_key_key", "invoices", ["access_key"])

    op.execute("DROP TYPE IF EXISTS invoice_source")
