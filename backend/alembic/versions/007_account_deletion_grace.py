"""Account deletion with a grace period

users.deleted_at: when the user asked to delete the account. Until the grace
period (ACCOUNT_DELETION_GRACE_DAYS) passes the account is hidden and can be
restored by logging in; after that it is erased for good.

Revision ID: 007_account_deletion_grace
Revises: 006_homes_admins
Create Date: 2026-11-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007_account_deletion_grace"
down_revision: Union[str, None] = "006_homes_admins"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"],
                    postgresql_where=sa.text("deleted_at IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_column("users", "deleted_at")
