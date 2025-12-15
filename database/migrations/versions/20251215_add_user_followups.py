"""add user_followups table

Revision ID: 20251215_add_user_followups
Revises: 20251215_add_user_goals
Create Date: 2025-12-15 17:00:00.000000

"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251215_add_user_followups'
down_revision = '20251215_add_user_goals'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """Создание таблицы user_followups."""
    op.create_table(
        'user_followups',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('scheduled_date', sa.DateTime(), nullable=True),
        sa.Column('followup_date', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('outcome', sa.Text(), nullable=True),
        sa.Column('outcome_sentiment', sa.String(length=20), nullable=True),
        sa.Column('priority', sa.String(length=10), nullable=False, server_default='medium'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('asked_at', sa.DateTime(), nullable=True),
        sa.Column('message_id', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['message_id'], ['conversations.id'], name='fk_user_followups_message_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_user_followups_user_id'),
        sa.PrimaryKeyConstraint('id', name='pk_user_followups')
    )

    # Индексы
    op.create_index('idx_user_followups_user', 'user_followups', ['user_id'], unique=False)
    op.create_index('idx_user_followups_status', 'user_followups', ['user_id', 'status'], unique=False)
    op.create_index('idx_user_followups_followup_date', 'user_followups', ['followup_date', 'status'], unique=False)
    op.create_index('idx_user_followups_priority', 'user_followups', ['user_id', 'priority', 'status'], unique=False)


def downgrade() -> None:
    """Удаление таблицы user_followups."""
    op.drop_index('idx_user_followups_priority', table_name='user_followups')
    op.drop_index('idx_user_followups_followup_date', table_name='user_followups')
    op.drop_index('idx_user_followups_status', table_name='user_followups')
    op.drop_index('idx_user_followups_user', table_name='user_followups')
    op.drop_table('user_followups')
