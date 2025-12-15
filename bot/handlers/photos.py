"""
Photo handler.
Отправка фотографий по запросу с отслеживанием отправленных.
Отправляет 1-2 фото за раз, не повторяется.
"""

import asyncio
import random
from pathlib import Path
from typing import List

from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from ai.prompts.mira_legend import (
    PHOTO_DESCRIPTIONS,
    PHOTO_LIST,
    TOTAL_PHOTOS,
    get_photo_story,
    get_all_photos_sent_message,
)


# Путь к папке с фотографиями
PHOTOS_DIR = Path(__file__).parent.parent.parent / "pic"


def get_all_photos() -> List[Path]:
    """Возвращает список всех фотографий в папке pic."""
    if not PHOTOS_DIR.exists():
        return []

    extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    photos = [
        f for f in PHOTOS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in extensions
    ]
    return sorted(photos)


async def send_photos(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: dict = None,
) -> bool:
    """
    Отправляет 1-2 фотографии если пользователь просит.
    Отслеживает какие фото уже отправлены конкретному пользователю.

    Args:
        update: Telegram update
        context: Bot context
        user_data: Данные пользователя из БД (содержит sent_photos)

    Returns:
        True если обработано, False если это не запрос фото
    """
    message_text = update.message.text.lower() if update.message.text else ""

    # Проверяем, просит ли пользователь фотографии
    photo_keywords = [
        "фото", "фотк", "фотограф", "картинк", "покажи себя",
        "как выглядишь", "твоё фото", "твое фото", "скинь фото",
        "пришли фото", "отправь фото", "покажи фото", "своё фото",
        "свое фото", "себя покажи", "как ты выглядишь", "увидеть тебя",
    ]

    if not any(kw in message_text for kw in photo_keywords):
        return False

    # Получаем список уже отправленных фото для этого пользователя
    sent_photos = []
    if user_data and user_data.get("sent_photos"):
        sent_photos = user_data.get("sent_photos", [])

    # Находим неотправленные фото
    unsent = [p for p in PHOTO_LIST if p not in sent_photos]

    # Если все фото уже отправлены
    if not unsent:
        await update.message.reply_text(get_all_photos_sent_message())
        return True

    # Фильтруем фото по контексту запроса (если есть ключевые слова)
    filtered_photos = unsent

    # Проверяем упоминание конкретных людей
    if "андре" in message_text or "муж" in message_text:
        # Ищем фото с мужем
        filtered_by_people = []
        for photo_id in unsent:
            photo_info = get_photo_story(photo_id)
            if photo_info and "people" in photo_info:
                people_lower = photo_info["people"].lower()
                if "андре" in people_lower or "муж" in people_lower:
                    filtered_by_people.append(photo_id)
        if filtered_by_people:
            filtered_photos = filtered_by_people
            logger.info(f"Filtered {len(filtered_by_people)} photos with husband")

    elif any(word in message_text for word in ["дет", "тим", "алис", "сын", "дочь", "ребен"]):
        # Ищем фото с детьми
        filtered_by_people = []
        for photo_id in unsent:
            photo_info = get_photo_story(photo_id)
            if photo_info and "people" in photo_info:
                people_lower = photo_info["people"].lower()
                if any(w in people_lower for w in ["тим", "алис", "дочь", "сын", "детьми", "ребен"]):
                    filtered_by_people.append(photo_id)
        if filtered_by_people:
            filtered_photos = filtered_by_people
            logger.info(f"Filtered {len(filtered_by_people)} photos with children")

    # Выбираем 1-2 фото для отправки
    num_to_send = min(random.choice([1, 1, 2]), len(filtered_photos))  # чаще 1, иногда 2
    photos_to_send = random.sample(filtered_photos, num_to_send)

    # Сообщаем сколько осталось
    remaining_after = len(unsent) - num_to_send

    # 1. Ищем в архивах
    search_messages = [
        "Сейчас поищу что-нибудь... 📱",
        "Хм, дай подумать какую показать... 🤔",
        "О, у меня есть кое-что! Секунду... 📸",
        "Сейчас, полистаю галерею... 🔍",
    ]
    await update.message.reply_text(random.choice(search_messages))
    await asyncio.sleep(random.uniform(1.5, 2.5))

    # 2. Показываем "печатает..."
    await update.message.chat.send_action("upload_photo")
    await asyncio.sleep(random.uniform(0.5, 1.0))

    # 3. Отправляем фото с историей
    new_sent = []

    for photo_id in photos_to_send:
        photo_info = get_photo_story(photo_id)
        photo_path = PHOTOS_DIR / photo_id

        if not photo_path.exists():
            logger.warning(f"Photo not found: {photo_path}")
            continue

        # Отправляем фото
        with open(photo_path, "rb") as photo:
            await update.message.reply_photo(
                photo,
                caption=f"📸 {photo_info['title']}" if photo_info else None
            )

        new_sent.append(photo_id)

        # Пауза между фото
        if len(photos_to_send) > 1 and photo_id != photos_to_send[-1]:
            await asyncio.sleep(random.uniform(1.0, 2.0))

    # 4. Рассказываем историю (для первого фото)
    if new_sent:
        first_photo_info = get_photo_story(new_sent[0])
        if first_photo_info:
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await update.message.chat.send_action("typing")
            await asyncio.sleep(random.uniform(1.0, 1.5))

            # История фото
            story = first_photo_info["story"].strip()
            await update.message.reply_text(story)

    # 5. Возвращаем информацию о новых отправленных фото
    # Это будет сохранено в user_data через message handler
    context.user_data["new_sent_photos"] = new_sent

    # Сохраняем контекст последнего фото для следующего сообщения
    # Это поможет Claude понять вопросы вроде "Сколько ему?" после фото
    if new_sent and first_photo_info:
        context.user_data["last_photo_context"] = {
            "photo_id": new_sent[0],
            "title": first_photo_info.get("title"),
            "story": first_photo_info.get("story"),
            "people": first_photo_info.get("people"),
            "mood": first_photo_info.get("mood"),
        }

    # Логируем
    logger.info(
        f"Sent {len(new_sent)} photos to user. "
        f"Total sent: {len(sent_photos) + len(new_sent)}/{TOTAL_PHOTOS}"
    )

    return True


async def get_photo_for_context(photo_id: str) -> dict | None:
    """
    Возвращает информацию о фото для использования в контексте AI.
    """
    return get_photo_story(photo_id)


def check_if_photo_request(text: str) -> bool:
    """Проверяет, является ли текст запросом фотографии."""
    text_lower = text.lower()
    photo_keywords = [
        "фото", "фотк", "картинк", "покажи себя",
        "как выглядишь", "скинь фото", "пришли фото",
        "отправь фото", "покажи фото", "своё фото",
        "свое фото", "увидеть тебя",
    ]
    return any(kw in text_lower for kw in photo_keywords)
