"""add user triggers

Revision ID: 20251215_add_user_triggers
Revises: 20251215_add_content_preferences_and_quiet_hours
Create Date: 2025-12-15 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251215_add_user_triggers'
down_revision: Union[str, None] = '5da41d0baade'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user_triggers table."""
    op.create_table(
        'user_triggers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('topic', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('severity', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('last_mentioned_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_user_triggers_user', 'user_triggers', ['user_id'], unique=False)
    op.create_index('idx_user_triggers_active', 'user_triggers', ['user_id', 'is_active'], unique=False)


def downgrade() -> None:
    """Remove user_triggers table."""
    op.drop_index('idx_user_triggers_active', table_name='user_triggers')
    op.drop_index('idx_user_triggers_user', table_name='user_triggers')
    op.drop_table('user_triggers')
