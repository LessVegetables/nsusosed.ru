"""Homes with admins: no single owner, several contacts, photos, user language

- listings.owner_id goes away: a home exists through its members, and
  memberships.is_admin says who can manage it. Former owners become admins.
- listings.contact_type/contact_value move to listing_contacts (several per home).
- listing_photos: photo files live on disk (MEDIA_DIR), the table keeps their order.
- profiles.situation: looking -> seeker, dorm_resident/apartment_host -> host.
  Everyone who is a member of a home is a host.
- users.language: interface language, null until the user picks one.

Revision ID: 006_homes_admins
Revises: 005_drop_duplicate_uniques
Create Date: 2026-10-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006_homes_admins"
down_revision: Union[str, None] = "005_drop_duplicate_uniques"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("language", sa.String(2), nullable=True))
    op.create_check_constraint("ck_users_language", "users", "language IN ('ru', 'en')")

    op.add_column("memberships", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("""
        UPDATE memberships m SET is_admin = true
        FROM listings l WHERE l.id = m.listing_id AND l.owner_id = m.user_id
    """)

    op.create_table("listing_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("value", sa.String(100), nullable=False),
        sa.CheckConstraint("type IN ('telegram', 'whatsapp', 'max', 'phone', 'other')", name="ck_listing_contacts_type"),
    )
    op.create_index("ix_listing_contacts_listing_id", "listing_contacts", ["listing_id"])
    op.execute("""
        INSERT INTO listing_contacts (id, listing_id, position, type, value)
        SELECT gen_random_uuid(), id, 0, contact_type, contact_value FROM listings
    """)
    op.drop_constraint("ck_listings_contact_type", "listings", type_="check")
    op.drop_column("listings", "contact_type")
    op.drop_column("listings", "contact_value")
    op.drop_column("listings", "owner_id")

    op.create_table("listing_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_listing_photos_listing_id", "listing_photos", ["listing_id"])

    op.execute("UPDATE profiles SET situation = CASE WHEN situation = 'looking' THEN 'seeker' ELSE 'host' END")
    op.execute("UPDATE profiles SET situation = 'host' WHERE user_id IN (SELECT user_id FROM memberships)")
    op.create_check_constraint("ck_profiles_situation", "profiles", "situation IN ('seeker', 'host')")


def downgrade() -> None:
    op.drop_constraint("ck_profiles_situation", "profiles", type_="check")
    op.execute("UPDATE profiles SET situation = CASE WHEN situation = 'seeker' THEN 'looking' ELSE 'dorm_resident' END")
    op.drop_table("listing_photos")

    # Back to one owner and one contact per listing: the earliest admin owns it,
    # the first contact stays. Listings without an admin can't be kept.
    op.add_column("listings", sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("listings", sa.Column("contact_type", sa.String(10), nullable=True))
    op.add_column("listings", sa.Column("contact_value", sa.String(100), nullable=True))
    op.execute("""
        UPDATE listings l SET owner_id = (
            SELECT m.user_id FROM memberships m WHERE m.listing_id = l.id AND m.is_admin
            ORDER BY m.joined_at LIMIT 1)
    """)
    op.execute("""
        UPDATE listings l SET contact_type = c.type, contact_value = c.value
        FROM listing_contacts c WHERE c.listing_id = l.id AND c.position = (
            SELECT min(position) FROM listing_contacts WHERE listing_id = l.id)
    """)
    op.execute("DELETE FROM listings WHERE owner_id IS NULL OR contact_type IS NULL")
    op.alter_column("listings", "owner_id", nullable=False)
    op.alter_column("listings", "contact_type", nullable=False)
    op.alter_column("listings", "contact_value", nullable=False)
    op.create_foreign_key("listings_owner_id_fkey", "listings", "users", ["owner_id"], ["id"], ondelete="CASCADE")
    op.create_unique_constraint("listings_owner_id_key", "listings", ["owner_id"])
    op.create_check_constraint("ck_listings_contact_type", "listings",
                               "contact_type IN ('telegram', 'whatsapp', 'max', 'phone', 'other')")
    op.drop_table("listing_contacts")

    op.drop_column("memberships", "is_admin")
    op.drop_constraint("ck_users_language", "users", type_="check")
    op.drop_column("users", "language")
