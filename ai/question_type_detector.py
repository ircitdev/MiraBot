"""
Детектор типа вопроса.
Определяет является ли вопрос закрытым, открытым или риторическим.
"""

from typing import Optional, Dict, Any
from loguru import logger


class QuestionTypeDetector:
    """Детектит тип вопроса пользователя."""

    # Маркеры закрытых вопросов (требуют да/нет ответа)
    CLOSED_QUESTION_PATTERNS = [
        "правда?", "да?", "нет?", "ведь?", "верно?",
        "так ли", "не так ли", "разве", "неужели",
        "может быть", "может",
        # Подтверждающие вопросы
        "правда ведь", "не правда ли",
        "согласна?", "понимаешь?",
    ]

    # Маркеры открытых вопросов (требуют развернутого ответа)
    OPEN_QUESTION_PATTERNS = [
        "что делать", "как быть", "как поступить",
        "что мне", "как мне", "почему",
        "зачем", "откуда", "куда",
        "как", "когда", "где",
        "что думаешь", "как думаешь",
        "что посоветуешь", "что скажешь",
    ]

    # Маркеры риторических вопросов (не требуют прямого ответа)
    RHETORICAL_PATTERNS = [
        "ну почему", "за что",
        "когда же", "сколько можно",
        "до каких пор", "что же мне",
        "что со мной", "что с ним",
        "ну как так", "как же так",
    ]

    # Эмоциональные состояния в вопросах
    EMOTIONAL_QUESTIONS = [
        "устала", "измучилась", "задолбало",
        "достало", "надоело", "замучилась",
    ]

    def detect(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Детектит тип вопроса в сообщении.

        Args:
            message: Сообщение пользователя

        Returns:
            Dict с типом вопроса и рекомендацией или None
        """
        message_lower = message.lower().strip()

        # Проверяем наличие вопросительного знака
        if "?" not in message:
            return None

        # Извлекаем последнее предложение с вопросом
        sentences = message_lower.split(".")
        question_sentence = ""
        for sentence in reversed(sentences):
            if "?" in sentence:
                question_sentence = sentence.strip()
                break

        if not question_sentence:
            return None

        # Проверяем риторический вопрос (приоритет!)
        if self._is_rhetorical(question_sentence):
            return {
                "type": "rhetorical",
                "question": question_sentence,
                "response_strategy": "validate_no_answer",
                "instruction": (
                    "Это риторический вопрос — НЕ отвечай на него прямо! "
                    "Вместо ответа — валидируй чувства: 'Да, это тяжело...', "
                    "'Понимаю твоё раздражение...'. Дай пространство выговориться."
                )
            }

        # Проверяем закрытый вопрос
        if self._is_closed(question_sentence):
            return {
                "type": "closed",
                "question": question_sentence,
                "response_strategy": "brief_then_reflect",
                "instruction": (
                    "Закрытый вопрос (да/нет). Ответь КРАТКО (1-2 предложения), "
                    "затем задай рефлексивный вопрос чтобы углубить разговор. "
                    "Пример: 'Да, понимаю. А что тебя больше всего беспокоит?'"
                )
            }

        # Проверяем открытый вопрос
        if self._is_open(question_sentence):
            return {
                "type": "open",
                "question": question_sentence,
                "response_strategy": "detailed_with_examples",
                "instruction": (
                    "Открытый вопрос — дай развёрнутый ответ. "
                    "Можешь использовать примеры, варианты, историю. "
                    "Но не перегружай — 3-4 абзаца max."
                )
            }

        # Если есть вопрос но тип неясен — считаем открытым
        return {
            "type": "open",
            "question": question_sentence,
            "response_strategy": "detailed_with_examples",
            "instruction": (
                "Вопрос (тип неясен, считаем открытым). "
                "Дай развёрнутый ответ с примерами."
            )
        }

    def _is_rhetorical(self, question: str) -> bool:
        """Проверяет является ли вопрос риторическим."""
        # Риторический вопрос часто начинается с эмоциональных слов
        for pattern in self.RHETORICAL_PATTERNS:
            if pattern in question:
                return True

        # Проверяем эмоциональные вопросы с "как", "почему"
        # Например: "Почему я такая дура?", "Как мне так везёт?"
        if any(emot in question for emot in self.EMOTIONAL_QUESTIONS):
            if any(word in question for word in ["почему", "как", "зачем"]):
                return True

        return False

    def _is_closed(self, question: str) -> bool:
        """Проверяет является ли вопрос закрытым (да/нет)."""
        for pattern in self.CLOSED_QUESTION_PATTERNS:
            if pattern in question:
                return True

        # Вопросы вида "Устала, правда?"
        if "," in question:
            parts = question.split(",")
            if len(parts) == 2:
                # Проверяем вторую часть
                if any(p in parts[1] for p in ["правда", "да", "нет", "ведь"]):
                    return True

        return False

    def _is_open(self, question: str) -> bool:
        """Проверяет является ли вопрос открытым."""
        for pattern in self.OPEN_QUESTION_PATTERNS:
            if question.startswith(pattern) or f" {pattern}" in question:
                return True

        return False


# Глобальный экземпляр
question_type_detector = QuestionTypeDetector()
