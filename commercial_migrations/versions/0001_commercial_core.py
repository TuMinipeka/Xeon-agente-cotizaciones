"""Create the isolated commercial core and import audit tables.

Revision ID: 0001_commercial_core
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_commercial_core"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "commercial"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.create_table(
        "businesses",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("legal_name", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("code", name="uq_businesses_code"),
        schema=SCHEMA,
    )
    op.create_table(
        "branches",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "business_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("business_id", "code", name="uq_branches_business_code"),
        schema=SCHEMA,
    )
    op.create_table(
        "warehouses",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "branch_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.branches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("branch_id", "code", name="uq_warehouses_branch_code"),
        schema=SCHEMA,
    )
    op.create_table(
        "data_sources",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_sha256", sa.String(64)),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint(
            "source_kind IN ('XLSX', 'SEED', 'API', 'ERP', 'MANUAL')",
            name="ck_data_sources_kind",
        ),
        sa.UniqueConstraint("code", name="uq_data_sources_code"),
        schema=SCHEMA,
    )
    op.create_table(
        "import_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "source_id",
            sa.BigInteger,
            sa.ForeignKey(f"{SCHEMA}.data_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source_rows", sa.Integer, nullable=False),
        sa.Column("accepted_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rejected_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_import_batches_status",
        ),
        sa.CheckConstraint(
            "source_rows >= 0 AND accepted_rows >= 0 AND rejected_rows >= 0",
            name="ck_import_batches_counts",
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(36),
            sa.ForeignKey(f"{SCHEMA}.import_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sku", sa.String(80)),
        sa.Column("issue_code", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("details", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "severity IN ('INFO', 'WARNING', 'ERROR')",
            name="ck_data_quality_issues_severity",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_data_quality_issues_batch_code",
        "data_quality_issues",
        ["batch_id", "issue_code"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_quality_issues_batch_code",
        table_name="data_quality_issues",
        schema=SCHEMA,
    )
    op.drop_table("data_quality_issues", schema=SCHEMA)
    op.drop_table("import_batches", schema=SCHEMA)
    op.drop_table("data_sources", schema=SCHEMA)
    op.drop_table("warehouses", schema=SCHEMA)
    op.drop_table("branches", schema=SCHEMA)
    op.drop_table("businesses", schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
