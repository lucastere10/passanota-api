"""openai embeddings vector(512)

Revision ID: 011
Revises: 010
Create Date: 2026-08-28

MiniLM (384-d) vectors are incompatible with text-embedding-3-small (512-d).
Existing embeddings are wiped; reembed.py backfills after deploy.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_invoice_items_embedding_hnsw", table_name="invoice_items")
    op.execute("ALTER TABLE invoice_items ALTER COLUMN embedding TYPE vector(512) USING NULL")
    op.execute("ALTER TABLE categories ALTER COLUMN embedding TYPE vector(512) USING NULL")
    op.create_index(
        "ix_invoice_items_embedding_hnsw",
        "invoice_items",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_invoice_items_embedding_hnsw", table_name="invoice_items")
    op.execute("ALTER TABLE invoice_items ALTER COLUMN embedding TYPE vector(384) USING NULL")
    op.execute("ALTER TABLE categories ALTER COLUMN embedding TYPE vector(384) USING NULL")
    op.create_index(
        "ix_invoice_items_embedding_hnsw",
        "invoice_items",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
