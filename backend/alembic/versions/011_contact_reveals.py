"""Contact-reveal log: who got whose contacts, kept 3 years.

Revision ID: 011
Revises: 010
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No foreign keys on home_id/room_id and the emails copied in: rows must outlive the
    # accounts and the home (see app/models/contact_reveal.py).
    op.create_table(
        "contact_reveals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("viewer_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("viewer_email", sa.String(254), nullable=False),
        sa.Column("home_id", UUID(as_uuid=True), nullable=False),
        sa.Column("room_id", UUID(as_uuid=True), nullable=False),
        sa.Column("host_emails", ARRAY(sa.String(254)), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_contact_reveals_viewer_id", "contact_reveals", ["viewer_id"])
    op.create_index("ix_contact_reveals_home_id", "contact_reveals", ["home_id"])
    op.create_index("ix_contact_reveals_created_at", "contact_reveals", ["created_at"])


def downgrade() -> None:
    op.drop_table("contact_reveals")
