"""Add onboarding_events table

Revision ID: 20260111_add_onboarding_events
Revises: 20260110_add_deletion_scheduled
Create Date: 2026-01-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260111_add_onboarding_events'
down_revision = '20260110_add_deletion_scheduled'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create onboarding_events table for tracking user onboarding flow."""
    # Use JSON for SQLite compatibility, JSONB for PostgreSQL
    op.create_table(
        'onboarding_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_name', sa.String(100), nullable=False, index=True),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Index('ix_onboarding_events_user_id', 'user_id'),
        sa.Index('ix_onboarding_events_created_at', 'created_at'),
    )


def downgrade() -> None:
    """Drop onboarding_events table."""
    op.drop_table('onboarding_events')
