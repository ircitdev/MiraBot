"""
Context Builder.
Сборка контекста пользователя из памяти и истории.
"""

from typing import Dict, Any, List, Optional
from database.repositories.memory import MemoryRepository
from database.repositories.conversation import ConversationRepository
from config.constants import (
    MEMORY_CATEGORY_FAMILY,
    MEMORY_CATEGORY_PROBLEMS,
    MEMORY_CATEGORY_INSIGHTS,
    MEMORY_CATEGORY_PATTERNS,
    MEMORY_CATEGORY_PROGRESS,
)


class ContextBuilder:
    """Строитель контекста для системного промпта."""
    
    def __init__(self):
        self.memory_repo = MemoryRepository()
        self.conversation_repo = ConversationRepository()
    
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
        
        # Получаем недавние темы из тегов
        recent_topics = await self._get_recent_topics(user_id, limit=5)
        if recent_topics:
            context["recent_topics"] = recent_topics
        
        # Долговременная память (только для премиум)
        if include_long_term_memory:
            long_term_memory = await self._get_long_term_memory(user_id)
            if long_term_memory:
                context["long_term_memory"] = long_term_memory
        
        return context
    
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
        """Получает важные записи из долговременной памяти."""
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
        
        # Сортируем по важности
        all_memories.sort(key=lambda x: x["importance"], reverse=True)
        
        # Возвращаем топ-10
        return all_memories[:10]
    
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
