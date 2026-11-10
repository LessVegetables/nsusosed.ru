"""Invite links.

Revision ID: 005
Revises: 004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("home_id", UUID(as_uuid=True), sa.ForeignKey("homes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", UUID(as_uuid=True), sa.ForeignKey("rooms.id", ondelete="SET NULL")),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uses", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_invites_home_id", "invites", ["home_id"])


def downgrade() -> None:
    op.drop_table("invites")
