"""Email-send log (kept 3 days) and the site going 18+ only.

Everyone now confirms they are 18 or older when they log in (the consent checkbox on the
login page). People already logged in who haven't said they are 18+ are logged out, so their
next login asks them.

Revision ID: 010
Revises: 009
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("message_id", sa.String(200)),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_email_log_created_at", "email_log", ["created_at"])
    op.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE is_adult IS NOT TRUE)")


def downgrade() -> None:
    op.drop_index("ix_email_log_created_at", table_name="email_log")
    op.drop_table("email_log")
