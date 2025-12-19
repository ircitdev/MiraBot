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
from ai.memory.attempt_detector import attempt_detector
from ai.question_type_detector import question_type_detector
from ai.trigger_detector import trigger_detector
from ai.medical_filter import medical_filter
from database.repositories.trigger import TriggerRepository
from config.constants import MEMORY_CATEGORY_ATTEMPTS


class ClaudeClient:
    """Клиент для работы с Claude API."""
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.memory_repo = MemoryRepository()
        self.conversation_repo = ConversationRepository()
        self.trigger_repo = TriggerRepository()
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
                current_message=user_message,
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

            # 5.5. Фильтруем медицинские советы
            response_text = medical_filter.filter_response(user_message, response_text)

            # 6. Извлекаем теги для памяти
            tags = self._extract_tags(user_message, response_text, crisis_check)

            # 7. Детектим и сохраняем упоминания о попытках решения
            await self._detect_and_save_attempts(
                user_id=user_id,
                user_message=user_message,
                response_text=response_text,
            )

            # 8. Детектим негативные реакции на темы (триггеры)
            await self._detect_and_save_trigger(
                user_id=user_id,
                user_message=user_message,
                bot_response=response_text,
            )

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
                current_message=user_message,
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

            # 5.5. Проверяем нужен ли медицинский дисклеймер
            # В streaming режиме мы не можем изменить уже отправленный текст,
            # но можем добавить дисклеймер в конец если нужно
            filtered_response = medical_filter.filter_response(user_message, full_response)
            if filtered_response != full_response:
                # Дисклеймер был добавлен - нужно отправить его
                disclaimer_part = filtered_response[len(full_response):]
                if on_chunk and disclaimer_part:
                    await on_chunk(disclaimer_part)
                full_response = filtered_response

            # 6. Извлекаем теги для памяти
            tags = self._extract_tags(user_message, full_response, crisis_check)

            # 7. Детектим и сохраняем упоминания о попытках решения
            await self._detect_and_save_attempts(
                user_id=user_id,
                user_message=user_message,
                response_text=full_response,
            )

            # 8. Детектим негативные реакции на темы (триггеры)
            await self._detect_and_save_trigger(
                user_id=user_id,
                user_message=user_message,
                bot_response=full_response,
            )

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
        """
        Извлекает теги для категоризации диалога.

        ВАЖНО: Используем СТРОГИЕ критерии для тегов!
        Тег добавляется только если тема АКТИВНО обсуждается, а не просто упоминается.
        """
        tags = []

        if crisis_check["is_crisis"]:
            tags.append("crisis")

        # Тематические теги — СТРОГИЕ КРИТЕРИИ
        # Тег добавляется только если тема ЦЕНТРАЛЬНАЯ в сообщении

        combined_text = (user_message + " " + response).lower()
        user_lower = user_message.lower()

        # topic:husband - только если муж АКТИВНО обсуждается
        if any(phrase in combined_text for phrase in [
            "с мужем", "муж не", "муж сказал", "муж сделал",
            "супруг", "мужа", "мужем отношения", "муж меня"
        ]):
            tags.append("topic:husband")

        # topic:children - только если дети в фокусе разговора
        if any(phrase in combined_text for phrase in [
            "дети", "ребёнок", "ребенок", "сын", "дочь",
            "детьми", "детей", "ребёнка", "школ", "детский сад"
        ]):
            tags.append("topic:children")

        # topic:work - СТРОГО только при активном обсуждении работы
        # НЕ добавляем тег если просто упомянута "работа" вскользь!
        if any(phrase in combined_text for phrase in [
            "на работе", "работе трудно", "работе тяжело",
            "начальник", "коллеги меня", "устала на работе",
            "выгораю", "карьера", "увольняться",
            "рабочий день", "работе не ценят", "работе стресс"
        ]):
            tags.append("topic:work")

        # topic:self - только при фокусе на себе
        if any(phrase in user_lower for phrase in [
            "я хочу", "моя жизнь", "мне нужно", "я мечтаю",
            "для себя", "о себе", "саморазвитие", "мои желания"
        ]):
            tags.append("topic:self")

        # topic:relatives - только при активном обсуждении родственников
        if any(phrase in combined_text for phrase in [
            "свекровь", "тёща", "теща", "родители",
            "свекрови", "родственник", "родня"
        ]):
            tags.append("topic:relatives")

        # topic:intimacy - только при обсуждении близости
        if any(phrase in combined_text for phrase in [
            "близост", "секс", "интим", "нежност",
            "охлаждени", "страст", "желани"
        ]):
            tags.append("topic:intimacy")
        
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

    async def generate_response_with_image(
        self,
        user_id: int,
        image_base64: str,
        media_type: str,
        caption: Optional[str],
        user_data: Dict[str, Any],
        is_premium: bool = False,
    ) -> Dict[str, Any]:
        """
        Генерирует ответ на изображение с учётом контекста.

        Args:
            user_id: ID пользователя в БД
            image_base64: Base64-encoded изображение
            media_type: MIME тип (image/jpeg, image/png, etc.)
            caption: Подпись к фото (если есть)
            user_data: Данные пользователя
            is_premium: Премиум ли подписка

        Returns:
            {
                "response": str,
                "is_crisis": bool,
                "tags": list[str],
                "tokens_used": int
            }
        """
        try:
            # 1. Собираем контекст
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

            # 2. Формируем системный промпт с инструкциями для фото
            base_prompt = build_system_prompt(
                persona=user_data.get("persona", "mira"),
                user_context=context,
                is_crisis=False,
            )

            image_instructions = """

## АНАЛИЗ ФОТОГРАФИЙ

Когда пользователь присылает фото, ты:
1. Внимательно смотришь на изображение
2. Отмечаешь эмоциональный контекст (настроение, атмосфера)
3. Реагируешь как близкая подруга — тепло, с интересом
4. Можешь задать вопросы о том, что видишь
5. Если на фото человек — комментируй тактично и поддерживающе
6. Если это что-то личное (дом, еда, место) — прояви искренний интерес

КРИТИЧЕСКИ ВАЖНО:
- ОПИСЫВАЙ ТОЛЬКО ТО, ЧТО РЕАЛЬНО ВИДНО НА ФОТО!
- НЕ ПРИДУМЫВАЙ детали, объекты или людей, которых нет на изображении!
- Если не уверена в чём-то — СПРОСИ, а не догадывайся!
- Если фото нечёткое или непонятное — так и скажи: "Что-то не очень разглядела, что это?"

ВАЖНО про людей на фото:
- НЕ называй людей на фото именами из своей жизни (Андрей, Алиса, Тима и т.д.)!
- Это фото ПОЛЬЗОВАТЕЛЯ, не твоё. Ты не знаешь кто эти люди.
- Если видишь человека — спроси "А кто это с тобой?" или "Это твой муж/подруга?"
- Используй имя партнёра пользователя ТОЛЬКО если оно указано в контексте выше

НЕ делай:
- НЕ ПРИДУМЫВАЙ то, чего нет на фото (например, лошадей вместо машины)!
- Не перечисляй все объекты на фото как робот
- Не давай оценок внешности ("ты красивая/некрасивая")
- Не будь формальной или отстранённой
- Не путай свою жизнь с жизнью пользователя!

Примеры реакций:
- "Ооо, какое уютное место! Это у тебя дома?"
- "Вижу, ты куда-то выбралась! Как там?"
- "Какая атмосферная фотка... А кто это рядом с тобой?"
- "Ух ты, как уютно! Расскажи, что там было?"
- "Хм, не очень разглядела... Что это на фото?"
"""

            system_prompt = base_prompt + image_instructions

            # 3. Формируем контент с изображением
            user_content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64,
                    },
                },
            ]

            # Добавляем подпись если есть
            if caption:
                user_content.append({
                    "type": "text",
                    "text": caption,
                })
            else:
                user_content.append({
                    "type": "text",
                    "text": "(пользователь прислал фото без подписи)",
                })

            # 4. Запрос к Claude
            response = self.client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=settings.CLAUDE_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )

            response_text = response.content[0].text

            logger.info(
                f"Generated image response for user {user_id}, "
                f"tokens: {response.usage.input_tokens + response.usage.output_tokens}"
            )

            return {
                "response": response_text,
                "is_crisis": False,
                "crisis_level": None,
                "tags": ["photo"],
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
            }

        except anthropic.APIError as e:
            logger.error(f"Claude API error (image): {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating image response: {e}")
            raise

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

    async def generate_simple(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
    ) -> str:
        """
        Простая генерация без контекста и памяти.
        Используется для ритуалов, подсказок и других коротких сообщений.

        Args:
            system_prompt: Системный промпт
            user_prompt: Пользовательский промпт
            max_tokens: Максимальное количество токенов

        Returns:
            Сгенерированный текст
        """
        try:
            response = self.client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            return response.content[0].text

        except anthropic.APIError as e:
            logger.error(f"Claude API error in generate_simple: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in generate_simple: {e}")
            raise

    async def _detect_and_save_attempts(
        self,
        user_id: int,
        user_message: str,
        response_text: str,
    ) -> None:
        """
        Детектит упоминания о попытках решения проблем и сохраняет в память.

        Args:
            user_id: ID пользователя
            user_message: Сообщение пользователя
            response_text: Ответ бота
        """
        try:
            # Детектим попытку
            attempt_info = attempt_detector.detect(
                user_message=user_message,
                assistant_response=response_text,
            )

            if not attempt_info:
                return

            # Формируем текст для памяти
            solution_name = attempt_info["solution_name"]
            result = attempt_info["result"]

            result_text = {
                "negative": "не помогло",
                "positive": "помогло",
                "neutral": "помогло частично",
                "unknown": "пыталась",
            }.get(result, "пыталась")

            memory_content = f"Попытка: {solution_name} — {result_text}"

            # Проверяем, нет ли уже похожей записи
            existing = await self.memory_repo.search(
                user_id=user_id,
                query=solution_name[:30],  # Поиск по названию решения
                limit=1,
            )

            if existing and solution_name.lower() in existing[0].content.lower():
                # Уже есть запись об этом решении — обновляем важность
                await self.memory_repo.update(
                    existing[0].id,
                    importance=max(existing[0].importance, attempt_info["importance"]),
                )
                logger.debug(f"Updated existing attempt memory: {solution_name}")
            else:
                # Создаём новую запись
                await self.memory_repo.create(
                    user_id=user_id,
                    category=MEMORY_CATEGORY_ATTEMPTS,
                    content=memory_content,
                    importance=attempt_info["importance"],
                )
                logger.info(f"Saved attempt to memory: {memory_content}")

        except Exception as e:
            # Не падаем если не удалось сохранить попытку
            logger.warning(f"Failed to detect/save attempt: {e}")

    async def _detect_and_save_trigger(
        self,
        user_id: int,
        user_message: str,
        bot_response: str,
    ) -> None:
        """
        Детектит негативную реакцию на тему и сохраняет триггер.

        Args:
            user_id: ID пользователя
            user_message: Сообщение пользователя
            bot_response: Ответ бота
        """
        try:
            # Детектим негативную реакцию
            trigger_info = trigger_detector.detect_negative_reaction(
                user_message=user_message,
                previous_bot_message=bot_response,
            )

            if not trigger_info or not trigger_info.get("has_negative_reaction"):
                return

            topic = trigger_info.get("topic")
            if not topic:
                logger.debug("Negative reaction detected but topic unknown")
                return

            # Сохраняем триггер
            await self.trigger_repo.create(
                user_id=user_id,
                topic=topic,
                description=trigger_info.get("reason"),
                severity=trigger_info.get("severity", 5),
            )

            logger.info(f"Saved trigger for user {user_id}: {topic} (severity={trigger_info['severity']})")

        except Exception as e:
            # Не падаем если не удалось сохранить триггер
            logger.warning(f"Failed to detect/save trigger: {e}")
