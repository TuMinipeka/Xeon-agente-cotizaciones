"""SQLAlchemy Core tables mirrored by Alembic migrations."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

funnel_states = Table(
    "funnel_states",
    metadata,
    Column("conversation_key", String(256), primary_key=True),
    Column("payload", JSONB, nullable=False),
)
cart_states = Table(
    "cart_states",
    metadata,
    Column("conversation_key", String(256), primary_key=True),
    Column("version", Integer, nullable=False),
    Column("payload", JSONB, nullable=False),
)
conversation_memories = Table(
    "conversation_memories",
    metadata,
    Column("conversation_key", String(256), primary_key=True),
    Column("payload", JSONB, nullable=False),
)
quote_drafts = Table(
    "quote_drafts",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("tenant_id", String(128), nullable=False),
    Column("request_id", String(256), nullable=False),
    Column("payload", JSONB, nullable=False),
    UniqueConstraint("tenant_id", "request_id", name="uq_quote_drafts_tenant_request"),
)
processed_events = Table(
    "processed_events",
    metadata,
    Column("tenant_id", String(128), primary_key=True),
    Column("instance", String(128), primary_key=True),
    Column("message_id", String(256), primary_key=True),
)
advisor_events = Table(
    "advisor_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("tenant_id", String(128), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("status", String(16), nullable=False),
    Column("conversation_key", String(256)),
    Column("quote_id", String(36)),
    Column("resolved_by", String(64)),
    Column("resolved_at", DateTime(timezone=True)),
    Column("reason", String(300)),
    Column("client_notified", Boolean),
    Index("ix_advisor_events_tenant_status_created", "tenant_id", "status", "created_at"),
)
