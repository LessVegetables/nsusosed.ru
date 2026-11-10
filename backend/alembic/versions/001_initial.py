"""Fresh schema for the pilot. Nothing is carried over from the MVP.

Revision ID: 001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("first_name", sa.String(40), nullable=False),
        sa.Column("last_name", sa.String(40), nullable=False, server_default=""),
        sa.Column("language", sa.String(2), nullable=False, server_default="ru"),
        sa.Column("gender", sa.String(1)),
        sa.Column("faculty", sa.String(20)),
        sa.Column("is_adult", sa.Boolean),
        sa.Column("intent", sa.String(10)),
        sa.Column("bio", sa.String(500), nullable=False, server_default=""),
        sa.Column("avatar_file", sa.String(64)),
        sa.Column("privacy_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("privacy_accepted_at", TZ, nullable=False),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", TZ),
        sa.CheckConstraint("language IN ('ru', 'en', 'zh')", name="ck_users_language"),
        sa.CheckConstraint("gender IN ('m', 'f')", name="ck_users_gender"),
        sa.CheckConstraint("intent IN ('seek_dorm', 'seek_apt', 'host', 'join')", name="ck_users_intent"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"],
                    postgresql_where=sa.text("deleted_at IS NOT NULL"))

    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", TZ, nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"], unique=True)
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "otp_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("privacy_accepted_at", TZ),
    )
    op.create_index("ix_otp_codes_email", "otp_codes", ["email"])
    op.create_index("ix_otp_codes_expires_at", "otp_codes", ["expires_at"])

    op.create_table(
        "auth_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("ip", sa.String(45)),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auth_events_email_kind_created", "auth_events", ["email", "kind", "created_at"])
    op.create_index("ix_auth_events_ip_created", "auth_events", ["ip", "created_at"])
    op.create_index("ix_auth_events_created_at", "auth_events", ["created_at"])


def downgrade() -> None:
    for table in ("auth_events", "otp_codes", "sessions", "users"):
        op.drop_table(table)
