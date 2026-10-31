"""Create effective-dated taxes and price lists without internal costs or margins.

Revision ID: 0003_versioned_pricing
Revises: 0002_normalized_catalog
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_versioned_pricing"
down_revision = "0002_normalized_catalog"
branch_labels = None
depends_on = None

SCHEMA = "commercial"


def upgrade() -> None:
    op.create_table(
        "currencies",
        sa.Column("code", sa.String(3), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("decimal_places", sa.SmallInteger, nullable=False),
        sa.CheckConstraint("decimal_places BETWEEN 0 AND 6", name="ck_currencies_decimals"),
        schema=SCHEMA,
    )
    op.create_table(
        "tax_classes",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "business_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("applies_to_sales", sa.Boolean, nullable=False),
        sa.Column("applies_to_purchases", sa.Boolean, nullable=False),
        sa.UniqueConstraint("business_id", "source_code", name="uq_tax_classes_business_code"),
        schema=SCHEMA,
    )
    op.create_table(
        "tax_rates",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "tax_class_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.tax_classes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rate", sa.Numeric(7, 4), nullable=False),
        sa.Column("valid_from", sa.Date, nullable=False),
        sa.Column("valid_to", sa.Date),
        sa.CheckConstraint("rate BETWEEN 0 AND 100", name="ck_tax_rates_range"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_tax_rates_validity",
        ),
        sa.UniqueConstraint("tax_class_id", "valid_from", name="uq_tax_rates_class_from"),
        schema=SCHEMA,
    )
    op.create_table(
        "product_tax_assignments",
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.products.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tax_class_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.tax_classes.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("valid_from", sa.Date, primary_key=True),
        sa.Column("valid_to", sa.Date),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_product_tax_assignments_validity",
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "price_lists",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "business_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("priority", sa.SmallInteger, nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("includes_tax", sa.Boolean, nullable=False),
        sa.CheckConstraint("priority > 0", name="ck_price_lists_priority"),
        sa.UniqueConstraint("business_id", "code", name="uq_price_lists_business_code"),
        sa.UniqueConstraint("business_id", "priority", name="uq_price_lists_business_priority"),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_price_lists_default",
        "price_lists",
        ["business_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
        schema=SCHEMA,
    )
    op.create_table(
        "product_prices",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "price_list_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.price_lists.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.warehouses.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "currency_code",
            sa.String(3),
            sa.ForeignKey(f"{SCHEMA}.currencies.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("valid_from", sa.Date, nullable=False),
        sa.Column("valid_to", sa.Date),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "import_batch_id",
            sa.String(36),
            sa.ForeignKey(f"{SCHEMA}.import_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("amount > 0", name="ck_product_prices_positive"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="ck_product_prices_validity",
        ),
        sa.UniqueConstraint(
            "product_id",
            "price_list_id",
            "warehouse_id",
            "valid_from",
            name="uq_product_prices_effective",
            postgresql_nulls_not_distinct=True,
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_product_prices_lookup",
        "product_prices",
        ["product_id", "price_list_id", "active", "valid_from"],
        schema=SCHEMA,
    )
    op.execute(f"""
        CREATE VIEW {SCHEMA}.current_product_prices AS
        WITH ranked AS (
            SELECT
                pp.product_id,
                pp.warehouse_id,
                pp.amount,
                pp.currency_code,
                pp.valid_from,
                pp.valid_to,
                pl.code AS price_list_code,
                pl.includes_tax,
                ROW_NUMBER() OVER (
                    PARTITION BY pp.product_id, pp.warehouse_id
                    ORDER BY pl.is_default DESC, pl.priority, pp.valid_from DESC, pp.id DESC
                ) AS preference
            FROM {SCHEMA}.product_prices pp
            JOIN {SCHEMA}.price_lists pl ON pl.id = pp.price_list_id
            WHERE pp.active
              AND pp.valid_from <= CURRENT_DATE
              AND (pp.valid_to IS NULL OR pp.valid_to >= CURRENT_DATE)
        )
        SELECT product_id, warehouse_id, amount, currency_code, valid_from, valid_to,
               price_list_code, includes_tax
        FROM ranked
        WHERE preference = 1
    """)


def downgrade() -> None:
    op.execute(f"DROP VIEW IF EXISTS {SCHEMA}.current_product_prices")
    op.drop_index("ix_product_prices_lookup", table_name="product_prices", schema=SCHEMA)
    op.drop_table("product_prices", schema=SCHEMA)
    op.drop_index("uq_price_lists_default", table_name="price_lists", schema=SCHEMA)
    op.drop_table("price_lists", schema=SCHEMA)
    op.drop_table("product_tax_assignments", schema=SCHEMA)
    op.drop_table("tax_rates", schema=SCHEMA)
    op.drop_table("tax_classes", schema=SCHEMA)
    op.drop_table("currencies", schema=SCHEMA)
