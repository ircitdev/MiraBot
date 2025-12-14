"""
Sticker Sender Service.
Отправляет стикеры из пака MiraDrug в зависимости от контекста/эмоций.
"""

import random
import asyncio
from typing import Optional, Dict, List, Any
from telegram import Bot
from telegram.error import TelegramError
from loguru import logger
import httpx

from config.settings import settings

# Имя стикерпака
STICKER_PACK_NAME = "MiraDrug"

# Маппинг эмоций на индексы стикеров (0-based)
# 1. 🤩 - Восторг
# 2. 👍 - Одобрение
# 3. 😍 - Влюблённость
# 4. 😭 - Грусть/плач
# 5. 😤 - Злость
# 6. 🤔 - Задумчивость
# 7. 😘 - Поцелуй
# 8. 🥳 - Праздник

EMOTION_STICKERS = {
    "excited": 0,      # 🤩 Восторг
    "approval": 1,     # 👍 Одобрение
    "love": 2,         # 😍 Влюблённость
    "sad": 3,          # 😭 Грусть
    "angry": 4,        # 😤 Злость
    "thinking": 5,     # 🤔 Задумчивость
    "kiss": 6,         # 😘 Поцелуй
    "party": 7,        # 🥳 Праздник
}

# Контексты для определения эмоций
EMOTION_CONTEXTS = {
    "excited": {
        "keywords": ["круто", "офигеть", "вау", "ура", "класс", "супер", "потрясающе", "невероятно", "amazing"],
        "moods": ["excited", "amazed"],
    },
    "approval": {
        "keywords": ["молодец", "правильно", "согласна", "верно", "точно", "хорошо", "отлично", "да!"],
        "moods": ["supportive", "agreeing"],
    },
    "love": {
        "keywords": ["люблю", "обожаю", "нравишься", "милый", "милая", "красивый", "красивая", "прекрасн"],
        "moods": ["loving", "affectionate"],
    },
    "sad": {
        "keywords": ["грустно", "печально", "плачу", "слёзы", "тоска", "одинок", "больно", "плохо"],
        "moods": ["sad", "crying", "depressed"],
    },
    "angry": {
        "keywords": ["злюсь", "бесит", "ненавижу", "достал", "раздражает", "злость", "ярость"],
        "moods": ["angry", "frustrated", "irritated"],
    },
    "thinking": {
        "keywords": ["думаю", "размышляю", "не знаю", "может быть", "возможно", "хм", "интересно"],
        "moods": ["thinking", "contemplating", "uncertain"],
    },
    "kiss": {
        "keywords": ["целую", "поцелуй", "чмок", "обнимаю", "скучаю по тебе", "хочу к тебе"],
        "moods": ["romantic", "affectionate", "missing"],
    },
    "party": {
        "keywords": ["праздник", "день рождения", "поздравляю", "отмечаем", "вечеринка", "гуляем"],
        "moods": ["celebrating", "happy", "festive"],
    },
}

# Кэш стикеров (file_id)
_sticker_cache: List[str] = []
_cache_loaded = False


class StickerSender:
    """Сервис отправки стикеров."""

    def __init__(self, bot: Bot = None):
        self.bot = bot
        self.pack_name = STICKER_PACK_NAME

    def set_bot(self, bot: Bot):
        """Устанавливает экземпляр бота."""
        self.bot = bot

    async def load_sticker_pack(self) -> bool:
        """Загружает стикерпак и кэширует file_id."""
        global _sticker_cache, _cache_loaded

        if _cache_loaded and _sticker_cache:
            return True

        try:
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getStickerSet"

            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json={"name": self.pack_name})
                data = resp.json()

            if data.get("ok"):
                stickers = data["result"]["stickers"]
                _sticker_cache = [s["file_id"] for s in stickers]
                _cache_loaded = True
                logger.info(f"Loaded {len(_sticker_cache)} stickers from {self.pack_name}")
                return True
            else:
                logger.error(f"Failed to load sticker pack: {data}")
                return False

        except Exception as e:
            logger.error(f"Error loading sticker pack: {e}")
            return False

    def detect_emotion(
        self,
        text: str,
        mood: Optional[str] = None,
        mira_response: Optional[str] = None,
    ) -> Optional[str]:
        """
        Определяет эмоцию на основе текста и контекста.

        Args:
            text: Текст сообщения пользователя
            mood: Настроение пользователя
            mira_response: Ответ Миры (для определения её эмоции)

        Returns:
            Ключ эмоции или None
        """
        # Анализируем ответ Миры если есть
        check_text = mira_response.lower() if mira_response else text.lower()

        for emotion, config in EMOTION_CONTEXTS.items():
            # Проверяем ключевые слова
            for keyword in config["keywords"]:
                if keyword in check_text:
                    return emotion

            # Проверяем настроение
            if mood and mood in config["moods"]:
                return emotion

        return None

    def should_send_sticker(self, emotion: str, probability: float = 0.3) -> bool:
        """
        Определяет, нужно ли отправить стикер (с вероятностью).

        Args:
            emotion: Определённая эмоция
            probability: Вероятность отправки (0.0-1.0)

        Returns:
            True если нужно отправить стикер
        """
        return random.random() < probability

    async def send_sticker(
        self,
        chat_id: int,
        emotion: str,
    ) -> bool:
        """
        Отправляет стикер пользователю.

        Args:
            chat_id: ID чата
            emotion: Ключ эмоции

        Returns:
            True если успешно
        """
        if not self.bot:
            logger.error("Bot not set in StickerSender")
            return False

        # Загружаем стикеры если не загружены
        if not _sticker_cache:
            await self.load_sticker_pack()

        if not _sticker_cache:
            logger.warning("No stickers in cache")
            return False

        # Получаем индекс стикера
        sticker_index = EMOTION_STICKERS.get(emotion)
        if sticker_index is None or sticker_index >= len(_sticker_cache):
            logger.warning(f"Unknown emotion or invalid index: {emotion}")
            return False

        file_id = _sticker_cache[sticker_index]

        try:
            await self.bot.send_sticker(chat_id=chat_id, sticker=file_id)
            logger.info(f"Sent sticker '{emotion}' to chat {chat_id}")
            return True

        except TelegramError as e:
            logger.error(f"Failed to send sticker: {e}")
            return False

    async def send_random_sticker(self, chat_id: int) -> bool:
        """Отправляет случайный стикер."""
        if not _sticker_cache:
            await self.load_sticker_pack()

        if not _sticker_cache:
            return False

        file_id = random.choice(_sticker_cache)

        try:
            await self.bot.send_sticker(chat_id=chat_id, sticker=file_id)
            return True
        except TelegramError as e:
            logger.error(f"Failed to send random sticker: {e}")
            return False

    def get_sticker_for_response(
        self,
        mira_response: str,
        user_message: str = "",
        mood: str = None,
    ) -> Optional[str]:
        """
        Определяет какой стикер подходит к ответу Миры.

        Returns:
            Ключ эмоции или None если стикер не нужен
        """
        # Сначала проверяем ответ Миры
        emotion = self.detect_emotion(
            text=user_message,
            mood=mood,
            mira_response=mira_response
        )

        if emotion and self.should_send_sticker(emotion, probability=0.25):
            return emotion

        return None


# Глобальный экземпляр
sticker_sender = StickerSender()


async def maybe_send_sticker(
    bot: Bot,
    chat_id: int,
    mira_response: str,
    user_message: str = "",
    mood: str = None,
) -> bool:
    """
    Вспомогательная функция для отправки стикера если уместно.

    Returns:
        True если стикер был отправлен
    """
    sticker_sender.set_bot(bot)

    emotion = sticker_sender.get_sticker_for_response(
        mira_response=mira_response,
        user_message=user_message,
        mood=mood
    )

    if emotion:
        return await sticker_sender.send_sticker(chat_id, emotion)

    return False
