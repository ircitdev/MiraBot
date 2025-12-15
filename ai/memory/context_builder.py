"""
Context Builder.
Сборка контекста пользователя из памяти и истории.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from loguru import logger
from database.repositories.memory import MemoryRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.mood import MoodRepository
from database.repositories.user import UserRepository
from ai.style_analyzer import style_analyzer
from config.constants import (
    MEMORY_CATEGORY_FAMILY,
    MEMORY_CATEGORY_PROBLEMS,
    MEMORY_CATEGORY_INSIGHTS,
    MEMORY_CATEGORY_PATTERNS,
    MEMORY_CATEGORY_PROGRESS,
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
    
    async def build(
        self,
        user_id: int,
        user_data: Dict[str, Any],
        recent_messages_limit: int = 10,
        include_long_term_memory: bool = True,
    ) -> Dict[str, Any]:
        """
        Собирает полный контекст пользователя.
        
        Args:
            user_id: ID пользователя
            user_data: Базовые данные пользователя
            recent_messages_limit: Лимит недавних сообщений
            include_long_term_memory: Включать ли долговременную память
        
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
