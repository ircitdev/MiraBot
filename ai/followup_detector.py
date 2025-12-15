"""
Детектор обещаний и планов пользователя для автоматических follow-ups.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from loguru import logger

from database.repositories.followup import FollowUpRepository


class FollowUpDetector:
    """Детектор обещаний, планов и намерений пользователя."""

    # Паттерны упоминания планов и намерений
    PLAN_PATTERNS = [
        # Прямые намерения
        "завтра", "сегодня вечером", "на этой неделе", "в выходные",
        "планирую", "собираюсь", "хочу", "надо", "нужно",

        # Обещания себе
        "попробую", "постараюсь", "сделаю", "скажу", "поговорю",

        # Конкретные действия
        "пойду", "позвоню", "напишу", "встречусь", "решу",
        "начну", "закончу", "сходу", "съезжу",
    ]

    # Категории действий
    ACTION_CATEGORIES = {
        "conversation": [
            "поговорю", "скажу", "объяснюсь", "признаюсь",
            "позвоню", "напишу", "встречусь", "обсужу",
        ],
        "task": [
            "сделаю", "закончу", "начну", "выполню",
            "подготовлю", "организую", "запланирую",
        ],
        "appointment": [
            "запись к", "прием", "консультация", "встреча",
            "пойду к врачу", "к психологу", "к специалисту",
        ],
        "decision": [
            "решу", "выберу", "определюсь", "приму решение",
            "подумаю", "взвешу", "решусь",
        ],
        "habit": [
            "начну делать", "перестану", "буду", "не буду",
            "каждый день", "регулярно", "по утрам",
        ],
    }

    # Индикаторы приоритета
    PRIORITY_INDICATORS = {
        "urgent": ["срочно", "критично", "немедленно", "сегодня обязательно", "прямо сейчас"],
        "high": ["важно", "очень нужно", "обязательно", "точно", "давно откладывала"],
        "low": ["может", "возможно", "если получится", "когда-нибудь", "подумаю"],
    }

    def __init__(self):
        self.followup_repo = FollowUpRepository()

    def detect_plan_mention(self, message: str) -> bool:
        """
        Детектит упоминание плана или намерения в сообщении.

        Args:
            message: Текст сообщения

        Returns:
            True если обнаружено упоминание плана
        """
        message_lower = message.lower()

        # Проверяем наличие паттернов
        has_pattern = any(pattern in message_lower for pattern in self.PLAN_PATTERNS)

        if not has_pattern:
            return False

        # Фильтруем вопросы и гипотетические ситуации
        if message_lower.startswith(("что если", "а если", "может ли", "стоит ли")):
            return False

        # Фильтруем отрицания прошлого
        if any(neg in message_lower for neg in ["не смогла", "не получилось", "не вышло"]):
            # Если есть "но" или "теперь" — это новый план
            if not any(conj in message_lower for conj in ["но", "теперь", "сейчас", "завтра"]):
                return False

        logger.debug(f"Detected potential plan mention in message: {message[:50]}...")
        return True

    def detect_category(self, action: str) -> str:
        """
        Определяет категорию действия.

        Args:
            action: Текст действия

        Returns:
            Название категории
        """
        action_lower = action.lower()

        for category, keywords in self.ACTION_CATEGORIES.items():
            if any(keyword in action_lower for keyword in keywords):
                return category

        return "other"

    def detect_priority(self, message: str, action: str) -> str:
        """
        Определяет приоритет действия.

        Args:
            message: Полное сообщение пользователя
            action: Извлеченное действие

        Returns:
            Приоритет: urgent/high/medium/low
        """
        full_text = f"{message} {action}".lower()

        for priority, indicators in self.PRIORITY_INDICATORS.items():
            if any(ind in full_text for ind in indicators):
                return priority

        # По умолчанию — medium
        return "medium"

    def extract_timeframe(self, message: str) -> Optional[datetime]:
        """
        Извлекает временные рамки из текста.

        Args:
            message: Текст сообщения

        Returns:
            Дата когда планировалось выполнить или None
        """
        message_lower = message.lower()
        now = datetime.utcnow()

        # Сегодня
        if "сегодня" in message_lower:
            return now

        # Завтра
        if "завтра" in message_lower:
            return now + timedelta(days=1)

        # Через N дней
        if "через" in message_lower:
            words = message_lower.split()
            for i, word in enumerate(words):
                if word == "через" and i + 1 < len(words):
                    next_word = words[i + 1]
                    if next_word.isdigit():
                        days = int(next_word)
                        return now + timedelta(days=days)

        # На этой неделе
        if "на этой неделе" in message_lower or "на неделе" in message_lower:
            return now + timedelta(days=3)  # Примерно середина недели

        # В выходные
        if "в выходные" in message_lower or "в субботу" in message_lower or "в воскресенье" in message_lower:
            days_until_weekend = (5 - now.weekday()) % 7
            if days_until_weekend == 0:
                days_until_weekend = 7
            return now + timedelta(days=days_until_weekend)

        # Следующая неделя
        if "на следующей неделе" in message_lower:
            return now + timedelta(weeks=1)

        # По умолчанию — завтра
        return now + timedelta(days=1)

    def calculate_followup_date(
        self,
        scheduled_date: Optional[datetime],
        priority: str,
    ) -> datetime:
        """
        Рассчитывает когда спросить "Как прошло?".

        Args:
            scheduled_date: Когда планировалось выполнить
            priority: Приоритет действия

        Returns:
            Дата для follow-up вопроса
        """
        if not scheduled_date:
            scheduled_date = datetime.utcnow() + timedelta(days=1)

        # Для urgent — через несколько часов после
        if priority == "urgent":
            return scheduled_date + timedelta(hours=6)

        # Для high — на следующий день
        if priority == "high":
            return scheduled_date + timedelta(days=1)

        # Для medium — через 2 дня
        if priority == "medium":
            return scheduled_date + timedelta(days=2)

        # Для low — через неделю
        return scheduled_date + timedelta(weeks=1)

    async def create_followup_from_message(
        self,
        user_id: int,
        message: str,
        action: str,
        context: Optional[str] = None,
        message_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Создает follow-up на основе сообщения пользователя.

        Args:
            user_id: ID пользователя
            message: Полное сообщение
            action: Извлеченное действие
            context: Контекст (почему важно)
            message_id: ID сообщения

        Returns:
            ID созданного follow-up или None
        """
        try:
            # Определяем параметры
            category = self.detect_category(action)
            priority = self.detect_priority(message, action)
            scheduled_date = self.extract_timeframe(message)
            followup_date = self.calculate_followup_date(scheduled_date, priority)

            # Создаем follow-up
            followup = await self.followup_repo.create(
                user_id=user_id,
                action=action,
                followup_date=followup_date,
                context=context,
                category=category,
                scheduled_date=scheduled_date,
                priority=priority,
                message_id=message_id,
            )

            logger.info(
                f"Created follow-up {followup.id} for user {user_id}: "
                f"'{action[:50]}...' (priority: {priority}, followup: {followup_date.date()})"
            )
            return followup.id

        except Exception as e:
            logger.error(f"Error creating follow-up for user {user_id}: {e}")
            return None


# Глобальный экземпляр
followup_detector = FollowUpDetector()
