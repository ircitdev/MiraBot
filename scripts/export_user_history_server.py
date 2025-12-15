"""
Экспорт истории переписки пользователя (для запуска на сервере).
"""

import asyncio
import sys
import os
from datetime import datetime

# Добавить корень проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.repositories.conversation import ConversationRepository
from database.repositories.user import UserRepository


async def export_user_history(telegram_id: int):
    """Экспортировать историю переписки пользователя."""

    user_repo = UserRepository()
    conv_repo = ConversationRepository()

    # Получить пользователя
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        print(f"❌ Пользователь с Telegram ID {telegram_id} не найден")
        return

    print(f"✅ Найден пользователь: {user.display_name or user.first_name or 'Без имени'}")
    print(f"   ID в БД: {user.id}")
    print(f"   Username: @{user.username or 'не указан'}")
    print(f"   Создан: {user.created_at.strftime('%Y-%m-%d %H:%M')}")
    print()

    # Получить все сообщения
    messages, total = await conv_repo.get_paginated(user.id, page=1, per_page=10000)

    print(f"📊 Всего сообщений: {total}")
    print()
    print("=" * 80)
    print()

    # Вывести историю
    for msg in reversed(messages):  # В хронологическом порядке
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        role = "👤 Пользователь" if msg.role == "user" else "🤖 Мира"
        msg_type = f"[{msg.message_type}]" if msg.message_type != "text" else ""

        print(f"{timestamp} | {role} {msg_type}")
        print(f"{msg.content}")

        if msg.tags:
            print(f"   Теги: {', '.join(msg.tags)}")

        print()
        print("-" * 80)
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python export_user_history_server.py <telegram_id>")
        sys.exit(1)

    telegram_id = int(sys.argv[1])
    asyncio.run(export_user_history(telegram_id))
