"""Listing contact: any type (telegram, whatsapp, max, phone, other)

Revision ID: 004_listing_contact_type
Revises: 003_auth_events
Create Date: 2026-10-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004_listing_contact_type"
down_revision: Union[str, None] = "003_auth_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Существующие контакты — Telegram-юзернеймы.
    op.add_column("listings", sa.Column("contact_type", sa.String(10), nullable=False, server_default="telegram"))
    op.alter_column("listings", "contact_type", server_default=None)
    op.alter_column("listings", "contact_username", new_column_name="contact_value",
                    type_=sa.String(100), existing_type=sa.String(32), existing_nullable=False)
    op.create_check_constraint("ck_listings_contact_type", "listings",
                               "contact_type IN ('telegram', 'whatsapp', 'max', 'phone', 'other')")


def downgrade() -> None:
    op.drop_constraint("ck_listings_contact_type", "listings", type_="check")
    # Не-Telegram контакты в старую схему не помещаются.
    op.execute("DELETE FROM listings WHERE contact_type <> 'telegram'")
    op.alter_column("listings", "contact_value", new_column_name="contact_username",
                    type_=sa.String(32), existing_type=sa.String(100), existing_nullable=False)
    op.drop_column("listings", "contact_type")
