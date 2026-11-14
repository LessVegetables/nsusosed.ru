"""Questionnaire v1: A1 and A2 now share the same six bedtime options.

A2 used to start an hour later (before 00:00 … 03:00 or later); it now starts at "before 23:00"
like A1, so every stored A2 answer moves up by one. A1 only gained "03:00 or later" at the end:
its stored answers keep their numbers ("02:00 or later" becomes "02:00–02:59").

Revision ID: 006
Revises: 005
"""
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

_SHIFT = """
    UPDATE questionnaire_responses
    SET answers = jsonb_set(answers, '{{A2}}', to_jsonb((answers->>'A2')::int {step}))
    WHERE version = 1 AND jsonb_typeof(answers->'A2') = 'number' {guard}
"""


def upgrade() -> None:
    op.execute(_SHIFT.format(step="+ 1", guard=""))


def downgrade() -> None:
    # "Before 23:00" and "23:00–23:59" both become the old "before 00:00"; A1's new last option
    # becomes the old last one.
    op.execute(_SHIFT.format(step="- 1", guard="AND (answers->>'A2')::int > 0"))
    op.execute("""
        UPDATE questionnaire_responses SET answers = jsonb_set(answers, '{A1}', '4')
        WHERE version = 1 AND jsonb_typeof(answers->'A1') = 'number' AND (answers->>'A1')::int = 5
    """)
