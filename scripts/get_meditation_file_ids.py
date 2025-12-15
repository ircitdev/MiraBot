"""
Скрипт для получения file_id голосовых сообщений с медитациями.
"""

import asyncio
from telegram import Bot
from config.settings import settings

# Ссылки на сообщения
MEDITATION_MESSAGES = [
    "https://t.me/uspmusiclib/120",  # quick_breath
    "https://t.me/uspmusiclib/121",  # anxiety_relief
    "https://t.me/uspmusiclib/122",  # body_relaxation
    "https://t.me/uspmusiclib/123",  # morning_intention
]

# Маппинг: порядковый номер -> meditation_id
MEDITATION_IDS = [
    "quick_breath",
    "anxiety_relief",
    "body_relaxation",
    "morning_intention",
]


async def get_file_ids():
    """Получает file_id из сообщений."""
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    print("Получение file_id голосовых сообщений...\n")
    print("ИНСТРУКЦИЯ:")
    print("1. Перешлите голосовые сообщения из канала боту (в личку)")
    print("2. Бот автоматически выведет file_id в логах")
    print("3. Или используйте этот скрипт с прямым доступом к сообщениям\n")

    # Для публичных каналов нужно использовать метод getChatMember
    # или переслать сообщения боту вручную

    for i, url in enumerate(MEDITATION_MESSAGES):
        parts = url.split("/")
        channel_username = f"@{parts[-2]}"
        message_id = int(parts[-1])
        meditation_id = MEDITATION_IDS[i]

        print(f"📍 {meditation_id}:")
        print(f"   Channel: {channel_username}")
        print(f"   Message ID: {message_id}")
        print(f"   URL: {url}")
        print(f"   → Перешлите это сообщение боту для получения file_id\n")

    await bot.close()

    print("\n" + "="*60)
    print("АЛЬТЕРНАТИВНЫЙ СПОСОБ:")
    print("Добавьте этот код в bot/handlers/voice.py временно:")
    print("""
# В начале функции handle_voice, после получения voice:
logger.info(f"MEDITATION FILE_ID: {voice.file_id}")
logger.info(f"Duration: {voice.duration}s")
    """)


if __name__ == "__main__":
    asyncio.run(get_file_ids())
