"""Initial schema (OTP version)

Revision ID: 001_initial
Revises:
Create Date: 2026-10-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users (без password_hash) ───────────────────────
    op.create_table("users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("display_name", sa.String(60), nullable=False, server_default="Пользователь"),
        sa.Column("privacy_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("privacy_accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table("profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("questionnaire_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("answers", postgresql.JSONB, nullable=False),
        sa.Column("situation", sa.String(30), nullable=False),
        sa.Column("budget_max_rub", sa.Integer, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("budget_max_rub BETWEEN 1 AND 200000", name="ck_profiles_budget"),
    )

    op.create_table("listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("occupied_count", sa.Integer, nullable=False),
        sa.Column("contact_username", sa.String(32), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("building", sa.String(20), nullable=True),
        sa.Column("room_number", sa.Integer, nullable=True),
        sa.Column("floor", sa.Integer, nullable=True),
        sa.Column("is_corner", sa.Boolean, nullable=True),
        sa.Column("windows_count", sa.Integer, nullable=True),
        sa.Column("view", sa.String(10), nullable=True),
        sa.Column("layout", sa.String(300), nullable=True),
        sa.Column("district", sa.String(80), nullable=True),
        sa.Column("monthly_cost_per_person_rub", sa.Integer, nullable=True),
        sa.Column("invite_token_hash", sa.String(64), nullable=True),
        sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("capacity BETWEEN 1 AND 10", name="ck_listings_capacity"),
        sa.CheckConstraint("occupied_count BETWEEN 1 AND capacity", name="ck_listings_occupied"),
        sa.CheckConstraint("kind IN ('dorm', 'apartment')", name="ck_listings_kind"),
        sa.CheckConstraint("status IN ('active', 'paused')", name="ck_listings_status"),
        sa.CheckConstraint("monthly_cost_per_person_rub BETWEEN 1 AND 200000", name="ck_listings_cost"),
    )
    op.create_index("uq_listings_dorm_addr", "listings", ["building", "room_number"],
                    unique=True, postgresql_where=sa.text("building IS NOT NULL AND room_number IS NOT NULL"))
    op.create_index("ix_listings_kind_status_confirmed", "listings", ["kind", "status", "confirmed_at"])

    op.create_table("memberships",
        sa.Column("listing_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, unique=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_memberships_listing_id", "memberships", ["listing_id"])

    op.create_table("sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"], unique=True)
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    # ── otp_codes (новая таблица) ───────────────────────
    op.create_table("otp_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_otp_codes_user_id", "otp_codes", ["user_id"])
    op.create_index("ix_otp_codes_email", "otp_codes", ["email"])
    op.create_index("ix_otp_codes_expires_at", "otp_codes", ["expires_at"])


def downgrade() -> None:
    op.drop_table("otp_codes")
    op.drop_table("sessions")
    op.drop_table("memberships")
    op.drop_table("listings")
    op.drop_table("profiles")
    op.drop_table("users")
