"""add admin_users and admin_logs tables

Revision ID: 20251229_add_admin_users_and_logs
Revises: 20251215_add_user_followups
Create Date: 2025-12-29 00:00:00.000000

"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251229_add_admin_users_and_logs'
down_revision = '20251215_add_user_followups'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """Add admin_users and admin_logs tables for moderator system."""

    # Create admin_users table
    op.create_table(
        'admin_users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('last_name', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='moderator'),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('accent_color', sa.String(length=7), nullable=False, server_default='#1976d2'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['admin_users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id')
    )

    # Create indexes for admin_users
    op.create_index('idx_admin_user_telegram_id', 'admin_users', ['telegram_id'], unique=False)
    op.create_index('idx_admin_user_role', 'admin_users', ['role'], unique=False)
    op.create_index('idx_admin_user_active', 'admin_users', ['is_active'], unique=False)

    # Create admin_logs table
    op.create_table(
        'admin_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('admin_user_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['admin_user_id'], ['admin_users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for admin_logs
    op.create_index('idx_admin_log_user', 'admin_logs', ['admin_user_id'], unique=False)
    op.create_index('idx_admin_log_action', 'admin_logs', ['action'], unique=False)
    op.create_index('idx_admin_log_resource', 'admin_logs', ['resource_type', 'resource_id'], unique=False)
    op.create_index('idx_admin_log_created', 'admin_logs', ['created_at'], unique=False)


def downgrade() -> None:
    """Remove admin_users and admin_logs tables."""

    # Drop admin_logs table (must be first due to foreign key)
    op.drop_index('idx_admin_log_created', table_name='admin_logs')
    op.drop_index('idx_admin_log_resource', table_name='admin_logs')
    op.drop_index('idx_admin_log_action', table_name='admin_logs')
    op.drop_index('idx_admin_log_user', table_name='admin_logs')
    op.drop_table('admin_logs')

    # Drop admin_users table
    op.drop_index('idx_admin_user_active', table_name='admin_users')
    op.drop_index('idx_admin_user_role', table_name='admin_users')
    op.drop_index('idx_admin_user_telegram_id', table_name='admin_users')
    op.drop_table('admin_users')
