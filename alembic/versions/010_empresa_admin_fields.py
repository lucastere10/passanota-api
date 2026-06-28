"""empresa admin fields is_active and monthly invoice limit

Revision ID: 010
Revises: 009
Create Date: 2026-06-28

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_MONTHLY_INVOICE_LIMIT = 200


def upgrade() -> None:
    op.add_column(
        "empresas",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "empresas",
        sa.Column("monthly_invoice_limit", sa.Integer(), nullable=True),
    )
    # Existing empresas stay unlimited until admin sets a limit.
    op.alter_column("empresas", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("empresas", "monthly_invoice_limit")
    op.drop_column("empresas", "is_active")
