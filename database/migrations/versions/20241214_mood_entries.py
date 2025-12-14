"""Add mood_entries table

Revision ID: 20241214_mood
Revises:
Create Date: 2024-12-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20241214_mood'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create mood_entries table
    op.create_table(
        'mood_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=True),
        sa.Column('mood_score', sa.Integer(), nullable=False),
        sa.Column('energy_level', sa.Integer(), nullable=True),
        sa.Column('anxiety_level', sa.Integer(), nullable=True),
        sa.Column('primary_emotion', sa.String(50), nullable=False),
        sa.Column('secondary_emotions', sa.JSON(), nullable=True),
        sa.Column('triggers', sa.JSON(), nullable=True),
        sa.Column('context_tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index for user_id + created_at
    op.create_index(
        'idx_mood_user_created',
        'mood_entries',
        ['user_id', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('idx_mood_user_created', table_name='mood_entries')
    op.drop_table('mood_entries')
