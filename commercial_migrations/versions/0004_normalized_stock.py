"""Create normalized stock quantities and calculated availability views.

Revision ID: 0004_normalized_stock
Revises: 0003_versioned_pricing
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_normalized_stock"
down_revision = "0003_versioned_pricing"
branch_labels = None
depends_on = None

SCHEMA = "commercial"


def upgrade() -> None:
    op.create_table(
        "stock_quantity_types",
        sa.Column("code", sa.String(24), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("availability_effect", sa.SmallInteger, nullable=False),
        sa.CheckConstraint(
            "availability_effect IN (-1, 0, 1)",
            name="ck_stock_quantity_types_effect",
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "stock",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.warehouses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unit_code",
            sa.String(24),
            sa.ForeignKey(f"{SCHEMA}.units_of_measure.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "quantity_type_code",
            sa.String(24),
            sa.ForeignKey(f"{SCHEMA}.stock_quantity_types.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.data_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "import_batch_id",
            sa.String(36),
            sa.ForeignKey(f"{SCHEMA}.import_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity >= 0", name="ck_stock_nonnegative_quantity"),
        sa.CheckConstraint("valid_until >= observed_at", name="ck_stock_validity"),
        sa.UniqueConstraint(
            "product_id",
            "warehouse_id",
            "unit_code",
            "quantity_type_code",
            "observed_at",
            name="uq_stock_observation",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_stock_current_lookup",
        "stock",
        ["product_id", "warehouse_id", "quantity_type_code", "observed_at"],
        schema=SCHEMA,
    )
    op.execute(f"""
        CREATE VIEW {SCHEMA}.available_stock AS
        WITH latest AS (
            SELECT
                s.*,
                ROW_NUMBER() OVER (
                    PARTITION BY s.product_id, s.warehouse_id, s.unit_code,
                                 s.quantity_type_code
                    ORDER BY s.observed_at DESC, s.id DESC
                ) AS recency
            FROM {SCHEMA}.stock s
        ), current_quantities AS (
            SELECT
                product_id,
                warehouse_id,
                unit_code,
                MAX(observed_at) AS observed_at,
                MIN(valid_until) AS valid_until,
                SUM(quantity) FILTER (WHERE quantity_type_code = 'ON_HAND') AS on_hand,
                SUM(quantity) FILTER (WHERE quantity_type_code = 'COMMITTED') AS committed,
                SUM(quantity) FILTER (WHERE quantity_type_code = 'INCOMING') AS incoming,
                SUM(quantity) FILTER (WHERE quantity_type_code = 'TO_DISPATCH') AS to_dispatch
            FROM latest
            WHERE recency = 1
            GROUP BY product_id, warehouse_id, unit_code
        )
        SELECT
            product_id,
            warehouse_id,
            unit_code,
            COALESCE(on_hand, 0) AS on_hand,
            COALESCE(committed, 0) AS committed,
            COALESCE(incoming, 0) AS incoming,
            COALESCE(to_dispatch, 0) AS to_dispatch,
            GREATEST(
                COALESCE(on_hand, 0) - COALESCE(committed, 0) - COALESCE(to_dispatch, 0),
                0
            ) AS available,
            observed_at,
            valid_until
        FROM current_quantities
    """)
    op.execute(f"""
        CREATE VIEW {SCHEMA}.branch_stock AS
        SELECT
            s.product_id,
            w.branch_id,
            s.unit_code,
            SUM(s.available) AS available,
            MIN(s.observed_at) AS observed_at,
            MIN(s.valid_until) AS valid_until
        FROM {SCHEMA}.available_stock s
        JOIN {SCHEMA}.warehouses w ON w.id = s.warehouse_id
        GROUP BY s.product_id, w.branch_id, s.unit_code
    """)


def downgrade() -> None:
    op.execute(f"DROP VIEW IF EXISTS {SCHEMA}.branch_stock")
    op.execute(f"DROP VIEW IF EXISTS {SCHEMA}.available_stock")
    op.drop_index("ix_stock_current_lookup", table_name="stock", schema=SCHEMA)
    op.drop_table("stock", schema=SCHEMA)
    op.drop_table("stock_quantity_types", schema=SCHEMA)
