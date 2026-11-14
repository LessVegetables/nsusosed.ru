"""Homes: how much sun gets in (sunny | partial | shady).

Nullable: homes listed before the question existed have no answer until a host edits them.

Revision ID: 007
Revises: 006
"""
import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("homes", sa.Column("sunlight", sa.String(10), nullable=True))
    op.create_check_constraint("ck_homes_sunlight", "homes", "sunlight IN ('sunny', 'partial', 'shady')")


def downgrade() -> None:
    op.drop_constraint("ck_homes_sunlight", "homes")
    op.drop_column("homes", "sunlight")
