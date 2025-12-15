"""
Детектор попыток решения проблем.
Определяет когда пользователь упоминает что уже пытался что-то сделать.
"""

from typing import Optional, Dict, Any
from loguru import logger


class AttemptDetector:
    """Детектит упоминания о попытках решения проблем."""

    # Паттерны упоминания попыток
    ATTEMPT_PATTERNS = [
        # Прямые упоминания попыток
        "пыталась",
        "пытался",
        "пробовала",
        "пробовал",
        "делала",
        "делал",
        "попробовала",
        "попробовал",

        # Результаты попыток
        "не помогло",
        "не сработало",
        "не получилось",
        "бесполезно",
        "напрасно",
        "зря",

        # Уже делал/делаю
        "уже делаю",
        "уже пыталась",
        "уже пробовала",
        "делала это",
        "пробовала это",

        # Негативные результаты
        "стало хуже",
        "не вышло",
        "провалилось",
    ]

    # Техники/решения для детекции
    COMMON_SOLUTIONS = {
        # Психологические техники
        "meditation": [
            "медитация", "медитировать", "медитации", "медитацию",
            "медитировала", "медитировать"
        ],
        "breathing": [
            "дыхание", "дышать", "дыхательные", "дышала",
            "вдох", "выдох", "дыхательное упражнение"
        ],
        "therapy": [
            "психолог", "терапия", "терапевт", "к психологу",
            "на терапию", "консультация"
        ],
        "journaling": [
            "дневник", "записывать", "писать", "письменные практики",
            "вести дневник"
        ],

        # Физическая активность
        "sport": [
            "спорт", "зал", "тренировки", "бегать", "фитнес",
            "йога", "физические упражнения"
        ],
        "walking": [
            "гулять", "прогулки", "ходить", "гуляла"
        ],

        # Социальные действия
        "talk_husband": [
            "говорила с мужем", "разговор с мужем", "сказала мужу",
            "поговорила", "обсудила с мужем"
        ],
        "talk_friends": [
            "говорила с подругой", "подруге сказала", "друзьям рассказала",
            "поговорила с подругой"
        ],

        # Изменение поведения
        "boundaries": [
            "границы", "отказывать", "сказать нет", "отказала",
            "установить границы"
        ],
        "time_for_self": [
            "время для себя", "побыть одной", "уединение"
        ],

        # Медицинские
        "medication": [
            "лекарства", "таблетки", "антидепрессанты", "препараты"
        ],
        "doctor": [
            "к врачу", "доктор", "обследование", "анализы"
        ],
    }

    def detect(
        self,
        user_message: str,
        assistant_response: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Детектит упоминание попытки решения в сообщении пользователя.

        Args:
            user_message: Сообщение пользователя
            assistant_response: Ответ ассистента (опционально)

        Returns:
            Dict с информацией о попытке или None
        """
        message_lower = user_message.lower()

        # Проверяем наличие паттернов попыток
        has_attempt_pattern = any(
            pattern in message_lower for pattern in self.ATTEMPT_PATTERNS
        )

        if not has_attempt_pattern:
            return None

        # Ищем упомянутое решение
        detected_solutions = []
        for solution_type, keywords in self.COMMON_SOLUTIONS.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_solutions.append(solution_type)

        if not detected_solutions:
            # Попытка упомянута, но решение не распознано
            # Сохраним общее упоминание
            return {
                "solution_type": "unknown",
                "solution_name": self._extract_solution_from_context(user_message),
                "result": self._extract_result(message_lower),
                "importance": 8,  # Высокая важность
            }

        # Если решение распознано
        result_info = {
            "solution_type": detected_solutions[0],  # Первое распознанное
            "solution_name": self._get_solution_name(detected_solutions[0]),
            "result": self._extract_result(message_lower),
            "importance": 8,
        }

        logger.info(
            f"Detected attempt: {result_info['solution_name']} - {result_info['result']}"
        )

        return result_info

    def _extract_result(self, message_lower: str) -> str:
        """Определяет результат попытки (negative/neutral/positive)."""
        negative_markers = [
            "не помогло", "не сработало", "не получилось",
            "бесполезно", "стало хуже", "не вышло"
        ]

        neutral_markers = [
            "иногда помогает", "немного помогло", "чуть легче"
        ]

        positive_markers = [
            "помогло", "стало легче", "получилось", "сработало"
        ]

        if any(marker in message_lower for marker in negative_markers):
            return "negative"
        elif any(marker in message_lower for marker in positive_markers):
            return "positive"
        elif any(marker in message_lower for marker in neutral_markers):
            return "neutral"
        else:
            return "unknown"

    def _get_solution_name(self, solution_type: str) -> str:
        """Возвращает читаемое название решения."""
        names = {
            "meditation": "медитация",
            "breathing": "дыхательные упражнения",
            "therapy": "психолог/терапия",
            "journaling": "дневник",
            "sport": "спорт/тренировки",
            "walking": "прогулки",
            "talk_husband": "разговор с мужем",
            "talk_friends": "разговор с подругой",
            "boundaries": "установление границ",
            "time_for_self": "время для себя",
            "medication": "лекарства",
            "doctor": "врач/обследование",
        }
        return names.get(solution_type, solution_type)

    def _extract_solution_from_context(self, message: str) -> str:
        """
        Пытается извлечь упомянутое решение из контекста
        если не распознано по ключевым словам.
        """
        # Простой подход: берём первые 50 символов упоминания
        # В будущем можно улучшить через NER
        message_lower = message.lower()

        for pattern in self.ATTEMPT_PATTERNS:
            if pattern in message_lower:
                # Находим позицию паттерна
                idx = message_lower.index(pattern)
                # Берём контекст (20 символов до и после)
                start = max(0, idx - 20)
                end = min(len(message), idx + len(pattern) + 30)
                context = message[start:end].strip()
                return context

        return "неизвестное решение"


# Глобальный экземпляр
attempt_detector = AttemptDetector()
