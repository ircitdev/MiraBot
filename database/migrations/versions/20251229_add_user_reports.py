"""add user_reports table

Revision ID: 20251229_add_user_reports
Revises: 20251229_add_admin_users_and_logs
Create Date: 2025-12-29 18:50:00.000000

"""
from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251229_add_user_reports'
down_revision = '20251229_add_admin_users_and_logs'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """Add user_reports table for AI-generated user summaries."""

    # Create user_reports table
    op.create_table(
        'user_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['telegram_id'], ['users.telegram_id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['admin_users.telegram_id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for user_reports
    op.create_index('idx_report_telegram_id', 'user_reports', ['telegram_id'], unique=False)
    op.create_index('idx_report_created_at', 'user_reports', ['created_at'], unique=False)


def downgrade() -> None:
    """Remove user_reports table."""

    # Drop indexes
    op.drop_index('idx_report_created_at', table_name='user_reports')
    op.drop_index('idx_report_telegram_id', table_name='user_reports')

    # Drop table
    op.drop_table('user_reports')
