"""XEON operational state, separate from any store connector database.

Revision ID: 0001_operational_state
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_operational_state"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "funnel_states",
        sa.Column("conversation_key", sa.String(256), primary_key=True),
        sa.Column("payload", JSONB, nullable=False),
    )
    op.create_table(
        "cart_states",
        sa.Column("conversation_key", sa.String(256), primary_key=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
    )
    op.create_table(
        "conversation_memories",
        sa.Column("conversation_key", sa.String(256), primary_key=True),
        sa.Column("payload", JSONB, nullable=False),
    )
    op.create_table(
        "quote_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("request_id", sa.String(256), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.UniqueConstraint("tenant_id", "request_id", name="uq_quote_drafts_tenant_request"),
    )
    op.create_table(
        "processed_events",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("instance", sa.String(128), primary_key=True),
        sa.Column("message_id", sa.String(256), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_table("quote_drafts")
    op.drop_table("conversation_memories")
    op.drop_table("cart_states")
    op.drop_table("funnel_states")
