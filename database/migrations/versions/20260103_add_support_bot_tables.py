"""add_support_bot_tables

Revision ID: 8271ed5def3c
Revises: 20260103_add_system_admin
Create Date: 2026-01-03 09:18:14.334990

Создаёт таблицы для бота технической поддержки:
- support_users: Пользователи поддержки
- support_messages: История сообщений
- support_reviews: Отзывы пользователей
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8271ed5def3c'
down_revision: Union[str, None] = '20260103_add_system_admin'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаём ENUM типы
    sender_type_enum = sa.Enum('user', 'admin', name='sender_type_enum')
    media_type_enum = sa.Enum(
        'text', 'photo', 'video', 'voice', 'video_note', 'document', 'sticker',
        name='media_type_enum'
    )

    sender_type_enum.create(op.get_bind(), checkfirst=True)
    media_type_enum.create(op.get_bind(), checkfirst=True)

    # Таблица support_users
    op.create_table(
        'support_users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('last_name', sa.String(length=255), nullable=True),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('photo_url', sa.String(length=500), nullable=True),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('is_bot_blocked', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id')
    )

    # Индексы для support_users
    op.create_index('idx_support_user_telegram_id', 'support_users', ['telegram_id'])
    op.create_index('idx_support_user_topic_id', 'support_users', ['topic_id'])

    # Таблица support_messages
    op.create_table(
        'support_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('sender_type', sender_type_enum, nullable=False),
        sa.Column('message_text', sa.Text(), nullable=True),
        sa.Column('media_type', media_type_enum, nullable=False, server_default='text'),
        sa.Column('media_file_id', sa.String(length=500), nullable=True),
        sa.Column('telegram_message_id', sa.BigInteger(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['support_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Индексы для support_messages
    op.create_index('idx_support_message_user', 'support_messages', ['user_id'])
    op.create_index('idx_support_message_created', 'support_messages', ['created_at'])
    op.create_index('idx_support_message_user_created', 'support_messages', ['user_id', 'created_at'])

    # Таблица support_reviews
    op.create_table(
        'support_reviews',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('about_self', sa.Text(), nullable=True),
        sa.Column('review_text', sa.Text(), nullable=False),
        sa.Column('permission_to_publish', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('telegram_message_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['support_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Индексы для support_reviews
    op.create_index('idx_support_review_user', 'support_reviews', ['user_id'])
    op.create_index('idx_support_review_created', 'support_reviews', ['created_at'])
    op.create_index('idx_support_review_permission', 'support_reviews', ['permission_to_publish'])


def downgrade() -> None:
    # Удаляем таблицы в обратном порядке
    op.drop_index('idx_support_review_permission', table_name='support_reviews')
    op.drop_index('idx_support_review_created', table_name='support_reviews')
    op.drop_index('idx_support_review_user', table_name='support_reviews')
    op.drop_table('support_reviews')

    op.drop_index('idx_support_message_user_created', table_name='support_messages')
    op.drop_index('idx_support_message_created', table_name='support_messages')
    op.drop_index('idx_support_message_user', table_name='support_messages')
    op.drop_table('support_messages')

    op.drop_index('idx_support_user_topic_id', table_name='support_users')
    op.drop_index('idx_support_user_telegram_id', table_name='support_users')
    op.drop_table('support_users')

    # Удаляем ENUM типы
    sa.Enum(name='media_type_enum').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='sender_type_enum').drop(op.get_bind(), checkfirst=True)
