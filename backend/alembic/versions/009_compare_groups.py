"""Comparing with friends: groups of people with no home, and the "compare" intent.

Revision ID: 009
Revises: 008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compare_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(8), nullable=False, unique=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "compare_members",
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("compare_groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_compare_members_user_id", "compare_members", ["user_id"])
    op.drop_constraint("ck_users_intent", "users", type_="check")
    op.create_check_constraint("ck_users_intent", "users", "intent IN ('seek_dorm', 'seek_apt', 'host', 'join', 'compare')")


def downgrade() -> None:
    op.execute("UPDATE users SET intent = NULL WHERE intent = 'compare'")
    op.drop_constraint("ck_users_intent", "users", type_="check")
    op.create_check_constraint("ck_users_intent", "users", "intent IN ('seek_dorm', 'seek_apt', 'host', 'join')")
    op.drop_table("compare_members")
    op.drop_table("compare_groups")
