"""add tokens_used and cost_usd to user_reports

Revision ID: 20251229_add_tokens_to_reports
Revises: 20251229_add_user_reports
Create Date: 2025-12-29 19:30:00.000000
"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision = '20251229_add_tokens_to_reports'
down_revision = '20251229_add_user_reports'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """Add tokens_used and cost_usd columns to user_reports table."""
    op.add_column('user_reports', sa.Column('tokens_used', sa.Integer(), nullable=True))
    op.add_column('user_reports', sa.Column('cost_usd', sa.Float(), nullable=True))


def downgrade() -> None:
    """Remove tokens_used and cost_usd columns from user_reports table."""
    op.drop_column('user_reports', 'cost_usd')
    op.drop_column('user_reports', 'tokens_used')
