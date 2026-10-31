"""Create the normalized product, taxonomy, brand, color, unit and measurement model.

Revision ID: 0002_normalized_catalog
Revises: 0001_commercial_core
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_normalized_catalog"
down_revision = "0001_commercial_core"
branch_labels = None
depends_on = None

SCHEMA = "commercial"


def _catalog_dimension(table: str) -> None:
    op.create_table(
        table,
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "business_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.UniqueConstraint("business_id", "source_code", name=f"uq_{table}_business_code"),
        schema=SCHEMA,
    )


def _product_dimension_link(table: str, target: str) -> None:
    singular = {
        "brands": "brand",
        "colors": "color",
        "lines": "line",
        "categories": "category",
        "sublines": "subline",
    }[target]
    op.create_table(
        table,
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.products.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            f"{singular}_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.{target}.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        schema=SCHEMA,
    )


def upgrade() -> None:
    op.create_table(
        "product_types",
        sa.Column("code", sa.String(24), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("manages_stock", sa.Boolean, nullable=False),
        schema=SCHEMA,
    )
    op.create_table(
        "units_of_measure",
        sa.Column("code", sa.String(24), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("dimension", sa.String(24), nullable=False),
        sa.Column("allows_fraction", sa.Boolean, nullable=False),
        sa.CheckConstraint(
            "dimension IN ('COUNT', 'LENGTH', 'AREA', 'VOLUME', 'MASS', 'PACKAGE')",
            name="ck_units_of_measure_dimension",
        ),
        schema=SCHEMA,
    )
    for table in ("brands", "colors", "lines", "categories", "sublines"):
        _catalog_dimension(table)

    op.create_table(
        "line_categories",
        sa.Column(
            "line_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.lines.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "category_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.categories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "category_sublines",
        sa.Column(
            "category_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.categories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "subline_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.sublines.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "business_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_type_code",
            sa.String(24),
            sa.ForeignKey(f"{SCHEMA}.product_types.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "import_batch_id",
            sa.String(36),
            sa.ForeignKey(f"{SCHEMA}.import_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sku", sa.String(80), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("registered_on", sa.Date),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("specs", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("description_context", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("business_id", "sku", name="uq_products_business_sku"),
        schema=SCHEMA,
    )
    op.create_index("ix_products_name", "products", ["name"], schema=SCHEMA)
    op.create_index(
        "ix_products_specs_gin",
        "products",
        ["specs"],
        unique=False,
        postgresql_using="gin",
        schema=SCHEMA,
    )

    _product_dimension_link("product_brands", "brands")
    _product_dimension_link("product_colors", "colors")
    _product_dimension_link("product_lines", "lines")
    _product_dimension_link("product_categories", "categories")
    _product_dimension_link("product_sublines", "sublines")

    op.create_table(
        "product_units",
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.products.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "unit_code",
            sa.String(24),
            sa.ForeignKey(f"{SCHEMA}.units_of_measure.code", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("is_primary", sa.Boolean, nullable=False),
        sa.Column("conversion_to_primary", sa.Numeric(18, 6), nullable=False),
        sa.Column("assignment_method", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "conversion_to_primary > 0",
            name="ck_product_units_positive_conversion",
        ),
        sa.CheckConstraint(
            "assignment_method IN ('SOURCE', 'DESCRIPTION_RULE', 'DEFAULT')",
            name="ck_product_units_assignment_method",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_product_units_primary",
        "product_units",
        ["product_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
        schema=SCHEMA,
    )
    op.create_table(
        "product_measurements",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "product_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.SmallInteger, nullable=False),
        sa.Column("measurement_kind", sa.String(24), nullable=False),
        sa.Column("value", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "unit_code",
            sa.String(24),
            sa.ForeignKey(f"{SCHEMA}.units_of_measure.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("raw_text", sa.String(80), nullable=False),
        sa.CheckConstraint("ordinal > 0", name="ck_product_measurements_ordinal"),
        sa.CheckConstraint("value > 0", name="ck_product_measurements_value"),
        sa.CheckConstraint(
            "measurement_kind IN ('UNSPECIFIED', 'LENGTH', 'WIDTH', 'HEIGHT', "
            "'DIAMETER', 'AREA', 'VOLUME', 'MASS')",
            name="ck_product_measurements_kind",
        ),
        sa.UniqueConstraint("product_id", "ordinal", name="uq_product_measurements_ordinal"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("product_measurements", schema=SCHEMA)
    op.drop_index("uq_product_units_primary", table_name="product_units", schema=SCHEMA)
    op.drop_table("product_units", schema=SCHEMA)
    for table in (
        "product_sublines",
        "product_categories",
        "product_lines",
        "product_colors",
        "product_brands",
    ):
        op.drop_table(table, schema=SCHEMA)
    op.drop_index("ix_products_specs_gin", table_name="products", schema=SCHEMA)
    op.drop_index("ix_products_name", table_name="products", schema=SCHEMA)
    op.drop_table("products", schema=SCHEMA)
    op.drop_table("category_sublines", schema=SCHEMA)
    op.drop_table("line_categories", schema=SCHEMA)
    for table in ("sublines", "categories", "lines", "colors", "brands"):
        op.drop_table(table, schema=SCHEMA)
    op.drop_table("units_of_measure", schema=SCHEMA)
    op.drop_table("product_types", schema=SCHEMA)
