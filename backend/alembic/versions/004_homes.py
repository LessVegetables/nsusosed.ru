"""Homes, rooms, memberships and home photos.

Revision ID: 004
Revises: 003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "homes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("building", sa.String(20)),
        sa.Column("room_label", sa.String(10)),
        sa.Column("district", sa.String(60)),
        sa.Column("lat", sa.Float),
        sa.Column("lon", sa.Float),
        sa.Column("radius_m", sa.Integer),
        sa.Column("utilities_mode", sa.String(10)),
        sa.Column("utilities_rub", sa.Integer),
        sa.Column("internet_mode", sa.String(10)),
        sa.CheckConstraint("kind IN ('dorm', 'apartment')", name="ck_homes_kind"),
    )
    op.create_index("uq_homes_dorm_room", "homes", ["building", "room_label"], unique=True,
                    postgresql_where=sa.text("kind = 'dorm'"))

    op.create_table(
        "rooms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("home_id", UUID(as_uuid=True), sa.ForeignKey("homes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("name", sa.String(40), nullable=False, server_default=""),
        sa.Column("gender", sa.String(3), nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("free_places", sa.Integer, nullable=False),
        sa.Column("rent_rub", sa.Integer),
        sa.Column("emoji", sa.String(40), nullable=False),
        sa.Column("emoji_key", sa.String(40), nullable=False, unique=True),
        sa.CheckConstraint("gender IN ('m', 'f', 'any')", name="ck_rooms_gender"),
        sa.CheckConstraint("capacity BETWEEN 1 AND 6 AND free_places BETWEEN 0 AND capacity", name="ck_rooms_places"),
    )
    op.create_index("ix_rooms_home_id", "rooms", ["home_id"])

    op.create_table(
        "memberships",
        sa.Column("home_id", UUID(as_uuid=True), sa.ForeignKey("homes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("room_id", UUID(as_uuid=True), sa.ForeignKey("rooms.id", ondelete="SET NULL")),
        sa.Column("joined_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("can_edit", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("can_photos", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("can_invites", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("can_residents", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("user_id", name="uq_memberships_user"),
    )

    op.create_table(
        "home_photos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("home_id", UUID(as_uuid=True), sa.ForeignKey("homes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("file_name", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
    )
    op.create_index("ix_home_photos_home_id", "home_photos", ["home_id"])


def downgrade() -> None:
    for table in ("home_photos", "memberships", "rooms", "homes"):
        op.drop_table(table)
