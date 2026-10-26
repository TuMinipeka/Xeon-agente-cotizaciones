"""Persist advisor events and attention state.

Revision ID: 0002_advisor_inbox
Revises: 0001_operational_state
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_advisor_inbox"
down_revision = "0001_operational_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "advisor_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("conversation_key", sa.String(256)),
        sa.Column("quote_id", sa.String(36)),
        sa.Column("resolved_by", sa.String(64)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.String(300)),
        sa.Column("client_notified", sa.Boolean()),
    )
    op.create_index(
        "ix_advisor_events_tenant_status_created",
        "advisor_events",
        ["tenant_id", "status", "created_at"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_advisor_pending ON advisor_events "
        "(tenant_id, kind, coalesce(conversation_key, ''), coalesce(quote_id, '')) "
        "WHERE status = 'PENDIENTE'"
    )


def downgrade() -> None:
    op.drop_index("uq_advisor_pending", table_name="advisor_events")
    op.drop_index("ix_advisor_events_tenant_status_created", table_name="advisor_events")
    op.drop_table("advisor_events")
