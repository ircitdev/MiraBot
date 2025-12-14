"""
Message handler.
Основной обработчик текстовых и фото сообщений.
"""

import traceback
import base64
import anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger
from datetime import datetime

from config.settings import settings
from ai.claude_client import ClaudeClient
from ai.mood_analyzer import mood_analyzer
from database.repositories.user import UserRepository
from database.repositories.subscription import SubscriptionRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.mood import MoodRepository
from services.referral import ReferralService
from bot.keyboards.inline import get_premium_keyboard, get_crisis_keyboard, get_hints_keyboard
from bot.handlers.photos import send_photos
from bot.handlers.music import check_and_send_music, detect_music_request
from ai.hint_generator import hint_generator
from utils.text_parser import extract_name_from_text
from utils.sanitizer import sanitize_text, sanitize_name, validate_message
from services.sticker_sender import maybe_send_sticker
from services.music_forwarder import music_forwarder


# Инициализируем сервисы
claude = ClaudeClient()
user_repo = UserRepository()
subscription_repo = SubscriptionRepository()
conversation_repo = ConversationRepository()
mood_repo = MoodRepository()
referral_service = ReferralService()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Основной обработчик текстовых сообщений."""

    user_tg = update.effective_user
    raw_text = update.message.text

    # Валидация и санитизация входных данных
    is_valid, message_text, error = validate_message(raw_text)
    if not is_valid:
        logger.warning(f"Invalid message from {user_tg.id}: {error}")
        await update.message.reply_text(
            "Не удалось обработать сообщение. Попробуй ещё раз 💛"
        )
        return

    try:
        # 1. Получаем пользователя
        user, _ = await user_repo.get_or_create(
            telegram_id=user_tg.id,
            username=user_tg.username,
            first_name=user_tg.first_name,
        )
        
        # 2. Проверяем блокировку
        if user.is_blocked:
            await update.message.reply_text(
                "К сожалению, доступ ограничен. "
                "Если считаешь, что это ошибка — напиши в поддержку."
            )
            return
        
        # 3. Проверяем онбординг
        if not user.onboarding_completed:
            await _handle_onboarding(update, context, user, message_text)
            return

        # 3.5. Проверяем запрос на фотографии
        user_data_for_photos = {"sent_photos": user.sent_photos or []}
        if await send_photos(update, context, user_data_for_photos):
            # Сохраняем отправленные фото
            new_sent = context.user_data.get("new_sent_photos", [])
            if new_sent:
                current_sent = user.sent_photos or []
                updated_sent = current_sent + new_sent
                await user_repo.update(user.id, sent_photos=updated_sent)
            return

        # 3.6. Проверяем запрос музыки
        if detect_music_request(message_text):
            music_sent = await check_and_send_music(update, context, message_text)
            if music_sent:
                return

        # 4. Проверяем лимиты
        subscription = await subscription_repo.get_active(user.id)
        is_premium = subscription and subscription.plan == "premium"
        
        if not is_premium:
            # Проверяем дневной лимит
            if subscription and subscription.messages_today >= settings.FREE_MESSAGES_PER_DAY:
                await _send_limit_reached(update)
                return
            
            # Увеличиваем счётчик
            if subscription:
                await subscription_repo.increment_messages(subscription.id)
        
        # 5. Обновляем last_active
        await user_repo.update_last_active(user.id)
        
        # 6. Подготавливаем данные пользователя
        user_data = {
            "persona": user.persona,
            "display_name": user.display_name,
            "partner_name": user.partner_name,
            "children_info": user.children_info,
            "marriage_years": user.marriage_years,
            "partner_gender": getattr(user, "partner_gender", None),
            "communication_style": user.communication_style,
        }

        # 7. Streaming ответ от Claude
        result = await _generate_and_stream_response(
            update=update,
            user_id=user.id,
            message_text=message_text,
            user_data=user_data,
            is_premium=is_premium,
        )

        # 8. Сохраняем сообщения
        user_message_saved = await conversation_repo.save_message(
            user_id=user.id,
            role="user",
            content=message_text,
            tags=[],
        )

        await conversation_repo.save_message(
            user_id=user.id,
            role="assistant",
            content=result["response"],
            tags=result["tags"],
            tokens_used=result["tokens_used"],
        )

        # 8.5. Mood tracking — анализируем и сохраняем настроение
        mood_entry = await _save_mood_entry(
            user_id=user.id,
            message_id=user_message_saved.id if user_message_saved else None,
            message_text=message_text,
            context_tags=result["tags"],
        )

        # 8.6. Отправляем стикер если уместно (по контексту ответа Миры)
        primary_mood = mood_entry.get("primary_emotion") if mood_entry else None
        try:
            await maybe_send_sticker(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                mira_response=result["response"],
                user_message=message_text,
                mood=primary_mood,
            )
        except Exception as e:
            logger.debug(f"Sticker send error: {e}")

        # 8.7. Отправляем музыку если Мира предложила
        try:
            await _maybe_send_music(
                update=update,
                context=context,
                mira_response=result["response"],
                user_message=message_text,
                mood=primary_mood,
            )
        except Exception as e:
            logger.debug(f"Music send error: {e}")

        # 9. Добавляем кнопки при кризисе (если streaming уже отправил текст)
        if result["is_crisis"]:
            keyboard = get_crisis_keyboard()
            await update.message.reply_text(
                "💛 Если нужна помощь прямо сейчас:",
                reply_markup=keyboard,
            )

        # 9.5. Контекстные подсказки (кнопки быстрых ответов)
        if not result["is_crisis"]:
            # Получаем количество сообщений для контекста
            message_count = await conversation_repo.count_by_user(user.id)

            # Генерируем подсказки с учётом настроения и стиля общения
            hints = hint_generator.generate(
                response_text=result["response"],
                tags=result["tags"],
                mood_data=mood_entry,
                message_count=message_count,
                communication_style=user.communication_style,
            )

            if hints:
                # Сохраняем подсказки в context для callback обработчика
                context.user_data["current_hints"] = [
                    {"text": h.text, "message": h.message}
                    for h in hints
                ]

                # Отправляем кнопки
                keyboard = get_hints_keyboard(hints)
                await update.message.reply_text(
                    "💬",
                    reply_markup=keyboard,
                )

        # 10. Проверяем триггеры реферала
        if not is_premium:
            await _check_referral_trigger(update, user, result)
        
        logger.info(
            f"Message processed for user {user_tg.id}, "
            f"tokens={result['tokens_used']}, "
            f"is_crisis={result['is_crisis']}"
        )
        
    except anthropic.APIConnectionError as e:
        # Ошибка подключения к API Claude
        logger.error(f"Claude API connection error for user {user_tg.id}: {e}")
        logger.debug(traceback.format_exc())

        # Сохраняем сообщение пользователя, чтобы не потерять контекст
        try:
            await conversation_repo.save_message(
                user_id=user.id,
                role="user",
                content=message_text,
                tags=["error:api_connection"],
            )
        except Exception as save_err:
            logger.error(f"Failed to save message on error: {save_err}")

        await update.message.reply_text(
            "Не могу связаться с сервером... Попробуй через пару минут 💛"
        )

    except anthropic.RateLimitError as e:
        # Превышен лимит запросов к Claude
        logger.warning(f"Claude rate limit for user {user_tg.id}: {e}")

        try:
            await conversation_repo.save_message(
                user_id=user.id,
                role="user",
                content=message_text,
                tags=["error:rate_limit"],
            )
        except Exception as save_err:
            logger.error(f"Failed to save message on error: {save_err}")

        await update.message.reply_text(
            "Сейчас много запросов, подожди минутку и напиши снова 💛"
        )

    except anthropic.APIStatusError as e:
        # Другие ошибки API Claude
        logger.error(f"Claude API error for user {user_tg.id}: {e.status_code} - {e.message}")
        logger.debug(traceback.format_exc())

        try:
            await conversation_repo.save_message(
                user_id=user.id,
                role="user",
                content=message_text,
                tags=["error:api_status"],
            )
        except Exception as save_err:
            logger.error(f"Failed to save message on error: {save_err}")

        await update.message.reply_text(
            "Что-то пошло не так на сервере... Попробуй ещё раз через минутку 💛"
        )

    except Exception as e:
        # Неизвестная ошибка
        logger.error(f"Unexpected error for user {user_tg.id}: {e}")
        logger.error(traceback.format_exc())

        # Пытаемся сохранить сообщение пользователя
        try:
            if 'user' in locals() and user:
                await conversation_repo.save_message(
                    user_id=user.id,
                    role="user",
                    content=message_text,
                    tags=["error:unknown"],
                )
        except Exception as save_err:
            logger.error(f"Failed to save message on error: {save_err}")

        await update.message.reply_text(
            "Прости, что-то пошло не так... Попробуй ещё раз через минутку 💛"
        )


# Настройки streaming
STREAM_UPDATE_INTERVAL = 1.0  # секунд между обновлениями сообщения
STREAM_MIN_CHARS = 20  # минимум символов для первого обновления


async def _generate_and_stream_response(
    update: Update,
    user_id: int,
    message_text: str,
    user_data: dict,
    is_premium: bool,
) -> dict:
    """
    Генерирует ответ Claude и стримит его пользователю.
    Редактирует сообщение по мере получения текста.
    """
    import time

    # Отправляем начальное сообщение
    bot_message = await update.message.reply_text("⏳")

    # Состояние для streaming
    current_text = ""
    last_update_time = time.time()
    last_sent_text = ""

    async def update_message(chunk: str):
        """Callback для обновления сообщения при получении чанка."""
        nonlocal current_text, last_update_time, last_sent_text

        current_text += chunk
        current_time = time.time()

        # Обновляем сообщение:
        # - если прошло достаточно времени
        # - и есть достаточно нового текста
        should_update = (
            current_time - last_update_time >= STREAM_UPDATE_INTERVAL
            and len(current_text) >= STREAM_MIN_CHARS
            and current_text != last_sent_text
        )

        if should_update:
            try:
                # Добавляем курсор "▌" для эффекта печати
                display_text = current_text + " ▌"
                await bot_message.edit_text(display_text)
                last_sent_text = current_text
                last_update_time = current_time
            except Exception as e:
                # Игнорируем ошибки редактирования (rate limit, message not modified)
                logger.debug(f"Stream update error: {e}")

    try:
        # Получаем streaming ответ
        result = await claude.generate_response_stream(
            user_id=user_id,
            user_message=message_text,
            user_data=user_data,
            is_premium=is_premium,
            on_chunk=update_message,
        )

        # Финальное обновление — убираем курсор, показываем полный текст
        final_text = result["response"]
        if final_text != last_sent_text:
            try:
                await bot_message.edit_text(final_text)
            except Exception as e:
                logger.debug(f"Final stream update error: {e}")
                # Если не удалось отредактировать — отправляем новое сообщение
                if not last_sent_text:
                    await update.message.reply_text(final_text)

        return result

    except Exception as e:
        # При ошибке удаляем сообщение-заглушку
        try:
            await bot_message.delete()
        except Exception:
            pass
        raise


async def _handle_onboarding(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user,
    message_text: str,
) -> None:
    """Обработка сообщений во время онбординга."""

    step = user.onboarding_step

    if step == 1:
        # Ожидаем имя пользователя
        display_name = extract_name_from_text(message_text)

        if not display_name:
            await update.message.reply_text(
                "Как мне к тебе обращаться? Напиши своё имя 💛"
            )
            return

        # Санитизируем имя
        display_name = sanitize_name(display_name, max_length=50)

        if not display_name:
            await update.message.reply_text(
                "Как мне к тебе обращаться? Напиши своё имя 💛"
            )
            return

        await user_repo.update(
            user.id,
            display_name=display_name,
            onboarding_step=2,
        )

        text = f"""{display_name}, очень приятно 💛

Можешь рассказать немного о себе? Есть ли у тебя партнёр/муж?

Если хочешь — напиши его имя. Или напиши "пропустить", если не хочешь об этом сейчас."""

        await update.message.reply_text(text)

    elif step == 2:
        # Ожидаем имя партнёра или "пропустить"
        text_lower = message_text.strip().lower()

        # Проверяем пропуск
        skip_words = ["пропустить", "пропуск", "skip", "нет", "не хочу", "-"]
        if any(word in text_lower for word in skip_words):
            await user_repo.update(
                user.id,
                onboarding_step=3,
                onboarding_completed=True,
            )

            display_name = user.display_name or "дорогая"
            text = f"""Хорошо, {display_name} 💛

Просто буду рядом. Можешь писать или отправлять голосовые 🎤

Расскажи, что тебя сюда привело? Или начни с чего угодно — как прошёл день, что на душе..."""

            await update.message.reply_text(text)
            return

        # Извлекаем имя партнёра
        partner_name = extract_name_from_text(message_text)

        if not partner_name:
            # Попробуем взять текст как есть, если он короткий
            if len(message_text.strip()) <= 20 and message_text.strip().isalpha():
                partner_name = message_text.strip().capitalize()
            else:
                await update.message.reply_text(
                    "Как зовут твоего партнёра? Напиши имя или \"пропустить\" 💛"
                )
                return

        # Санитизируем имя партнёра
        partner_name = sanitize_name(partner_name, max_length=50)

        if not partner_name:
            await update.message.reply_text(
                "Как зовут твоего партнёра? Напиши имя или \"пропустить\" 💛"
            )
            return

        # Определяем пол по имени (эвристика для русских имён)
        partner_gender = _detect_gender_by_name(partner_name)

        await user_repo.update(
            user.id,
            partner_name=partner_name,
            partner_gender=partner_gender,
            onboarding_step=3,
            onboarding_completed=True,
        )

        display_name = user.display_name or "дорогая"
        text = f"""{display_name}, спасибо что поделилась 💛

Просто буду рядом. Можешь писать или отправлять голосовые 🎤

Расскажи, что тебя сюда привело? Или начни с чего угодно — как прошёл день, что на душе..."""

        await update.message.reply_text(text)

    else:
        # Неожиданное состояние — отправляем на выбор персоны
        from bot.handlers.start import _start_onboarding
        await _start_onboarding(update, user)


def _detect_gender_by_name(name: str) -> str:
    """
    Определяет пол по русскому имени.
    Эвристика: имена на -а/-я обычно женские (кроме исключений).
    """
    name_lower = name.lower().strip()

    # Явно мужские имена (исключения на -а/-я)
    male_names = {
        "саша", "женя", "никита", "илья", "данила", "лёша", "лёня",
        "ваня", "коля", "толя", "митя", "гоша", "паша", "миша", "гриша",
        "костя", "петя", "федя", "серёжа", "вова", "дима", "лёва",
    }

    # Явно женские имена
    female_names = {
        "оля", "катя", "маша", "даша", "наташа", "таня", "аня", "юля",
        "света", "лена", "ира", "вика", "настя", "кристина", "марина",
    }

    if name_lower in male_names:
        return "male"

    if name_lower in female_names:
        return "female"

    # Общая эвристика: окончание на -а/-я = женское
    if name_lower.endswith(("а", "я")):
        return "female"

    # По умолчанию — мужское
    return "male"


async def _send_limit_reached(update: Update) -> None:
    """Отправляет сообщение о достижении лимита."""
    
    text = """Наш разговор сегодня подходит к паузе... 
Но я здесь, и завтра мы продолжим 💛

Если хочешь общаться без ограничений — есть премиум-доступ."""
    
    keyboard = get_premium_keyboard()
    await update.message.reply_text(text, reply_markup=keyboard)


async def _save_mood_entry(
    user_id: int,
    message_id: int | None,
    message_text: str,
    context_tags: list,
) -> dict | None:
    """
    Анализирует настроение и сохраняет в БД.
    Возвращает данные о настроении для использования в подсказках.
    """
    try:
        # Анализируем текст
        mood_analysis = mood_analyzer.analyze(message_text)

        # Сохраняем только если уверенность достаточная
        if mood_analysis.confidence < 0.3:
            return None

        await mood_repo.create(
            user_id=user_id,
            message_id=message_id,
            mood_score=mood_analysis.mood_score,
            primary_emotion=mood_analysis.primary_emotion,
            energy_level=mood_analysis.energy_level,
            anxiety_level=mood_analysis.anxiety_level,
            secondary_emotions=mood_analysis.secondary_emotions,
            triggers=mood_analysis.triggers,
            context_tags=context_tags,
        )

        logger.debug(
            f"Mood saved for user {user_id}: "
            f"score={mood_analysis.mood_score}, emotion={mood_analysis.primary_emotion}"
        )

        # Возвращаем данные для использования в подсказках
        return {
            "primary_emotion": mood_analysis.primary_emotion,
            "mood_score": mood_analysis.mood_score,
            "anxiety_level": mood_analysis.anxiety_level,
            "energy_level": mood_analysis.energy_level,
        }

    except Exception as e:
        # Ошибки mood tracking не должны ломать основной флоу
        logger.warning(f"Failed to save mood entry: {e}")
        return None


async def _check_referral_trigger(update: Update, user, result: dict) -> None:
    """Проверяет, нужно ли предложить реферальную программу."""
    
    # Не показываем при кризисе
    if result["is_crisis"]:
        return
    
    # Показываем при инсайтах или позитивных сигналах
    should_show = False
    
    if "insight" in result["tags"]:
        should_show = True
    
    if "positive" in result["tags"]:
        should_show = True
    
    if not should_show:
        return
    
    # Проверяем, не показывали ли недавно (через context или БД)
    # Пока простая логика — показываем редко
    import random
    if random.random() > 0.2:  # 20% шанс
        return
    
    # Получаем реферальный код
    code = await referral_service.get_or_create_code(user.id)
    
    if "insight" in result["tags"]:
        text = f"""💛 Рада, что удалось увидеть что-то новое.

Если у тебя есть подруга, которой тоже нужно безопасное место выговориться — можешь поделиться.

Ваш код: `{code}`
Вам обеим будет +7 дней без ограничений 🎁"""
    else:
        text = f"""💛 Если знаешь кого-то, кому тоже не с кем поговорить — можешь пригласить.

Ваш код: `{code}`"""
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик фотографий от пользователей.
    Скачивает фото, конвертирует в base64 и отправляет Claude для анализа.
    """
    user_tg = update.effective_user
    caption = update.message.caption  # Подпись к фото (если есть)

    try:
        # 1. Получаем пользователя
        user, _ = await user_repo.get_or_create(
            telegram_id=user_tg.id,
            username=user_tg.username,
            first_name=user_tg.first_name,
        )

        # 2. Проверяем блокировку
        if user.is_blocked:
            await update.message.reply_text(
                "К сожалению, доступ ограничен. "
                "Если считаешь, что это ошибка — напиши в поддержку."
            )
            return

        # 3. Проверяем онбординг
        if not user.onboarding_completed:
            await update.message.reply_text(
                "Давай сначала познакомимся! Напиши мне своё имя 💛"
            )
            return

        # 4. Проверяем лимиты
        subscription = await subscription_repo.get_active(user.id)
        is_premium = subscription and subscription.plan == "premium"

        if not is_premium:
            if subscription and subscription.messages_today >= settings.FREE_MESSAGES_PER_DAY:
                await _send_limit_reached(update)
                return
            if subscription:
                await subscription_repo.increment_messages(subscription.id)

        # 5. Обновляем last_active
        await user_repo.update_last_active(user.id)

        # 6. Скачиваем фото (берём самое большое разрешение)
        photo = update.message.photo[-1]  # Последний элемент = максимальное разрешение
        file = await context.bot.get_file(photo.file_id)

        # Скачиваем в байты
        photo_bytes = await file.download_as_bytearray()

        # Конвертируем в base64
        image_base64 = base64.b64encode(photo_bytes).decode("utf-8")

        # Определяем MIME тип (Telegram всегда отправляет JPEG)
        media_type = "image/jpeg"

        # 7. Отправляем "печатает..."
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )

        # 8. Подготавливаем данные пользователя
        user_data = {
            "persona": user.persona,
            "display_name": user.display_name,
            "partner_name": user.partner_name,
            "children_info": user.children_info,
            "marriage_years": user.marriage_years,
            "partner_gender": getattr(user, "partner_gender", None),
        }

        # 9. Генерируем ответ на фото через Claude
        result = await claude.generate_response_with_image(
            user_id=user.id,
            image_base64=image_base64,
            media_type=media_type,
            caption=caption,
            user_data=user_data,
            is_premium=is_premium,
        )

        # 10. Отправляем ответ
        await update.message.reply_text(result["response"])

        # 11. Сохраняем сообщения в историю
        # Сохраняем сообщение пользователя (отмечаем что это фото)
        photo_description = "[Пользователь отправил фото]"
        if caption:
            photo_description += f" с подписью: {caption}"

        await conversation_repo.save_message(
            user_id=user.id,
            role="user",
            content=photo_description,
            tags=["photo"],
        )

        await conversation_repo.save_message(
            user_id=user.id,
            role="assistant",
            content=result["response"],
            tags=result.get("tags", ["photo"]),
            tokens_used=result.get("tokens_used", 0),
        )

        logger.info(
            f"Photo processed for user {user_tg.id}, "
            f"tokens={result.get('tokens_used', 0)}"
        )

    except anthropic.APIConnectionError as e:
        logger.error(f"Claude API connection error (photo) for user {user_tg.id}: {e}")
        await update.message.reply_text(
            "Не могу связаться с сервером... Попробуй через пару минут 💛"
        )

    except anthropic.RateLimitError as e:
        logger.warning(f"Claude rate limit (photo) for user {user_tg.id}: {e}")
        await update.message.reply_text(
            "Сейчас много запросов, подожди минутку и напиши снова 💛"
        )

    except anthropic.APIStatusError as e:
        logger.error(f"Claude API error (photo) for user {user_tg.id}: {e.status_code} - {e.message}")
        await update.message.reply_text(
            "Что-то пошло не так на сервере... Попробуй ещё раз 💛"
        )

    except Exception as e:
        logger.error(f"Unexpected error processing photo for user {user_tg.id}: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(
            "Прости, не получилось посмотреть фото... Попробуй ещё раз 💛"
        )


async def _maybe_send_music(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    mira_response: str,
    user_message: str,
    mood: str = None,
) -> bool:
    """
    Отправляет музыку если Мира предложила её в ответе.

    Returns:
        True если музыка была отправлена
    """
    response_lower = mira_response.lower()

    # Проверяем, предложила ли Мира музыку (корни слов для гибкого матчинга)
    music_offer_patterns = [
        "включ", "ставлю", "переключ",  # включу, включаю, ставлю, поставлю, переключаю
        "музык", "послушай", "трек", "мелоди", "песн",
        "🎧", "🎵", "🎸", "🌙", "🎤",
    ]

    offers_music = any(pattern in response_lower for pattern in music_offer_patterns)

    if not offers_music:
        return False

    logger.info(f"Music offer detected in response, determining topic...")

    # Определяем жанр по контексту
    chat_id = update.effective_chat.id

    # Инициализируем music_forwarder с ботом
    music_forwarder.set_bot(context.bot)

    # Определяем топик по контексту
    topic_key = _detect_music_topic(mira_response, user_message, mood)

    if not topic_key:
        return False

    # Пробуем отправить музыку
    success = await music_forwarder.forward_music(chat_id, topic_key)

    if success:
        logger.info(f"Music sent to {chat_id}, topic={topic_key}")

    return success


def _detect_music_topic(mira_response: str, user_message: str, mood: str = None) -> str:
    """Определяет подходящий топик музыки."""
    text = f"{mira_response} {user_message}".lower()

    # Романтика
    if any(w in text for w in ["романтик", "любовь", "близост", "интим", "страст", "свидани", "💋"]):
        return "sex"

    # Релакс
    if any(w in text for w in ["расслаб", "отдых", "спокойн", "релакс", "медитац", "🌙", "устал"]):
        return "lounge"

    # Энергия
    if any(w in text for w in ["энерги", "мотивац", "драйв", "работ", "концентр", "🎧"]):
        return "trance"

    # Злость
    if any(w in text for w in ["злост", "злюсь", "бесит", "ярост", "🎸"]):
        return "rock"

    # Веселье
    if any(w in text for w in ["весел", "праздник", "танц", "радост", "вечеринк", "🎤"]):
        return "pop"

    # По настроению
    if mood:
        mood_mapping = {
            "sad": "lounge",
            "angry": "rock",
            "happy": "pop",
            "romantic": "sex",
            "tired": "lounge",
            "excited": "trance",
        }
        if mood in mood_mapping:
            return mood_mapping[mood]

    # По умолчанию — хиты
    return "hits"
