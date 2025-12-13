"""
Claude API Client.
Обёртка для работы с Anthropic Claude API.
"""

import anthropic
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator, Callable, Awaitable
from loguru import logger

from config.settings import settings
from utils.retry import async_retry, APIError
from database.repositories.memory import MemoryRepository
from database.repositories.conversation import ConversationRepository
from ai.prompts.system_prompt import build_system_prompt
from ai.memory.context_builder import ContextBuilder
from ai.crisis_detector import CrisisDetector


class ClaudeClient:
    """Клиент для работы с Claude API."""
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.memory_repo = MemoryRepository()
        self.conversation_repo = ConversationRepository()
        self.context_builder = ContextBuilder()
        self.crisis_detector = CrisisDetector()
        self.max_retries = 3
        self.retry_delay = 1.0
    
    async def generate_response(
        self,
        user_id: int,
        user_message: str,
        user_data: Dict[str, Any],
        is_premium: bool = False,
    ) -> Dict[str, Any]:
        """
        Генерирует ответ с учётом контекста и памяти.
        
        Args:
            user_id: ID пользователя в БД
            user_message: Сообщение пользователя
            user_data: Данные пользователя (персона, имя, и т.д.)
            is_premium: Премиум ли подписка
        
        Returns:
            {
                "response": str,
                "is_crisis": bool,
                "crisis_level": Optional[str],
                "tags": list[str],
                "tokens_used": int
            }
        """
        try:
            # 1. Проверка на кризисные сигналы
            crisis_check = self.crisis_detector.check(user_message)
            
            # 2. Собираем контекст
            memory_depth = (
                settings.PREMIUM_MEMORY_DEPTH if is_premium 
                else settings.FREE_MEMORY_DEPTH
            )
            
            context = await self.context_builder.build(
                user_id=user_id,
                user_data=user_data,
                recent_messages_limit=memory_depth,
                include_long_term_memory=is_premium,
            )
            
            # 3. Формируем системный промпт
            system_prompt = build_system_prompt(
                persona=user_data.get("persona", "mira"),
                user_context=context,
                is_crisis=crisis_check["is_crisis"],
            )
            
            # 4. Собираем историю сообщений
            messages = await self._build_messages(
                user_id=user_id,
                current_message=user_message,
                limit=memory_depth,
            )
            
            # 5. Запрос к Claude
            response = self.client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=settings.CLAUDE_MAX_TOKENS,
                system=system_prompt,
                messages=messages,
            )
            
            response_text = response.content[0].text
            
            # 6. Извлекаем теги для памяти
            tags = self._extract_tags(user_message, response_text, crisis_check)
            
            logger.info(
                f"Generated response for user {user_id}, "
                f"tokens: {response.usage.input_tokens + response.usage.output_tokens}, "
                f"is_crisis: {crisis_check['is_crisis']}"
            )
            
            return {
                "response": response_text,
                "is_crisis": crisis_check["is_crisis"],
                "crisis_level": crisis_check.get("level"),
                "tags": tags,
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
            }
            
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    async def generate_response_stream(
        self,
        user_id: int,
        user_message: str,
        user_data: Dict[str, Any],
        is_premium: bool = False,
        on_chunk: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Генерирует ответ с учётом контекста и памяти в режиме streaming.

        Args:
            user_id: ID пользователя в БД
            user_message: Сообщение пользователя
            user_data: Данные пользователя (персона, имя, и т.д.)
            is_premium: Премиум ли подписка
            on_chunk: Callback для обработки каждого чанка текста

        Returns:
            {
                "response": str,
                "is_crisis": bool,
                "crisis_level": Optional[str],
                "tags": list[str],
                "tokens_used": int
            }
        """
        try:
            # 1. Проверка на кризисные сигналы
            crisis_check = self.crisis_detector.check(user_message)

            # 2. Собираем контекст
            memory_depth = (
                settings.PREMIUM_MEMORY_DEPTH if is_premium
                else settings.FREE_MEMORY_DEPTH
            )

            context = await self.context_builder.build(
                user_id=user_id,
                user_data=user_data,
                recent_messages_limit=memory_depth,
                include_long_term_memory=is_premium,
            )

            # 3. Формируем системный промпт
            system_prompt = build_system_prompt(
                persona=user_data.get("persona", "mira"),
                user_context=context,
                is_crisis=crisis_check["is_crisis"],
            )

            # 4. Собираем историю сообщений
            messages = await self._build_messages(
                user_id=user_id,
                current_message=user_message,
                limit=memory_depth,
            )

            # 5. Streaming запрос к Claude
            full_response = ""
            input_tokens = 0
            output_tokens = 0

            with self.client.messages.stream(
                model=settings.CLAUDE_MODEL,
                max_tokens=settings.CLAUDE_MAX_TOKENS,
                system=system_prompt,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    full_response += text
                    if on_chunk:
                        await on_chunk(text)

                # Получаем финальное сообщение для статистики
                final_message = stream.get_final_message()
                input_tokens = final_message.usage.input_tokens
                output_tokens = final_message.usage.output_tokens

            # 6. Извлекаем теги для памяти
            tags = self._extract_tags(user_message, full_response, crisis_check)

            logger.info(
                f"Generated streaming response for user {user_id}, "
                f"tokens: {input_tokens + output_tokens}, "
                f"is_crisis: {crisis_check['is_crisis']}"
            )

            return {
                "response": full_response,
                "is_crisis": crisis_check["is_crisis"],
                "crisis_level": crisis_check.get("level"),
                "tags": tags,
                "tokens_used": input_tokens + output_tokens,
            }

        except anthropic.APIError as e:
            logger.error(f"Claude API error (streaming): {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating streaming response: {e}")
            raise

    async def _build_messages(
        self,
        user_id: int,
        current_message: str,
        limit: int,
    ) -> List[Dict[str, str]]:
        """Собирает историю сообщений для контекста."""
        history = await self.conversation_repo.get_recent(
            user_id=user_id,
            limit=limit,
        )
        
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in history
        ]
        messages.append({"role": "user", "content": current_message})
        
        return messages
    
    def _extract_tags(
        self,
        user_message: str,
        response: str,
        crisis_check: Dict[str, Any],
    ) -> List[str]:
        """Извлекает теги для категоризации диалога."""
        tags = []
        
        if crisis_check["is_crisis"]:
            tags.append("crisis")
        
        # Тематические теги
        topic_keywords = {
            "topic:husband": ["муж", "супруг", "он сказал", "он сделал", "мужа", "мужем"],
            "topic:children": ["ребёнок", "ребенок", "дети", "сын", "дочь", "школа", "детей", "детьми"],
            "topic:self": ["я хочу", "моя жизнь", "саморазвитие", "мечта", "себя", "для себя"],
            "topic:relatives": ["свекровь", "тёща", "теща", "родители", "родственники", "свекрови"],
            "topic:intimacy": ["близость", "секс", "нежность", "охлаждение", "интим"],
            "topic:work": ["работа", "карьера", "начальник", "коллеги", "офис"],
        }
        
        combined_text = (user_message + " " + response).lower()
        
        for tag, keywords in topic_keywords.items():
            if any(kw in combined_text for kw in keywords):
                tags.append(tag)
        
        # Детекция инсайтов
        insight_markers = [
            "поняла", "осознала", "теперь вижу", "никогда не думала",
            "до меня дошло", "я осознаю", "стало понятно"
        ]
        if any(marker in combined_text for marker in insight_markers):
            tags.append("insight")
        
        # Детекция позитива
        positive_markers = ["спасибо", "благодарю", "стало легче", "помогло"]
        if any(marker in combined_text for marker in positive_markers):
            tags.append("positive")
        
        return tags
    
    async def generate_ritual_message(
        self,
        ritual_type: str,
        user_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Генерирует сообщение для ритуала.
        
        Args:
            ritual_type: Тип ритуала (morning_checkin, evening_checkin, etc.)
            user_data: Данные пользователя
            context: Дополнительный контекст
        
        Returns:
            Текст сообщения
        """
        from ai.prompts.rituals import get_ritual_prompt
        
        prompt = get_ritual_prompt(ritual_type, user_data, context)
        
        response = self.client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=300,
            system=prompt["system"],
            messages=[{"role": "user", "content": prompt["user"]}],
        )
        
        return response.content[0].text
    
    async def summarize_conversation(
        self,
        messages: List[Dict[str, str]],
    ) -> str:
        """
        Суммаризирует разговор для памяти.
        
        Args:
            messages: Список сообщений
        
        Returns:
            Краткое резюме
        """
        conversation_text = "\n".join([
            f"{'Пользователь' if m['role'] == 'user' else 'Бот'}: {m['content']}"
            for m in messages
        ])
        
        response = self.client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=500,
            system="""
            Ты — ассистент для суммаризации разговоров.
            Твоя задача — выделить ключевые темы, инсайты и важную информацию из разговора.
            Пиши кратко, по пунктам.
            Выдели:
            - Основные темы/проблемы
            - Важные факты о пользователе
            - Инсайты и осознания
            - Эмоциональное состояние
            """,
            messages=[{
                "role": "user",
                "content": f"Суммаризируй этот разговор:\n\n{conversation_text}"
            }],
        )
        
        return response.content[0].text
