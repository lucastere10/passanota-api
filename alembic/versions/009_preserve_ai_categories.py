"""preserve ai-assigned categories in normalize_invoice_items

Revision ID: 009
Revises: 008
Create Date: 2026-06-28

"""

from typing import Sequence, Union

from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
            WHERE ii.invoice_id = p_invoice_id
              AND ii.category_id IS NULL;

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
        $$;
        """
    )


def downgrade() -> None:
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
        $$;
        """
    )
