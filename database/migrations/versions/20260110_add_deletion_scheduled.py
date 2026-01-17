"""
Add deletion_scheduled_for field to users

Revision ID: 20260110_add_deletion_scheduled
Revises: 20260103_add_support_bot_tables
Create Date: 2026-01-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260110_add_deletion_scheduled'
down_revision = '8271ed5def3c'
branch_labels = None
depends_on = None


def upgrade():
    """
    Добавляет поле deletion_scheduled_for в таблицу users.
    """
    op.add_column('users', sa.Column('deletion_scheduled_for', sa.DateTime(), nullable=True))


def downgrade():
    """
    Удаляет поле deletion_scheduled_for из таблицы users.
    """
    op.drop_column('users', 'deletion_scheduled_for')
