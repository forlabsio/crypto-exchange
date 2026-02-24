"""add allocated_usdt to bot_subscriptions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Branch Labels: None
Depends On: None
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('bot_subscriptions',
        sa.Column('allocated_usdt', sa.Numeric(18, 2), nullable=False, server_default='100'))

def downgrade():
    op.drop_column('bot_subscriptions', 'allocated_usdt')
