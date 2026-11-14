"""Dorm room labels: the block letter is stored as a Latin b/m ("100б" → "100b", "100м" → "100m").

The form now offers only a number from 100 to 999 plus Б, М or no letter. A label that would
collide with one already in the new spelling is left as it is rather than failing the upgrade.

Revision ID: 007
Revises: 006
"""
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

_RESPELL = """
    UPDATE homes h SET room_label = translate(h.room_label, '{src}', '{dst}')
    WHERE h.kind = 'dorm' AND h.room_label ~ '[{src}]'
      AND NOT EXISTS (SELECT 1 FROM homes o WHERE o.kind = 'dorm' AND o.building = h.building
                      AND o.room_label = translate(h.room_label, '{src}', '{dst}'))
"""


def upgrade() -> None:
    op.execute(_RESPELL.format(src="бм", dst="bm"))


def downgrade() -> None:
    op.execute(_RESPELL.format(src="bm", dst="бм"))
