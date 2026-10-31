"""Add full-text search and pgvector storage without an ANN index.

Revision ID: 0005_vector_search_foundation
Revises: 0004_normalized_stock
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "0005_vector_search_foundation"
down_revision = "0004_normalized_stock"
branch_labels = None
depends_on = None

SCHEMA = "commercial"


class Vector(sa.types.UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_kw: object) -> str:
        return "vector"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "embedding_models",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("dimension", sa.Integer),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.CheckConstraint("dimension IS NULL OR dimension > 0", name="ck_embedding_models_dim"),
        sa.UniqueConstraint("code", name="uq_embedding_models_code"),
        schema=SCHEMA,
    )
    op.create_table(
        "product_search_documents",
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.products.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "search_vector",
            TSVECTOR,
            sa.Computed("to_tsvector('spanish', content)", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_product_search_documents_fts",
        "product_search_documents",
        ["search_vector"],
        postgresql_using="gin",
        schema=SCHEMA,
    )
    op.create_table(
        "product_embeddings",
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.products.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "embedding_model_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.embedding_models.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "embedded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("vector_dims(embedding) > 0", name="ck_product_embeddings_dim"),
        schema=SCHEMA,
    )
    op.execute(f"""
        CREATE VIEW {SCHEMA}.catalog_products AS
        SELECT
            p.id,
            p.business_id,
            p.sku,
            p.name,
            pu.unit_code,
            cp.amount AS price,
            cp.currency_code,
            cp.includes_tax,
            psd.content AS search_content
        FROM {SCHEMA}.products p
        JOIN {SCHEMA}.product_units pu ON pu.product_id = p.id AND pu.is_primary
        JOIN {SCHEMA}.current_product_prices cp
          ON cp.product_id = p.id AND cp.warehouse_id IS NULL
        JOIN {SCHEMA}.product_search_documents psd ON psd.product_id = p.id
        WHERE p.active
    """)


def downgrade() -> None:
    op.execute(f"DROP VIEW IF EXISTS {SCHEMA}.catalog_products")
    op.drop_table("product_embeddings", schema=SCHEMA)
    op.drop_index(
        "ix_product_search_documents_fts",
        table_name="product_search_documents",
        schema=SCHEMA,
    )
    op.drop_table("product_search_documents", schema=SCHEMA)
    op.drop_table("embedding_models", schema=SCHEMA)
