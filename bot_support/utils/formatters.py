"""
Formatters для бота поддержки.
Форматирование карточек пользователей и сообщений.
"""

from datetime import datetime
from typing import Optional
from database.models import SupportUser


def format_user_card(user: SupportUser) -> str:
    """
    Форматирует карточку пользователя для отправки в топик поддержки.

    Args:
        user: Объект SupportUser

    Returns:
        str: Отформатированная карточка пользователя
    """
    # Формируем имя
    full_name = user.first_name
    if user.last_name:
        full_name += f" {user.last_name}"

    # Формируем username
    username_line = ""
    if user.username:
        username_line = f"\n📱 Username: @{user.username}"

    # Формируем ссылку на профиль (tg://user?id=)
    profile_link = f"tg://user?id={user.telegram_id}"

    # Формируем дату
    created_date = user.created_at.strftime("%d.%m.%Y %H:%M")

    card = f"""🆕 Новый пользователь

👤 Имя: {full_name}
🆔 ID: {user.telegram_id}
🔗 Профиль: {profile_link}{username_line}

⏰ Первое обращение: {created_date}"""

    return card


def format_date(dt: datetime) -> str:
    """
    Форматирует дату для отображения.

    Args:
        dt: Объект datetime

    Returns:
        str: Отформатированная дата (DD.MM.YYYY HH:MM)
    """
    return dt.strftime("%d.%m.%Y %H:%M")


def format_time(dt: datetime) -> str:
    """
    Форматирует время для отображения.

    Args:
        dt: Объект datetime

    Returns:
        str: Отформатированное время (HH:MM)
    """
    return dt.strftime("%H:%M")


def format_support_reply(text: str) -> str:
    """
    Форматирует ответ админа для пользователя.

    Args:
        text: Текст ответа

    Returns:
        str: Отформатированный текст
    """
    # Пока просто возвращаем текст как есть
    # В будущем можно добавить форматирование (эмодзи, подпись и т.д.)
    return text


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Обрезает текст до указанной длины с добавлением многоточия.

    Args:
        text: Исходный текст
        max_length: Максимальная длина

    Returns:
        str: Обрезанный текст
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_message_preview(text: Optional[str], media_type: str) -> str:
    """
    Форматирует превью сообщения для списка обращений.

    Args:
        text: Текст сообщения
        media_type: Тип медиа (text, photo, video, etc.)

    Returns:
        str: Отформатированное превью
    """
    if media_type == "photo":
        preview = "📷 Фото"
        if text:
            preview += f": {truncate_text(text, 50)}"
    elif media_type == "video":
        preview = "🎥 Видео"
        if text:
            preview += f": {truncate_text(text, 50)}"
    elif media_type == "voice":
        preview = "🎤 Голосовое сообщение"
    elif media_type == "video_note":
        preview = "📹 Видеосообщение"
    elif media_type == "document":
        preview = "📄 Документ"
        if text:
            preview += f": {truncate_text(text, 50)}"
    elif media_type == "sticker":
        preview = "🎭 Стикер"
    else:
        # text
        preview = truncate_text(text, 100) if text else "Сообщение"

    return preview
