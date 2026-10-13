"""OTP codes are tied to an email, users are created after verification

Revision ID: 002_otp_without_user
Revises: 001_initial
Create Date: 2026-10-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_otp_without_user"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_otp_codes_user_id", table_name="otp_codes")
    op.drop_column("otp_codes", "user_id")
    op.add_column("otp_codes", sa.Column("privacy_accepted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("otp_codes", "privacy_accepted_at")
    # Коды короткоживущие — при откате просто удаляем их.
    op.execute("DELETE FROM otp_codes")
    op.add_column("otp_codes", sa.Column("user_id", postgresql.UUID(as_uuid=True),
                                         sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False))
    op.create_index("ix_otp_codes_user_id", "otp_codes", ["user_id"])
