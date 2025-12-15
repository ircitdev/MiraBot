"""
Context Builder.
Сборка контекста пользователя из памяти и истории.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from loguru import logger
import pytz
from database.repositories.memory import MemoryRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.mood import MoodRepository
from database.repositories.user import UserRepository
from database.repositories.trigger import TriggerRepository
from ai.style_analyzer import style_analyzer
from ai.question_type_detector import question_type_detector
from config.constants import (
    MEMORY_CATEGORY_FAMILY,
    MEMORY_CATEGORY_PROBLEMS,
    MEMORY_CATEGORY_INSIGHTS,
    MEMORY_CATEGORY_PATTERNS,
    MEMORY_CATEGORY_PROGRESS,
    MEMORY_CATEGORY_ATTEMPTS,
)

# Интервал обновления стиля (в сообщениях)
STYLE_UPDATE_INTERVAL = 50


class ContextBuilder:
    """Строитель контекста для системного промпта."""

    def __init__(self):
        self.memory_repo = MemoryRepository()
        self.conversation_repo = ConversationRepository()
        self.mood_repo = MoodRepository()
        self.user_repo = UserRepository()
        self.trigger_repo = TriggerRepository()
    
    async def build(
        self,
        user_id: int,
        user_data: Dict[str, Any],
        recent_messages_limit: int = 10,
        include_long_term_memory: bool = True,
        current_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Собирает полный контекст пользователя.

        Args:
            user_id: ID пользователя
            user_data: Базовые данные пользователя
            recent_messages_limit: Лимит недавних сообщений
            include_long_term_memory: Включать ли долговременную память
            current_message: Текущее сообщение пользователя (для детекции вопроса)

        Returns:
            Словарь с контекстом для промпта
        """
        context = {
            "display_name": user_data.get("display_name"),
            "persona": user_data.get("persona"),
            "partner_name": user_data.get("partner_name"),
            "marriage_years": user_data.get("marriage_years"),
            "children_info": user_data.get("children_info"),
        }

        # Детекция типа вопроса (если есть текущее сообщение)
        if current_message:
            question_info = question_type_detector.detect(current_message)
            if question_info:
                context["question_type"] = question_info

        # Добавляем контекст времени суток
        time_context = self._get_time_context(user_data.get("timezone", "Europe/Moscow"))
        if time_context:
            context["time_context"] = time_context

        # Детектор зацикливания на темах
        conversation_patterns = await self._detect_conversation_patterns(user_id)
        if conversation_patterns:
            context["conversation_patterns"] = conversation_patterns

        # Добавляем контекст последнего отправленного фото если есть
        # Это помогает Claude понимать вопросы вроде "Сколько ему?" после показа фото
        last_photo_sent = user_data.get("last_photo_sent")
        if last_photo_sent:
            context["last_photo_sent"] = last_photo_sent

        # Получаем недавние темы из тегов
        recent_topics = await self._get_recent_topics(user_id, limit=5)
        if recent_topics:
            context["recent_topics"] = recent_topics

        # Mood tracking — история настроения
        mood_summary = await self._get_mood_summary(user_id)
        if mood_summary and mood_summary.get("has_data"):
            context["mood_summary"] = mood_summary

        # Чувствительные темы (триггеры)
        sensitive_topics = await self._get_sensitive_topics(user_id)
        if sensitive_topics:
            context["sensitive_topics"] = sensitive_topics

        # Долговременная память (только для премиум)
        if include_long_term_memory:
            long_term_memory = await self._get_long_term_memory(user_id)
            if long_term_memory:
                context["long_term_memory"] = long_term_memory

        # Стиль общения пользователя (персонализация)
        communication_style = user_data.get("communication_style")

        # Проверяем, нужно ли обновить стиль
        should_update_style = await self._should_update_style(
            user_id=user_id,
            current_style=communication_style,
        )

        if communication_style and not should_update_style:
            context["communication_style"] = communication_style
        else:
            # Анализируем стиль из недавних сообщений
            recent_messages = await self.conversation_repo.get_recent(
                user_id=user_id, limit=20
            )
            if recent_messages:
                messages_for_analysis = [
                    {"role": m.role, "content": m.content}
                    for m in recent_messages
                ]
                analyzed_style = style_analyzer.analyze_messages(messages_for_analysis)
                context["communication_style"] = analyzed_style

                # Сохраняем обновлённый стиль в БД
                try:
                    await self.user_repo.update_communication_style(
                        user_id=user_id,
                        style=analyzed_style,
                    )
                    logger.info(f"Updated communication style for user {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to save communication style: {e}")

        return context

    async def _should_update_style(
        self,
        user_id: int,
        current_style: Optional[Dict[str, Any]],
    ) -> bool:
        """
        Определяет, нужно ли обновить стиль общения.

        Обновляем если:
        - Стиль ещё не анализировался
        - Прошло более 50 сообщений с последнего обновления
        """
        if not current_style:
            return True

        style_updated_at = current_style.get("updated_at")
        if not style_updated_at:
            return True

        # Получаем количество сообщений пользователя
        message_count = await self.conversation_repo.count_user_messages(user_id)

        # Обновляем каждые N сообщений
        if message_count > 0 and message_count % STYLE_UPDATE_INTERVAL == 0:
            logger.debug(
                f"Style update triggered for user {user_id}: "
                f"{message_count} messages"
            )
            return True

        return False
    
    async def _get_recent_topics(
        self,
        user_id: int,
        limit: int = 5,
    ) -> List[str]:
        """Извлекает недавние темы из тегов сообщений."""
        top_tags = await self.conversation_repo.get_top_tags(user_id, limit=limit)
        
        # Фильтруем только тематические теги
        topics = []
        for tag_info in top_tags:
            tag = tag_info.get("tag", "")
            if tag.startswith("topic:"):
                topic_name = tag.replace("topic:", "")
                # Переводим в человекочитаемый формат
                topic_names = {
                    "husband": "отношения с мужем",
                    "children": "дети",
                    "self": "самореализация",
                    "relatives": "родственники",
                    "intimacy": "близость",
                    "work": "работа",
                }
                readable_name = topic_names.get(topic_name, topic_name)
                topics.append(readable_name)
        
        return topics
    
    async def _get_long_term_memory(
        self,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Получает важные записи из долговременной памяти.

        КРИТИЧЕСКИ ВАЖНО: Приоритет отдаётся ФАКТАМ о пользователе:
        - Профессия, место работы
        - Семейные факты
        - Важные события из жизни
        """
        categories = [
            MEMORY_CATEGORY_FAMILY,
            MEMORY_CATEGORY_PROBLEMS,
            MEMORY_CATEGORY_INSIGHTS,
            MEMORY_CATEGORY_PATTERNS,
            MEMORY_CATEGORY_ATTEMPTS,  # Попытки решения
        ]

        all_memories = []

        for category in categories:
            memories = await self.memory_repo.get_by_user(
                user_id=user_id,
                category=category,
                min_importance=5,  # Только важные
                limit=5,  # Максимум 5 на категорию
            )

            for mem in memories:
                all_memories.append({
                    "category": category,
                    "content": mem.content,
                    "importance": mem.importance,
                })

        # УЛУЧШЕНИЕ: Повышаем важность ФАКТОВ о работе/профессии
        # Эти факты должны ВСЕГДА быть в контексте!
        for memory in all_memories:
            content_lower = memory["content"].lower()
            # Проверяем ключевые слова профессии/работы
            if any(keyword in content_lower for keyword in [
                "работаю", "работа:", "профессия:", "я медсестра", "я врач",
                "я учитель", "я менеджер", "я программист", "в больнице",
                "в школе", "в офисе", "должность:", "специальность:"
            ]):
                # Повышаем важность до максимума
                memory["importance"] = max(memory["importance"], 10)
                logger.debug(f"Boosted work-related memory importance: {memory['content'][:50]}")

        # Сортируем по важности
        all_memories.sort(key=lambda x: x["importance"], reverse=True)

        # Возвращаем топ-15 (увеличил лимит для большего контекста)
        return all_memories[:15]

    async def _get_mood_summary(
        self,
        user_id: int,
        days: int = 7,
    ) -> Optional[Dict[str, Any]]:
        """Получает сводку по настроению пользователя."""
        try:
            summary = await self.mood_repo.get_mood_summary(user_id, days=days)
            return summary
        except Exception:
            # Если таблица не существует или ошибка — игнорируем
            return None

    async def build_minimal(
        self,
        user_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Собирает минимальный контекст (только базовые данные).
        Используется для free-пользователей или быстрых ответов.
        """
        return {
            "display_name": user_data.get("display_name"),
            "persona": user_data.get("persona"),
            "partner_name": user_data.get("partner_name"),
            "children_info": user_data.get("children_info"),
        }

    async def _detect_conversation_patterns(
        self,
        user_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Детектит паттерны разговора: зацикливание на темах, повторяющиеся жалобы.

        Returns:
            Dict с информацией о паттернах или None если паттернов нет
        """
        try:
            # Получаем последние 30 сообщений для анализа
            recent_messages = await self.conversation_repo.get_recent(
                user_id=user_id,
                limit=30,
            )

            if len(recent_messages) < 10:
                return None  # Слишком мало данных для анализа

            # Собираем статистику по тегам
            topic_counts = {}
            for msg in recent_messages:
                if hasattr(msg, 'tags') and msg.tags:
                    for tag in msg.tags:
                        if tag.startswith("topic:"):
                            topic_counts[tag] = topic_counts.get(tag, 0) + 1

            if not topic_counts:
                return None

            total_messages = len(recent_messages)

            # Ищем "застревание" на теме
            # Тема считается "застрявшей" если упоминается в >40% последних сообщений
            stuck_topic = None
            stuck_percentage = 0

            for topic, count in topic_counts.items():
                percentage = (count / total_messages) * 100
                if percentage > 40:  # Больше 40% сообщений об одной теме
                    stuck_topic = topic
                    stuck_percentage = percentage
                    break

            if stuck_topic:
                # Переводим тег в читаемый формат
                topic_names = {
                    "topic:husband": "отношения с мужем",
                    "topic:children": "дети",
                    "topic:self": "самореализация",
                    "topic:relatives": "родственники",
                    "topic:intimacy": "близость",
                    "topic:work": "работа",
                }
                readable_topic = topic_names.get(stuck_topic, stuck_topic.replace("topic:", ""))

                logger.info(
                    f"User {user_id} stuck on topic: {stuck_topic} "
                    f"({stuck_percentage:.1f}% of last {total_messages} messages)"
                )

                return {
                    "stuck_on_topic": stuck_topic,
                    "stuck_topic_name": readable_topic,
                    "stuck_percentage": int(stuck_percentage),
                    "needs_breakthrough": True,
                }

            return None

        except Exception as e:
            logger.warning(f"Error detecting conversation patterns: {e}")
            return None

    def _get_time_context(self, timezone_str: str) -> Optional[Dict[str, Any]]:
        """
        Определяет время суток пользователя для адаптации тона.

        Args:
            timezone_str: Часовой пояс пользователя

        Returns:
            Dict с информацией о времени суток
        """
        try:
            user_tz = pytz.timezone(timezone_str)
            current_time = datetime.now(user_tz)
            hour = current_time.hour

            # Определяем период суток
            if 6 <= hour < 12:
                period = "утро"
                tone_hint = "бодрая, мотивирующая (но не навязчиво)"
            elif 12 <= hour < 18:
                period = "день"
                tone_hint = "деловая, энергичная"
            elif 18 <= hour < 23:
                period = "вечер"
                tone_hint = "спокойная, рефлексивная, располагающая к откровенности"
            else:  # 23-6
                period = "ночь"
                tone_hint = "очень мягкая, утешающая (если пишет ночью — значит что-то беспокоит)"

            return {
                "hour": hour,
                "period": period,
                "tone_hint": tone_hint,
            }

        except Exception as e:
            logger.warning(f"Error getting time context: {e}")
            return None

    async def _get_sensitive_topics(self, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        Получает чувствительные темы (триггеры) пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Список триггеров или None
        """
        try:
            triggers = await self.trigger_repo.get_active_triggers(user_id)

            if not triggers:
                return None

            # Форматируем для промпта
            sensitive_topics = []
            for trigger in triggers:
                sensitive_topics.append({
                    "topic": trigger.topic,
                    "severity": trigger.severity,
                    "description": trigger.description,
                })

            logger.debug(f"Loaded {len(sensitive_topics)} sensitive topics for user {user_id}")
            return sensitive_topics

        except Exception as e:
            logger.warning(f"Error getting sensitive topics: {e}")
            return None
