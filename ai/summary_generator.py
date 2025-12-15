"""
Генератор персонализированных сводок прогресса для пользователей.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from loguru import logger

from database.repositories.mood import MoodRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.memory import MemoryRepository
from ai.claude_client import ClaudeClient


class SummaryGenerator:
    """Генерирует персонализированные сводки о прогрессе пользователя."""

    def __init__(self):
        self.mood_repo = MoodRepository()
        self.conversation_repo = ConversationRepository()
        self.memory_repo = MemoryRepository()
        self.claude_client = ClaudeClient()

    async def generate_biweekly_summary(
        self,
        user_id: int,
        period_days: int = 14,
    ) -> Optional[str]:
        """
        Генерирует сводку за последние N дней (по умолчанию 14 - две недели).

        Args:
            user_id: ID пользователя
            period_days: Период в днях

        Returns:
            Текст сводки или None если недостаточно данных
        """
        try:
            # Собираем данные за период
            summary_data = await self._collect_period_data(user_id, period_days)

            if not summary_data["has_sufficient_data"]:
                logger.info(f"Insufficient data for user {user_id} summary")
                return None

            # Генерируем сводку через Claude
            summary_text = await self._generate_summary_text(user_id, summary_data)

            logger.info(f"Generated bi-weekly summary for user {user_id}")
            return summary_text

        except Exception as e:
            logger.error(f"Error generating summary for user {user_id}: {e}")
            return None

    async def _collect_period_data(
        self,
        user_id: int,
        period_days: int,
    ) -> Dict[str, Any]:
        """
        Собирает данные за период для анализа.

        Returns:
            Dict с данными о прогрессе
        """
        now = datetime.utcnow()
        period_start = now - timedelta(days=period_days)
        period_mid = period_start + timedelta(days=period_days // 2)

        # Получаем mood данные
        all_moods = await self.mood_repo.get_by_date_range(
            user_id=user_id,
            start_date=period_start,
            end_date=now,
        )

        # Минимум 3 записи для сводки
        if len(all_moods) < 3:
            return {"has_sufficient_data": False}

        # Разделяем на две половины периода
        first_half = [m for m in all_moods if m.created_at < period_mid]
        second_half = [m for m in all_moods if m.created_at >= period_mid]

        # Средний mood
        first_half_avg = (
            sum(m.mood_score for m in first_half) / len(first_half)
            if first_half else None
        )
        second_half_avg = (
            sum(m.mood_score for m in second_half) / len(second_half)
            if second_half else None
        )

        # Определяем тренд
        mood_trend = self._calculate_trend(first_half_avg, second_half_avg)

        # Топ эмоций
        emotion_counts = {}
        for mood in all_moods:
            emotion = mood.primary_emotion
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

        top_emotions = sorted(
            emotion_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        # Получаем топ-темы из тегов сообщений
        messages = await self.conversation_repo.get_by_date_range(
            user_id=user_id,
            start_date=period_start,
            end_date=now,
        )

        topic_counts = {}
        for msg in messages:
            for tag in msg.tags or []:
                topic_counts[tag] = topic_counts.get(tag, 0) + 1

        top_topics = sorted(
            topic_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        # Получаем ключевые воспоминания за период
        key_memories = await self.memory_repo.get_by_date_range(
            user_id=user_id,
            start_date=period_start,
            end_date=now,
        )

        return {
            "has_sufficient_data": True,
            "period_days": period_days,
            "period_start": period_start,
            "period_end": now,
            "mood_entries_count": len(all_moods),
            "messages_count": len(messages),
            "first_half_mood_avg": round(first_half_avg, 1) if first_half_avg else None,
            "second_half_mood_avg": round(second_half_avg, 1) if second_half_avg else None,
            "mood_trend": mood_trend,
            "top_emotions": top_emotions,
            "top_topics": top_topics,
            "key_memories": key_memories[:5],  # Топ-5 воспоминаний
        }

    def _calculate_trend(
        self,
        first_avg: Optional[float],
        second_avg: Optional[float],
    ) -> str:
        """Определяет тренд настроения."""
        if first_avg is None or second_avg is None:
            return "недостаточно данных"

        diff = second_avg - first_avg

        if diff > 1.0:
            return "значительное улучшение"
        elif diff > 0.5:
            return "улучшение"
        elif diff < -1.0:
            return "значительное ухудшение"
        elif diff < -0.5:
            return "небольшое ухудшение"
        else:
            return "стабильно"

    async def _generate_summary_text(
        self,
        user_id: int,
        data: Dict[str, Any],
    ) -> str:
        """
        Генерирует текст сводки через Claude API.

        Args:
            user_id: ID пользователя
            data: Данные за период

        Returns:
            Персонализированный текст сводки
        """
        # Формируем промпт для генерации сводки
        prompt = self._build_summary_prompt(data)

        # Генерируем через Claude (без сохранения в историю)
        response = await self.claude_client.generate_simple(
            system_prompt=self._get_summary_system_prompt(),
            user_prompt=prompt,
            max_tokens=500,
        )

        return response

    def _build_summary_prompt(self, data: Dict[str, Any]) -> str:
        """Строит промпт для генерации сводки."""
        parts = [
            f"Создай персонализированную сводку прогресса за {data['period_days']} дней.",
            "",
            "**Данные:**",
            f"- Количество разговоров: {data['messages_count']}",
            f"- Количество записей настроения: {data['mood_entries_count']}",
        ]

        # Тренд настроения
        if data["first_half_mood_avg"] and data["second_half_mood_avg"]:
            parts.append(
                f"- Настроение в начале периода: {data['first_half_mood_avg']}/10"
            )
            parts.append(
                f"- Настроение в конце периода: {data['second_half_mood_avg']}/10"
            )
            parts.append(f"- Тренд: {data['mood_trend']}")

        # Топ эмоций
        if data["top_emotions"]:
            parts.append("\n**Частые эмоции:**")
            for emotion, count in data["top_emotions"]:
                parts.append(f"- {emotion} ({count} раз)")

        # Топ тем
        if data["top_topics"]:
            parts.append("\n**О чём говорили:**")
            for topic, count in data["top_topics"][:3]:
                parts.append(f"- {topic}")

        # Ключевые воспоминания
        if data["key_memories"]:
            parts.append("\n**Что запомнилось:**")
            for memory in data["key_memories"]:
                parts.append(f"- {memory.content[:100]}...")

        parts.append("\n---")
        parts.append(
            "Создай теплую, поддерживающую сводку (2-3 абзаца), "
            "которая отражает прогресс пользователя и мотивирует его продолжать."
        )

        return "\n".join(parts)

    def _get_summary_system_prompt(self) -> str:
        """Системный промпт для генерации сводок."""
        return """Ты — Мира, AI-психолог и подруга.

Твоя задача — создать персонализированную сводку прогресса пользователя за последние 2 недели.

**Стиль сводки:**
- Теплый, дружелюбный тон (как подруга)
- Фокус на прогрессе и позитиве
- Честность: если тренд негативный — мягко признай это
- Мотивация: вдохновить продолжать работу над собой

**Структура:**
1. Приветствие: "Слушай, давай посмотрим что было за эти 2 недели..."
2. Основные наблюдения (настроение, темы, эмоции)
3. Что изменилось / какие шаги сделаны
4. Мотивация на будущее

**НЕ используй:**
- Списки с буллетами
- Формальный язык
- Клише ("ты молодец", "так держать")
- Советы (это сводка, не сессия)

**Объём:** 2-3 абзаца (максимум 400 символов).

Пиши как подруга, которая искренне рада прогрессу человека.
"""

    async def should_send_summary(self, user_id: int) -> bool:
        """
        Проверяет нужно ли отправлять сводку пользователю.

        Критерии:
        - Прошло 14+ дней с последней сводки
        - Есть достаточно активности (минимум 3 mood записи)

        Returns:
            True если нужно отправить сводку
        """
        try:
            # Проверяем последнюю сводку в памяти
            last_summary = await self.memory_repo.get_last_summary(user_id)

            if last_summary:
                days_since_last = (datetime.utcnow() - last_summary.created_at).days
                if days_since_last < 14:
                    return False

            # Проверяем активность за последние 14 дней
            moods = await self.mood_repo.get_recent(user_id, days=14, limit=100)

            if len(moods) < 3:
                logger.debug(f"User {user_id} has insufficient activity for summary")
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking summary eligibility for user {user_id}: {e}")
            return False


# Глобальный экземпляр
summary_generator = SummaryGenerator()
