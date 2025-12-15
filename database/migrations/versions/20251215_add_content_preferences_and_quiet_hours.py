"""add_content_preferences_and_quiet_hours

Revision ID: 5da41d0baade
Revises: 20241214_mood
Create Date: 2025-12-15 02:53:33.289164

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5da41d0baade'
down_revision: Union[str, None] = '20241214_mood'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавить content_preferences
    op.add_column('users', sa.Column('content_preferences', sa.JSON(), nullable=True))

    # Добавить quiet_hours_start и quiet_hours_end
    op.add_column('users', sa.Column('quiet_hours_start', sa.Time(), nullable=True))
    op.add_column('users', sa.Column('quiet_hours_end', sa.Time(), nullable=True))


def downgrade() -> None:
    # Удалить в обратном порядке
    op.drop_column('users', 'quiet_hours_end')
    op.drop_column('users', 'quiet_hours_start')
    op.drop_column('users', 'content_preferences')
