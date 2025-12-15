"""
Детектор негативных реакций на темы для создания триггеров.
"""

from typing import Optional, Dict, Any, List
from loguru import logger


class TriggerDetector:
    """Детектит когда пользователь негативно реагирует на тему."""

    # Маркеры негативной реакции
    NEGATIVE_REACTION_PATTERNS = [
        # Прямой отказ
        "не хочу об этом", "не буду говорить", "не готова обсуждать",
        "давай не будем", "лучше не будем", "можно не об этом",

        # Эмоциональная реакция
        "больно об этом", "тяжело говорить", "не могу об этом",
        "меня это ранит", "это задевает", "это триггерит",

        # Избегание
        "лучше сменим тему", "поговорим о другом", "не об этом сейчас",
    ]

    # Темы которые часто триггерят
    COMMON_SENSITIVE_TOPICS = {
        "свекровь": ["свекровь", "свекрови", "его мама", "его мать"],
        "развод": ["развод", "разводиться", "расстались", "разошлись"],
        "измена": ["изменил", "изменила", "измена", "предательство"],
        "родители": ["мои родители", "моя мама", "мой отец", "родители давят"],
        "здоровье": ["болезнь", "больна", "диагноз", "лечение"],
        "деньги": ["денег нет", "финансы", "долги", "кредит"],
        "работа": ["уволили", "начальник орет", "на работе кошмар"],
        "дети": ["с ребенком проблемы", "ребенок болеет"],
    }

    def detect_negative_reaction(
        self,
        user_message: str,
        previous_bot_message: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Детектит негативную реакцию пользователя на тему.

        Args:
            user_message: Сообщение пользователя
            previous_bot_message: Предыдущее сообщение бота (если есть)

        Returns:
            Dict с информацией о триггере или None
        """
        message_lower = user_message.lower()

        # Проверяем маркеры негативной реакции
        has_negative_reaction = any(
            pattern in message_lower for pattern in self.NEGATIVE_REACTION_PATTERNS
        )

        if not has_negative_reaction:
            return None

        # Пытаемся определить тему
        detected_topic = self._extract_topic(user_message, previous_bot_message)

        if not detected_topic:
            # Негативная реакция есть, но тему не распознали
            return {
                "has_negative_reaction": True,
                "topic": None,
                "severity": 5,
                "reason": "negative_reaction_without_topic"
            }

        logger.info(f"Detected negative reaction to topic: {detected_topic}")

        return {
            "has_negative_reaction": True,
            "topic": detected_topic,
            "severity": self._estimate_severity(message_lower),
            "reason": "user_expressed_discomfort"
        }

    def _extract_topic(
        self,
        user_message: str,
        previous_bot_message: Optional[str] = None
    ) -> Optional[str]:
        """
        Пытается извлечь тему из контекста.

        Args:
            user_message: Сообщение пользователя
            previous_bot_message: Предыдущее сообщение бота

        Returns:
            Название темы или None
        """
        message_lower = user_message.lower()

        # Проверяем известные темы
        for topic_name, keywords in self.COMMON_SENSITIVE_TOPICS.items():
            if any(keyword in message_lower for keyword in keywords):
                return topic_name

        # Проверяем в предыдущем сообщении бота (если есть)
        if previous_bot_message:
            bot_message_lower = previous_bot_message.lower()
            for topic_name, keywords in self.COMMON_SENSITIVE_TOPICS.items():
                if any(keyword in bot_message_lower for keyword in keywords):
                    return topic_name

        # Пытаемся извлечь тему из контекста
        # Паттерн: "не хочу об этом [тема]"
        if "об этом" in message_lower or "о том" in message_lower:
            # Извлекаем слова после "об этом" / "о том"
            for phrase in ["об этом", "о том"]:
                if phrase in message_lower:
                    idx = message_lower.index(phrase)
                    # Берем следующие слова
                    rest = user_message[idx + len(phrase):].strip()
                    words = rest.split()[:3]  # Первые 3 слова
                    if words:
                        return " ".join(words)

        return None

    def _estimate_severity(self, message_lower: str) -> int:
        """
        Оценивает степень чувствительности темы на основе эмоциональности сообщения.

        Returns:
            Степень от 1 до 10
        """
        high_severity_markers = [
            "больно", "не могу", "ранит", "очень тяжело", "триггерит"
        ]

        medium_severity_markers = [
            "не хочу", "не готова", "лучше не будем"
        ]

        if any(marker in message_lower for marker in high_severity_markers):
            return 8  # Высокая чувствительность
        elif any(marker in message_lower for marker in medium_severity_markers):
            return 6  # Средняя
        else:
            return 5  # По умолчанию

    def detect_topic_in_message(self, message: str) -> List[str]:
        """
        Детектит упоминания известных чувствительных тем в сообщении.

        Args:
            message: Текст сообщения

        Returns:
            Список обнаруженных тем
        """
        message_lower = message.lower()
        detected_topics = []

        for topic_name, keywords in self.COMMON_SENSITIVE_TOPICS.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_topics.append(topic_name)

        return detected_topics


# Глобальный экземпляр
trigger_detector = TriggerDetector()
