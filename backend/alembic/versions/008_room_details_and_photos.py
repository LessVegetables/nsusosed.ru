"""Rooms get their own details and photos; photos can be uploaded before a home exists.

  - rooms.area_m2 (optional), rooms.description, rooms.sunlight: an apartment's rooms differ
    (size, window side). The home's sunlight answer moves to each of its rooms.
  - room_photos: which of the home's photos show this room (a subset, any order of the home's).
  - staged_photos: photos uploaded while the listing form is still being filled in. They become
    home photos (same id) when the home is created; unclaimed ones are swept after a week.

Revision ID: 008
Revises: 007
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rooms", sa.Column("area_m2", sa.Integer, nullable=True))
    op.add_column("rooms", sa.Column("description", sa.Text, nullable=False, server_default=""))
    op.add_column("rooms", sa.Column("sunlight", sa.String(10), nullable=True))
    op.create_check_constraint("ck_rooms_sunlight", "rooms", "sunlight IN ('sunny', 'partial', 'shady')")
    op.create_check_constraint("ck_rooms_area", "rooms", "area_m2 BETWEEN 3 AND 200")
    op.execute("UPDATE rooms SET sunlight = homes.sunlight FROM homes WHERE homes.id = rooms.home_id")
    op.drop_constraint("ck_homes_sunlight", "homes")
    op.drop_column("homes", "sunlight")

    op.create_table(
        "room_photos",
        sa.Column("room_id", UUID(as_uuid=True), sa.ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("photo_id", UUID(as_uuid=True), sa.ForeignKey("home_photos.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_room_photos_photo_id", "room_photos", ["photo_id"])

    op.create_table(
        "staged_photos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("file_name", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("staged_photos")
    op.drop_index("ix_room_photos_photo_id", "room_photos")
    op.drop_table("room_photos")
    op.add_column("homes", sa.Column("sunlight", sa.String(10), nullable=True))
    op.create_check_constraint("ck_homes_sunlight", "homes", "sunlight IN ('sunny', 'partial', 'shady')")
    op.execute("""UPDATE homes SET sunlight = r.sunlight FROM rooms r
                  WHERE r.home_id = homes.id AND r.position = 0""")
    op.drop_constraint("ck_rooms_area", "rooms")
    op.drop_constraint("ck_rooms_sunlight", "rooms")
    op.drop_column("rooms", "sunlight")
    op.drop_column("rooms", "description")
    op.drop_column("rooms", "area_m2")
