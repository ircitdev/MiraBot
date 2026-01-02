"""
Script to check and log inactive users.
Проверяет пользователей с 50+ сообщениями, которые не писали 5+ дней.
Запускается через cron или вручную.
"""

import asyncio
from datetime import datetime, timedelta
from database.repositories.user import UserRepository
from database.repositories.conversation import ConversationRepository
from utils.system_logger import system_logger
from loguru import logger


async def check_inactive_users():
    """Проверяет и логирует неактивных пользователей."""
    user_repo = UserRepository()
    conversation_repo = ConversationRepository()

    # Получаем всех пользователей
    users = await user_repo.list_users(limit=10000)

    logger.info(f"Checking {len(users)} users for inactivity...")

    inactive_count = 0
    now = datetime.now()
    threshold_days = 5

    for user in users:
        # Пропускаем заблокированных и не прошедших онбординг
        if user.is_blocked or not user.onboarding_completed:
            continue

        # Получаем сообщения пользователя
        conversations = await conversation_repo.get_by_user(
            user.id,
            limit=100  # Последние 100 сообщений
        )

        # Считаем сообщения пользователя
        user_messages = [c for c in conversations if c.role == "user"]
        total_messages = len(user_messages)

        # Проверяем, есть ли минимум 50 сообщений
        if total_messages < 50:
            continue

        # Находим последнее сообщение
        if not user_messages:
            continue

        last_message = max(user_messages, key=lambda c: c.created_at)
        days_since_last = (now - last_message.created_at).days

        # Если неактивен 5+ дней
        if days_since_last >= threshold_days:
            try:
                await system_logger.log_user_inactive(
                    user_id=user.id,
                    telegram_id=user.telegram_id,
                    username=user.username,
                    total_messages=total_messages,
                    days_inactive=days_since_last,
                )
                inactive_count += 1
                logger.info(
                    f"User {user.telegram_id} ({user.username}) inactive for {days_since_last} days "
                    f"({total_messages} messages)"
                )
            except Exception as e:
                logger.error(f"Failed to log inactive user {user.telegram_id}: {e}")

    logger.info(f"Found {inactive_count} inactive users")


async def main():
    """Главная функция."""
    logger.info("Starting inactive users check...")
    try:
        await check_inactive_users()
        logger.info("Inactive users check completed successfully")
    except Exception as e:
        logger.error(f"Error during inactive users check: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
