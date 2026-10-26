"""Durable Kapso inbox and transactional outgoing messages.

Revision ID: 0003_kapso_outbox
Revises: 0002_advisor_inbox
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_kapso_outbox"
down_revision = "0002_advisor_inbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inbound_deliveries",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("instance", sa.String(128), primary_key=True),
        sa.Column("message_id", sa.String(256), primary_key=True),
        sa.Column("sender_jid", sa.String(128), nullable=False),
        sa.Column("sender_number", sa.String(64), nullable=False),
        sa.Column("text", sa.String(4096), nullable=False),
        sa.Column("option_id", sa.String(256)),
        sa.Column("raw_payload", JSONB, nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_until", sa.DateTime(timezone=True)),
        sa.Column("claim_token", sa.String(36)),
    )
    op.create_index("ix_inbound_due", "inbound_deliveries", ["tenant_id", "status", "available_at"])
    op.create_table(
        "outbound_deliveries",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("send_key", sa.String(256), primary_key=True),
        sa.Column("recipient_number", sa.String(64), nullable=False),
        sa.Column("reply", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("advisor_event_id", sa.String(36)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_until", sa.DateTime(timezone=True)),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("provider_message_id", sa.String(256)),
        sa.Column("last_status_code", sa.Integer),
    )
    op.create_index(
        "ix_outbound_due", "outbound_deliveries", ["tenant_id", "status", "available_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_outbound_due", table_name="outbound_deliveries")
    op.drop_table("outbound_deliveries")
    op.drop_index("ix_inbound_due", table_name="inbound_deliveries")
    op.drop_table("inbound_deliveries")
