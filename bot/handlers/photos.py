"""
Photo handler.
Отправка фотографий по запросу с паузами.
"""

import asyncio
import random
from pathlib import Path
from typing import List

from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes
from loguru import logger


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


async def send_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Отправляет фотографии если пользователь просит.
    С паузами и сообщениями для естественности.
    """
    message_text = update.message.text.lower() if update.message.text else ""

    # Проверяем, просит ли пользователь фотографии
    photo_keywords = [
        "фото", "фотк", "фотограф", "картинк", "покажи себя",
        "как выглядишь", "твоё фото", "твое фото", "скинь фото",
        "пришли фото", "отправь фото", "покажи фото"
    ]

    if not any(kw in message_text for kw in photo_keywords):
        return False

    photos = get_all_photos()

    if not photos:
        await update.message.reply_text(
            "У меня пока нет фотографий, но я работаю над этим 💛"
        )
        return True

    # Перемешиваем фотографии
    random.shuffle(photos)
    first_batch = photos[:3]
    remaining = photos[3:]

    # 1. Первое сообщение - ищем
    await update.message.reply_text("Хм, сейчас поищу в архивах... 🔍")
    await asyncio.sleep(2)

    # 2. Показываем "печатает..."
    await update.message.chat.send_action("typing")
    await asyncio.sleep(1.5)

    # 3. Нашла!
    await update.message.reply_text("Кажется, что-то нашла! 📸")
    await asyncio.sleep(1)

    # 4. Отправляем первые 3 фотографии
    await update.message.chat.send_action("upload_photo")
    await asyncio.sleep(0.5)

    if len(first_batch) == 1:
        with open(first_batch[0], "rb") as photo:
            await update.message.reply_photo(photo)
    else:
        media_group = []
        for photo_path in first_batch:
            with open(photo_path, "rb") as f:
                media_group.append(InputMediaPhoto(f.read()))
        await update.message.reply_media_group(media_group)

    # 5. Если есть ещё фото - отправляем после паузы
    if remaining:
        await asyncio.sleep(2)
        await update.message.chat.send_action("typing")
        await asyncio.sleep(1)

        await update.message.reply_text(f"О, и ещё такие есть! 💛")
        await asyncio.sleep(1.5)

        # Отправляем оставшиеся фото
        await update.message.chat.send_action("upload_photo")
        await asyncio.sleep(0.5)

        if len(remaining) == 1:
            with open(remaining[0], "rb") as photo:
                await update.message.reply_photo(photo)
        else:
            media_group = []
            for photo_path in remaining:
                with open(photo_path, "rb") as f:
                    media_group.append(InputMediaPhoto(f.read()))
            await update.message.reply_media_group(media_group)

    logger.info(f"Sent {len(first_batch)} + {len(remaining)} photos")
    return True
