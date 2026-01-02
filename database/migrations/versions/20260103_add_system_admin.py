"""
Add system admin user for automatic logs

Revision ID: 20260103_add_system_admin
Revises: 20251229_add_admin_users_and_logs
Create Date: 2026-01-03

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '20260103_add_system_admin'
down_revision = '20251229_add_admin_users_and_logs'
branch_labels = None
depends_on = None


def upgrade():
    """
    Создаёт системного администратора для автоматических логов.
    """
    # Создаём системного администратора
    op.execute("""
        INSERT INTO admin_users (telegram_id, username, first_name, role, is_active, created_at)
        VALUES (0, 'system', 'System', 'admin', true, NOW())
        ON CONFLICT (telegram_id) DO NOTHING;
    """)


def downgrade():
    """
    Удаляет системного администратора.
    """
    op.execute("""
        DELETE FROM admin_users WHERE telegram_id = 0;
    """)
