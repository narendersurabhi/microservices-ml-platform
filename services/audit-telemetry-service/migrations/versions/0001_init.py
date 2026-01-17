"""init

Revision ID: 0001
Revises:
Create Date: 2025-02-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auditevent",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("auditevent")
