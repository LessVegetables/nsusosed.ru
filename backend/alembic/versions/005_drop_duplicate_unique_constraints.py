"""Drop unique constraints that duplicate unique indexes

users.email and sessions.token_hash each had both a UNIQUE constraint and a
unique index (ix_users_email, ix_sessions_token_hash). The indexes stay and
still enforce uniqueness; this matches what the models declare.

Revision ID: 005_drop_duplicate_uniques
Revises: 004_listing_contact_type
Create Date: 2026-10-13
"""
from typing import Sequence, Union
from alembic import op

revision: str = "005_drop_duplicate_uniques"
down_revision: Union[str, None] = "004_listing_contact_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.drop_constraint("sessions_token_hash_key", "sessions", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("sessions_token_hash_key", "sessions", ["token_hash"])
    op.create_unique_constraint("users_email_key", "users", ["email"])
