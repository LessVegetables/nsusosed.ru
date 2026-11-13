"""Contact methods on the account.

Revision ID: 002
Revises: 001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_contacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("value", sa.String(100), nullable=False),
        sa.UniqueConstraint("user_id", "type", name="uq_user_contacts_user_type"),
    )
    op.create_index("ix_user_contacts_user_id", "user_contacts", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_contacts")
