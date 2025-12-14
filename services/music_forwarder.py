"""
Music Forwarder Service.
Пересылает музыку из супергруппы с топиками в зависимости от контекста разговора.

Как заполнить кэш:
1. Добавить бота в супергруппу с правами чтения
2. Бот автоматически кэширует аудио из топиков
3. Либо вручную вызвать populate_message_cache()
"""

import random
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from telegram import Bot, Update, Message
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from loguru import logger

# ID супергруппы (без -100 префикса, он добавляется автоматически)
# https://t.me/c/3502484471 -> chat_id = -1003502484471
MUSIC_SUPERGROUP_ID = -1003502484471

# Путь к файлу кэша
CACHE_FILE = Path(__file__).parent.parent / "data" / "music_cache.json"

# Маппинг топиков на их ID и контекст
MUSIC_TOPICS = {
    "trance": {
        "thread_id": 11,
        "name": "Trance",
        "contexts": ["энергия", "мотивация", "спорт", "работа", "концентрация", "драйв"],
        "moods": ["energetic", "motivated", "focused"],
        "emoji": "🎧"
    },
    "lounge": {
        "thread_id": 3,
        "name": "Lounge",
        "contexts": ["отдых", "релакс", "спокойствие", "вечер", "расслабление", "медитация"],
        "moods": ["calm", "relaxed", "tired"],
        "emoji": "🌙"
    },
    "rock": {
        "thread_id": 9,
        "name": "Rock",
        "contexts": ["злость", "протест", "сила", "бунт", "агрессия", "буря"],
        "moods": ["angry", "frustrated", "rebellious"],
        "emoji": "🎸"
    },
    "pop": {
        "thread_id": 5,
        "name": "Pop",
        "contexts": ["веселье", "праздник", "танцы", "радость", "вечеринка", "хорошее настроение"],
        "moods": ["happy", "joyful", "excited"],
        "emoji": "🎤"
    },
    "sex": {
        "thread_id": 25,
        "name": "Sex",
        "contexts": ["романтика", "близость", "страсть", "любовь", "интим", "свидание"],
        "moods": ["romantic", "passionate", "sensual"],
        "emoji": "💋"
    },
    "hits": {
        "thread_id": 7,
        "name": "Hits",
        "contexts": ["популярное", "хиты", "известные", "топ"],
        "moods": ["neutral", "any"],
        "emoji": "⭐"
    },
}

# Кэш сообщений из топиков (message_id -> topic)
_message_cache: Dict[str, List[int]] = {}
_cache_loaded = False


class MusicForwarder:
    """Сервис пересылки музыки из супергруппы."""

    def __init__(self, bot: Bot = None):
        self.bot = bot
        self.supergroup_id = MUSIC_SUPERGROUP_ID

    def set_bot(self, bot: Bot):
        """Устанавливает экземпляр бота."""
        self.bot = bot

    def detect_music_context(
        self,
        message_text: str,
        mood: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Определяет какой жанр музыки подходит под контекст.

        Args:
            message_text: Текст сообщения пользователя
            mood: Настроение пользователя (из mood_analyzer)
            tags: Теги разговора

        Returns:
            Ключ топика или None если музыка не уместна
        """
        text_lower = message_text.lower()

        # Проверяем явный запрос музыки
        music_keywords = [
            "музык", "песн", "трек", "мелоди", "послушать",
            "включи", "поставь", "что послушать", "посоветуй музыку",
        ]

        is_music_request = any(kw in text_lower for kw in music_keywords)

        if not is_music_request:
            return None

        # Определяем жанр по контексту
        for topic_key, topic_info in MUSIC_TOPICS.items():
            # Проверяем по ключевым словам контекста
            for context_word in topic_info["contexts"]:
                if context_word in text_lower:
                    return topic_key

            # Проверяем по настроению
            if mood and mood in topic_info["moods"]:
                return topic_key

        # Дополнительные эвристики по тексту
        if any(word in text_lower for word in ["грустн", "тоск", "печал", "плач"]):
            return "lounge"  # Спокойная музыка для грусти

        if any(word in text_lower for word in ["злюсь", "бесит", "достал", "ненавиж"]):
            return "rock"

        if any(word in text_lower for word in ["радост", "счастлив", "весел", "класс"]):
            return "pop"

        if any(word in text_lower for word in ["устал", "отдохн", "расслаб", "спать"]):
            return "lounge"

        if any(word in text_lower for word in ["работ", "сосредоточ", "фокус", "дела"]):
            return "trance"

        if any(word in text_lower for word in ["романтик", "любовь", "свидани", "муж", "близост"]):
            return "sexy"

        # По умолчанию — хиты
        return "hits"

    async def get_random_track_from_topic(self, topic_key: str) -> Optional[int]:
        """
        Получает случайный message_id трека из топика.

        Note: Telegram Bot API не позволяет получить историю сообщений группы.
        Нужно либо кэшировать при добавлении, либо использовать userbot/MTProto.

        Пока используем заранее известные message_id.
        """
        global _message_cache, _cache_loaded

        if topic_key not in MUSIC_TOPICS:
            return None

        # Если кэш не загружен — загружаем из конфига
        if not _cache_loaded:
            await self._load_message_cache()

        topic_messages = _message_cache.get(topic_key, [])

        if not topic_messages:
            logger.warning(f"No cached messages for topic: {topic_key}")
            return None

        return random.choice(topic_messages)

    async def _load_message_cache(self):
        """
        Загружает кэш сообщений из файла.
        """
        global _message_cache, _cache_loaded

        # Инициализируем базовую структуру
        base_cache = {
            "trance": [],
            "lounge": [],
            "rock": [],
            "pop": [],
            "sex": [],
            "hits": [],
        }

        # Пробуем загрузить из файла
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r") as f:
                    loaded = json.load(f)
                # Мержим загруженные данные с базовой структурой
                for key in base_cache:
                    if key in loaded:
                        base_cache[key] = loaded[key]
                _message_cache = base_cache
                total = sum(len(v) for v in _message_cache.values())
                logger.info(f"Music cache loaded from file: {total} tracks")
                _cache_loaded = True
                return
            except Exception as e:
                logger.error(f"Failed to load music cache: {e}")

        _message_cache = base_cache
        _cache_loaded = True
        logger.info("Music cache initialized (empty)")

    def _save_cache(self):
        """Сохраняет кэш в файл."""
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w") as f:
                json.dump(_message_cache, f)
            logger.debug("Music cache saved to file")
        except Exception as e:
            logger.error(f"Failed to save music cache: {e}")

    async def forward_music(
        self,
        chat_id: int,
        topic_key: str,
        message_id: Optional[int] = None,
    ) -> bool:
        """
        Пересылает музыку пользователю.

        Args:
            chat_id: ID чата пользователя
            topic_key: Ключ топика (trance, lounge, etc.)
            message_id: Конкретный message_id или None для случайного

        Returns:
            True если успешно
        """
        if not self.bot:
            logger.error("Bot not set in MusicForwarder")
            return False

        topic_info = MUSIC_TOPICS.get(topic_key)
        if not topic_info:
            logger.error(f"Unknown topic: {topic_key}")
            return False

        # Получаем message_id если не указан
        if message_id is None:
            message_id = await self.get_random_track_from_topic(topic_key)

        if message_id is None:
            logger.warning(f"No message to forward for topic: {topic_key}")
            return False

        try:
            # Пересылаем сообщение
            await self.bot.forward_message(
                chat_id=chat_id,
                from_chat_id=self.supergroup_id,
                message_id=message_id,
                message_thread_id=topic_info["thread_id"],
            )

            logger.info(f"Forwarded music from {topic_key} to chat {chat_id}")
            return True

        except TelegramError as e:
            logger.error(f"Failed to forward music: {e}")
            return False

    async def copy_music(
        self,
        chat_id: int,
        topic_key: str,
        message_id: int,
        caption: Optional[str] = None,
    ) -> bool:
        """
        Копирует музыку пользователю (без указания источника).

        Args:
            chat_id: ID чата пользователя
            topic_key: Ключ топика
            message_id: ID сообщения для копирования
            caption: Новый caption (опционально)

        Returns:
            True если успешно
        """
        if not self.bot:
            logger.error("Bot not set in MusicForwarder")
            return False

        topic_info = MUSIC_TOPICS.get(topic_key)
        if not topic_info:
            return False

        try:
            await self.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=self.supergroup_id,
                message_id=message_id,
                caption=caption,
            )

            logger.info(f"Copied music from {topic_key} to chat {chat_id}")
            return True

        except TelegramError as e:
            logger.error(f"Failed to copy music: {e}")
            return False

    def get_topic_suggestion(self, topic_key: str) -> str:
        """Возвращает текст с предложением музыки."""
        topic_info = MUSIC_TOPICS.get(topic_key)
        if not topic_info:
            return ""

        suggestions = {
            "trance": [
                "Держи заряд энергии! 🎧",
                "Для концентрации и драйва:",
                "Музыка для продуктивности:",
            ],
            "lounge": [
                "Для расслабления и отдыха 🌙",
                "Спокойная музыка для тебя:",
                "Чтобы расслабиться:",
            ],
            "rock": [
                "Выпусти пар! 🎸",
                "Для тех, кто злится:",
                "Рок для настроения:",
            ],
            "pop": [
                "Позитив для тебя! 🎤",
                "Чтобы поднять настроение:",
                "Для хорошего настроения:",
            ],
            "sexy": [
                "Для романтического настроения 💋",
                "Музыка для двоих:",
                "Создать атмосферу:",
            ],
            "hits": [
                "Что-то популярное для тебя ⭐",
                "Актуальный хит:",
                "Послушай:",
            ],
        }

        topic_suggestions = suggestions.get(topic_key, ["Держи музыку:"])
        return random.choice(topic_suggestions)


# Глобальный экземпляр
music_forwarder = MusicForwarder()


def populate_message_cache(topic_key: str, message_ids: List[int]):
    """
    Заполняет кэш сообщений для топика.
    Вызывать при старте бота или при обновлении.

    Args:
        topic_key: Ключ топика
        message_ids: Список message_id из этого топика
    """
    global _message_cache, _cache_loaded
    _message_cache[topic_key] = message_ids
    _cache_loaded = True
    music_forwarder._save_cache()
    logger.info(f"Populated cache for {topic_key}: {len(message_ids)} messages")


def get_topic_by_thread_id(thread_id: int) -> Optional[str]:
    """Возвращает ключ топика по thread_id."""
    for topic_key, topic_info in MUSIC_TOPICS.items():
        if topic_info["thread_id"] == thread_id:
            return topic_key
    return None


async def handle_supergroup_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler для сообщений в супергруппе с музыкой.
    Кэширует audio/voice сообщения из топиков.

    Добавить в main.py:
    from services.music_forwarder import handle_supergroup_message, MUSIC_SUPERGROUP_ID
    application.add_handler(MessageHandler(
        filters.Chat(MUSIC_SUPERGROUP_ID) & (filters.AUDIO | filters.VOICE | filters.VIDEO),
        handle_supergroup_message
    ))
    """
    global _message_cache

    message = update.message
    if not message:
        return

    # Проверяем что это сообщение из нашей группы
    if message.chat_id != MUSIC_SUPERGROUP_ID:
        return

    # Получаем thread_id (топик)
    thread_id = message.message_thread_id
    if not thread_id:
        return

    # Определяем топик
    topic_key = get_topic_by_thread_id(thread_id)
    if not topic_key:
        return

    # Проверяем что это аудио/видео
    if not (message.audio or message.voice or message.video):
        return

    # Добавляем в кэш если ещё нет
    if topic_key not in _message_cache:
        _message_cache[topic_key] = []

    if message.message_id not in _message_cache[topic_key]:
        _message_cache[topic_key].append(message.message_id)
        music_forwarder._save_cache()
        logger.info(f"Cached music message {message.message_id} in {topic_key}")


def get_cache_stats() -> Dict[str, int]:
    """Возвращает статистику кэша."""
    return {topic: len(ids) for topic, ids in _message_cache.items()}
