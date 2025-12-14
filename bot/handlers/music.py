"""
Music Handler.
Обработка запросов музыки и пересылка из супергруппы.
"""

import re
import asyncio
import random
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from services.music_forwarder import (
    music_forwarder,
    MUSIC_TOPICS,
)


async def check_and_send_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
    mood: str = None,
) -> bool:
    """
    Проверяет запрос музыки и отправляет если нужно.

    Args:
        update: Telegram update
        context: Bot context
        user_message: Текст сообщения пользователя
        mood: Настроение пользователя

    Returns:
        True если музыка отправлена, False если не запрашивалась
    """
    # Устанавливаем бота если ещё не установлен
    if not music_forwarder.bot:
        music_forwarder.set_bot(context.bot)

    # Определяем контекст для музыки
    topic_key = music_forwarder.detect_music_context(user_message, mood=mood)

    if not topic_key:
        return False

    # Пересылаем музыку (кэш загрузится автоматически внутри)
    success = await music_forwarder.forward_music(
        chat_id=update.effective_chat.id,
        topic_key=topic_key,
    )

    if not success:
        logger.warning(f"Failed to send music for topic: {topic_key}")
        return False

    # Отправляем подводку после трека
    suggestion = music_forwarder.get_topic_suggestion(topic_key)
    if suggestion:
        await update.message.reply_text(suggestion)

    logger.info(f"Sent music from {topic_key} to user {update.effective_user.id}")

    # Запускаем отложенный follow-up (30-60 сек)
    asyncio.create_task(_send_music_followup(context.bot, update.effective_chat.id))

    return True


async def _send_music_followup(bot, chat_id: int):
    """Отправляет follow-up сообщение через некоторое время после музыки."""
    # Ждём 30-60 секунд
    delay = random.randint(30, 60)
    await asyncio.sleep(delay)

    followups = [
        "Как тебе? Заходит? 🎵",
        "Ну как, нравится? 😊",
        "Подходит под настроение?",
        "Как тебе трек?",
    ]

    try:
        await bot.send_message(chat_id, random.choice(followups))
    except Exception as e:
        logger.debug(f"Failed to send music followup: {e}")


def detect_music_request(text: str) -> bool:
    """Проверяет, является ли текст запросом музыки."""
    text_lower = text.lower()

    music_keywords = [
        "музык", "песн", "трек", "мелоди", "послушать",
        "включи музыку", "поставь музыку", "хочу музыку",
        "да, включи", "хочу послушать",
    ]

    return any(kw in text_lower for kw in music_keywords)


def detect_music_preference(text: str) -> str | None:
    """
    Определяет предпочтение по жанру из текста.

    Returns:
        Ключ топика или None
    """
    text_lower = text.lower()

    # Явные указания жанра
    if any(w in text_lower for w in ["спокойн", "релакс", "расслаб", "тих"]):
        return "lounge"

    if any(w in text_lower for w in ["энергич", "бодр", "активн", "драйв"]):
        return "trance"

    if any(w in text_lower for w in ["рок", "тяжел", "громк"]):
        return "rock"

    if any(w in text_lower for w in ["попс", "весел", "танц", "поп"]):
        return "pop"

    if any(w in text_lower for w in ["романтик", "любов", "нежн"]):
        return "sexy"

    return None
