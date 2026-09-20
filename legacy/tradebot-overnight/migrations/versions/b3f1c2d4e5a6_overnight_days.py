"""overnight_days

Revision ID: b3f1c2d4e5a6
Revises: 8492ed477737
Create Date: 2026-09-18 17:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3f1c2d4e5a6"
down_revision: str | None = "8492ed477737"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "overnight_days",
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action", sa.String(), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=True),
        sa.Column("entry_status", sa.String(), nullable=False),
        sa.Column("entry_filled", sa.Float(), nullable=False),
        sa.Column("exit_status", sa.String(), nullable=False),
        sa.Column("exit_filled", sa.Float(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("trade_date"),
    )


def downgrade() -> None:
    op.drop_table("overnight_days")
