"""
Утилиты для имитации естественного диалога.
"""

import asyncio
from telegram import Update, Message, CallbackQuery
from typing import Union


async def send_with_typing(
    update_or_query: Union[Update, CallbackQuery],
    text: str,
    delay: float = 1.5,
    parse_mode: str = None,
) -> Message:
    """
    Отправить сообщение с имитацией печати.

    Args:
        update_or_query: Telegram Update или CallbackQuery объект
        text: Текст сообщения
        delay: Задержка в секундах перед отправкой (имитация печати)
        parse_mode: Режим форматирования (Markdown, HTML)

    Returns:
        Отправленное сообщение
    """
    # Определяем тип объекта
    if isinstance(update_or_query, CallbackQuery):
        chat = update_or_query.message.chat
        message = update_or_query.message
    else:
        chat = update_or_query.effective_chat
        message = update_or_query.message

    # Показываем индикатор "печатает..."
    await chat.send_action('typing')

    # Ждём указанное время
    await asyncio.sleep(delay)

    # Отправляем сообщение
    return await message.reply_text(text, parse_mode=parse_mode)


async def send_typing_only(update_or_query: Union[Update, CallbackQuery], delay: float = 1.5) -> None:
    """
    Показать индикатор "печатает..." без отправки сообщения.

    Args:
        update_or_query: Telegram Update или CallbackQuery объект
        delay: Длительность показа индикатора
    """
    # Определяем тип объекта
    if isinstance(update_or_query, CallbackQuery):
        chat = update_or_query.message.chat
    else:
        chat = update_or_query.effective_chat

    await chat.send_action('typing')
    await asyncio.sleep(delay)
