"""audit_events.created_at uses clock_timestamp

PostgreSQL's now() returns the time the *transaction* started, so every
statement inside one transaction sees the same value. Two audit rows written
during a single request therefore shared a created_at, and their order could
not be recovered afterwards - which is the one thing an audit log must not
lose.

clock_timestamp() reads the actual clock on each call. Verified in psql:
inside one transaction now() returned 23:14:44.199224 twice, while
clock_timestamp() advanced to 23:14:44.253365.

Only the column default changes. Existing rows keep the timestamps they were
written with; this affects rows inserted from here on.

Revision ID: 48274f3e8da8
Revises: 8ac0e215d10c
Create Date: 2026-11-23 23:15:09.766254

"""
from typing import Sequence, Union

from alembic import op

revision: str = "48274f3e8da8"
down_revision: Union[str, None] = "8ac0e215d10c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE audit_events "
        "ALTER COLUMN created_at SET DEFAULT clock_timestamp()"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE audit_events ALTER COLUMN created_at SET DEFAULT now()")
