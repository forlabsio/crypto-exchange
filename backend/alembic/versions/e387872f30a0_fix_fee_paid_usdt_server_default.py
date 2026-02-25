"""fix_fee_paid_usdt_server_default

Revision ID: e387872f30a0
Revises: d1e2f3a4b5c6
Create Date: 2026-02-25 13:31:05.202396

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e387872f30a0'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add server_default='0' to fee_paid_usdt so existing NULL rows are defaulted
    op.alter_column(
        'bot_subscriptions',
        'fee_paid_usdt',
        existing_type=sa.Numeric(precision=18, scale=2),
        server_default='0',
        nullable=True,
    )
    # Backfill any existing NULL values
    op.execute("UPDATE bot_subscriptions SET fee_paid_usdt = 0 WHERE fee_paid_usdt IS NULL")


def downgrade() -> None:
    op.alter_column(
        'bot_subscriptions',
        'fee_paid_usdt',
        existing_type=sa.Numeric(precision=18, scale=2),
        server_default=None,
        nullable=True,
    )
