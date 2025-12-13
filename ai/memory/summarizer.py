"""
Conversation Summarizer.
Суммаризация разговоров для долговременной памяти.
"""

from typing import List, Dict, Any, Optional
import anthropic
from config.settings import settings
from database.repositories.memory import MemoryRepository
from config.constants import (
    MEMORY_CATEGORY_FAMILY,
    MEMORY_CATEGORY_PROBLEMS,
    MEMORY_CATEGORY_INSIGHTS,
    MEMORY_CATEGORY_PATTERNS,
    MEMORY_CATEGORY_PROGRESS,
)


class ConversationSummarizer:
    """Суммаризатор разговоров для памяти."""
    
    EXTRACTION_PROMPT = """
Ты — ассистент для анализа разговоров. 
Твоя задача — извлечь важную информацию для долговременной памяти.

Проанализируй разговор и извлеки:

1. **Семья (family):** факты о семье пользователя
   - Имена членов семьи
   - Возраст детей
   - Важные события

2. **Проблемы (problems):** текущие проблемы и темы
   - О чём беспокоится
   - Что вызывает стресс
   - Конфликты

3. **Инсайты (insights):** осознания пользователя
   - Что поняла нового
   - Важные выводы

4. **Паттерны (patterns):** повторяющиеся темы
   - Что упоминает часто
   - Триггеры эмоций

Формат ответа — JSON:
{
    "family": ["факт 1", "факт 2"],
    "problems": ["проблема 1"],
    "insights": ["инсайт 1"],
    "patterns": ["паттерн 1"]
}

Если категория пустая — верни пустой массив.
Каждый факт — краткий (1-2 предложения).
"""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.memory_repo = MemoryRepository()
    
    async def extract_and_save(
        self,
        user_id: int,
        messages: List[Dict[str, str]],
    ) -> Dict[str, List[str]]:
        """
        Извлекает важную информацию из разговора и сохраняет в память.
        
        Args:
            user_id: ID пользователя
            messages: Список сообщений разговора
        
        Returns:
            Словарь извлечённых данных по категориям
        """
        # Формируем текст разговора
        conversation_text = self._format_conversation(messages)
        
        if len(conversation_text) < 100:  # Слишком короткий разговор
            return {}
        
        # Извлекаем информацию через Claude
        extracted = await self._extract_info(conversation_text)
        
        if not extracted:
            return {}
        
        # Сохраняем в память
        await self._save_to_memory(user_id, extracted, messages)
        
        return extracted
    
    def _format_conversation(
        self,
        messages: List[Dict[str, str]],
    ) -> str:
        """Форматирует сообщения в текст."""
        lines = []
        for msg in messages:
            role = "Пользователь" if msg["role"] == "user" else "Бот"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)
    
    async def _extract_info(
        self,
        conversation_text: str,
    ) -> Optional[Dict[str, List[str]]]:
        """Извлекает информацию через Claude."""
        try:
            response = self.client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=500,
                system=self.EXTRACTION_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"Проанализируй этот разговор:\n\n{conversation_text}"
                }],
            )
            
            # Парсим JSON из ответа
            import json
            response_text = response.content[0].text
            
            # Ищем JSON в ответе
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            
            if start != -1 and end != 0:
                json_str = response_text[start:end]
                return json.loads(json_str)
            
            return None
            
        except Exception as e:
            from loguru import logger
            logger.error(f"Error extracting conversation info: {e}")
            return None
    
    async def _save_to_memory(
        self,
        user_id: int,
        extracted: Dict[str, List[str]],
        messages: List[Dict[str, str]],
    ) -> None:
        """Сохраняет извлечённую информацию в память."""
        # Получаем ID сообщений (если есть)
        message_ids = [m.get("id") for m in messages if m.get("id")]
        
        category_map = {
            "family": MEMORY_CATEGORY_FAMILY,
            "problems": MEMORY_CATEGORY_PROBLEMS,
            "insights": MEMORY_CATEGORY_INSIGHTS,
            "patterns": MEMORY_CATEGORY_PATTERNS,
        }
        
        # Определяем важность
        importance_map = {
            "family": 8,  # Факты о семье важны
            "problems": 7,
            "insights": 9,  # Инсайты очень важны
            "patterns": 6,
        }
        
        for key, items in extracted.items():
            if not items:
                continue
            
            category = category_map.get(key)
            if not category:
                continue
            
            importance = importance_map.get(key, 5)
            
            for item in items:
                if len(item.strip()) < 10:  # Слишком короткий факт
                    continue
                
                # Проверяем, нет ли уже похожей записи
                existing = await self.memory_repo.search(
                    user_id=user_id,
                    query=item[:50],  # Поиск по началу
                    limit=1,
                )
                
                if existing:
                    # Обновляем важность существующей записи
                    await self.memory_repo.update(
                        existing[0].id,
                        importance=max(existing[0].importance, importance),
                    )
                else:
                    # Создаём новую запись
                    await self.memory_repo.create(
                        user_id=user_id,
                        category=category,
                        content=item,
                        importance=importance,
                        source_message_ids=message_ids[:5] if message_ids else None,
                    )
    
    async def summarize_for_followup(
        self,
        messages: List[Dict[str, str]],
    ) -> str:
        """
        Создаёт краткое резюме для followup-сообщения.
        
        Args:
            messages: Сообщения последнего разговора
        
        Returns:
            Краткое резюме (1-2 предложения)
        """
        conversation_text = self._format_conversation(messages[-10:])  # Последние 10 сообщений
        
        try:
            response = self.client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=100,
                system="Ты создаёшь очень краткие резюме разговоров (1-2 предложения).",
                messages=[{
                    "role": "user",
                    "content": f"Кратко (1-2 предложения) о чём был разговор:\n\n{conversation_text}"
                }],
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            from loguru import logger
            logger.error(f"Error summarizing conversation: {e}")
            return "был важный разговор"
