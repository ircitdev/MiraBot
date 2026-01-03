"""add user_goals table

Revision ID: 20251215_add_user_goals
Revises: 20251215_add_user_triggers
Create Date: 2025-12-15 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251215_add_user_goals'
down_revision: Union[str, None] = '20251215_add_user_triggers'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт таблицу user_goals для SMART goals tracking."""
    op.create_table(
        'user_goals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('original_goal', sa.Text(), nullable=False),
        sa.Column('smart_goal', sa.Text(), nullable=True),
        sa.Column('specific', sa.Text(), nullable=True),
        sa.Column('measurable', sa.String(length=255), nullable=True),
        sa.Column('achievable', sa.Text(), nullable=True),
        sa.Column('relevant', sa.Text(), nullable=True),
        sa.Column('time_bound', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('milestones', sa.JSON(), nullable=True),
        sa.Column('reminder_frequency', sa.String(length=20), nullable=True),
        sa.Column('last_check_in', sa.DateTime(), nullable=True),
        sa.Column('next_check_in', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('abandoned_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    # Индексы
    op.create_index('idx_user_goals_user', 'user_goals', ['user_id'])
    op.create_index('idx_user_goals_status', 'user_goals', ['user_id', 'status'])
    op.create_index('idx_user_goals_next_checkin', 'user_goals', ['next_check_in', 'status'])


def downgrade() -> None:
    """Удаляет таблицу user_goals."""
    op.drop_index('idx_user_goals_next_checkin', table_name='user_goals')
    op.drop_index('idx_user_goals_status', table_name='user_goals')
    op.drop_index('idx_user_goals_user', table_name='user_goals')
    op.drop_table('user_goals')
