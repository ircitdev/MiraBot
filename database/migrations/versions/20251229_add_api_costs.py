"""Add api_costs table for tracking API usage costs

Revision ID: 20251229_add_api_costs
Revises: 20251229_add_tokens_to_reports
Create Date: 2025-12-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251229_add_api_costs'
down_revision = '20251229_add_tokens_to_reports'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add api_costs table for tracking Claude, Yandex, OpenAI API expenses."""
    op.create_table(
        'api_costs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('operation', sa.String(100), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('characters_count', sa.Integer(), nullable=True),
        sa.Column('audio_seconds', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Float(), nullable=False),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('message_id', sa.BigInteger(), nullable=True),
        sa.Column('admin_user_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_api_cost_user', 'api_costs', ['user_id'], unique=False)
    op.create_index('idx_api_cost_provider', 'api_costs', ['provider'], unique=False)
    op.create_index('idx_api_cost_created', 'api_costs', ['created_at'], unique=False)
    op.create_index('idx_api_cost_user_created', 'api_costs', ['user_id', 'created_at'], unique=False)
    op.create_index('idx_api_cost_provider_created', 'api_costs', ['provider', 'created_at'], unique=False)


def downgrade() -> None:
    """Remove api_costs table."""
    op.drop_index('idx_api_cost_provider_created', table_name='api_costs')
    op.drop_index('idx_api_cost_user_created', table_name='api_costs')
    op.drop_index('idx_api_cost_created', table_name='api_costs')
    op.drop_index('idx_api_cost_provider', table_name='api_costs')
    op.drop_index('idx_api_cost_user', table_name='api_costs')
    op.drop_table('api_costs')
