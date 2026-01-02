"""
Message handler.
Основной обработчик текстовых и фото сообщений.
"""

import traceback
import base64
import random
import re
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
from database.repositories.admin_log import AdminLogRepository
from services.referral import ReferralService
from utils.system_logger import system_logger
from utils.event_tracker import event_tracker
from bot.keyboards.inline import get_premium_keyboard, get_crisis_keyboard, get_hints_keyboard
from bot.handlers.photos import send_photos
from bot.handlers.music import (
    check_and_send_music,
    check_and_send_music_by_emotion,
    detect_music_request,
)
from ai.hint_generator import hint_generator
from utils.text_parser import extract_name_from_text
from utils.sanitizer import sanitize_text, sanitize_name, validate_message
from services.sticker_sender import maybe_send_sticker
from services.music_forwarder import music_forwarder
from bot.handlers.payments import handle_promo_code_input
from services.storage.file_storage import file_storage_service
from services.tts_yandex import send_voice_message
from ai.crisis_protocol import (
    get_emergency_message,
    requires_emergency_message,
    detect_crisis_type,
)


# Инициализируем сервисы
claude = ClaudeClient()
user_repo = UserRepository()
admin_log_repo = AdminLogRepository()
subscription_repo = SubscriptionRepository()
conversation_repo = ConversationRepository()
mood_repo = MoodRepository()
referral_service = ReferralService()


def parse_inline_buttons(text: str) -> tuple[str, list[list[InlineKeyboardButton]] | None]:
    """
    Парсит текст на наличие [buttons:opt1|opt2|opt3] и возвращает
    очищенный текст и кнопки.

    Returns:
        (clean_text, buttons) - текст без маркера и список кнопок или None
    """
    # Ищем паттерн [buttons:опция1|опция2|опция3]
    pattern = r'\[buttons?:([^\]]+)\]'
    match = re.search(pattern, text)

    if not match:
        return text, None

    # Извлекаем опции
    options_str = match.group(1)
    options = [opt.strip() for opt in options_str.split('|') if opt.strip()]

    if not options:
        return text, None

    # Создаём кнопки (callback_data = текст кнопки)
    buttons = []
    row = []
    for i, option in enumerate(options[:4]):  # Максимум 4 кнопки
        # callback_data не может быть длиннее 64 байт
        callback_data = option[:60]
        row.append(InlineKeyboardButton(option, callback_data=f"choice:{callback_data}"))
        # По 2 кнопки в ряд
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Убираем маркер из текста
    clean_text = re.sub(pattern, '', text).strip()

    return clean_text, buttons


def parse_voice_marker(text: str) -> tuple[str, str | None]:
    """
    Парсит текст на наличие [voice:текст для озвучки] и возвращает
    очищенный текст и текст для голосового сообщения.

    Returns:
        (clean_text, voice_text) - текст без маркера и текст для TTS или None
    """
    # Ищем паттерн [voice:текст для озвучки]
    pattern = r'\[voice:([^\]]+)\]'
    match = re.search(pattern, text)

    if not match:
        return text, None

    # Извлекаем текст для озвучки
    voice_text = match.group(1).strip()

    if not voice_text:
        return text, None

    # Убираем маркер из текста
    clean_text = re.sub(pattern, '', text).strip()

    return clean_text, voice_text


def detect_voice_request(text: str) -> bool:
    """
    Проверяет, является ли текст запросом услышать голос Миры.

    Returns:
        True если пользователь хочет услышать голос
    """
    text_lower = text.lower()

    voice_keywords = [
        "хочу услышать твой голос",
        "хочу слышать твой голос",
        "хочу твой голос",
        "скажи голосом",
        "запиши голосовое",
        "отправь голосовое",
        "пришли голосовое",
        "можешь сказать голосом",
        "скажи мне голосом",
        "говори голосом",
        "ответь голосом",
        "хочу голосовое",
        "дай голосовое",
        "запиши войс",
        "пришли войс",
    ]

    return any(kw in text_lower for kw in voice_keywords)


async def _get_fresh_user_data(user) -> dict:
    """
    Получает актуальные данные пользователя из БД.
    ВАЖНО: Всегда перечитывает display_name из БД, чтобы учесть изменения.
    """
    fresh_user = await user_repo.get(user.id)
    return {
        "persona": user.persona,
        "display_name": fresh_user.display_name if fresh_user else user.display_name,
        "partner_name": user.partner_name,
        "children_info": user.children_info,
        "marriage_years": user.marriage_years,
        "partner_gender": getattr(user, "partner_gender", None),
        "communication_style": getattr(user, "communication_style", None),
    }


def _get_opening_question() -> str:
    """
    Возвращает приветственный вопрос в зависимости от времени суток.
    Добавляет разнообразие и делает общение более естественным.
    """
    from datetime import datetime

    hour = datetime.now().hour

    # Утро (6:00 - 11:59)
    if 6 <= hour < 12:
        questions = [
            "Как начался день?",
            "Как утро?",
            "Что на душе сегодня?",
        ]
    # День (12:00 - 17:59)
    elif 12 <= hour < 18:
        questions = [
            "Как дела?",
            "Как день проходит?",
            "Что у тебя на душе?",
        ]
    # Вечер (18:00 - 22:59)
    elif 18 <= hour < 23:
        questions = [
            "Как прошёл день?",
            "Как дела сегодня?",
            "О чём думаешь?",
        ]
    # Ночь (23:00 - 5:59)
    else:
        questions = [
            "Не спится?",
            "Что не даёт уснуть?",
            "О чём думаешь?",
        ]

    return random.choice(questions)


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

    # Проверяем ожидание ввода промо-кода
    if await handle_promo_code_input(update, context):
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

        # 3.6. Проверяем запрос музыки - НЕ перехватываем, пусть Claude отвечает с кнопками
        # Если пользователь просит музыку, Claude ответит с [buttons:...] для выбора жанра
        # Кнопки обрабатываются в callbacks.py -> _handle_choice_callback

        # 4. Проверяем лимиты
        subscription = await subscription_repo.get_active(user.id)
        is_premium = subscription and subscription.plan in ("premium", "trial")
        
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
        # ВАЖНО: Всегда получаем актуальные данные из БД (включая display_name)
        user_data = await _get_fresh_user_data(user)

        # 6.5. Добавляем контекст последнего фото если есть
        # Это помогает Claude понимать вопросы вроде "Сколько ему?" после показа фото
        last_photo_context = context.user_data.get("last_photo_context")
        if last_photo_context:
            user_data["last_photo_sent"] = last_photo_context
            # Очищаем контекст после использования
            context.user_data.pop("last_photo_context", None)

        # 6.6. Проверяем запрос услышать голос Миры
        if detect_voice_request(message_text):
            user_data["voice_requested"] = True
            logger.debug(f"Voice request detected for user {user_tg.id}")

        # 6.7. КРИЗИСНЫЙ ПРОТОКОЛ — проверка перед ответом Claude
        from ai.crisis_detector import CrisisDetector
        crisis_detector = CrisisDetector()
        crisis_check = crisis_detector.check(message_text)

        # Если обнаружен кризис высокого уровня — отправляем экстренное сообщение НЕМЕДЛЕННО
        if requires_emergency_message(crisis_check.get("level")):
            crisis_type = detect_crisis_type(crisis_check.get("matched_keywords", []))
            emergency_text = get_emergency_message(
                crisis_level=crisis_check["level"],
                crisis_type=crisis_type
            )

            if emergency_text:
                # Отправляем экстренное сообщение ДО ответа Claude
                await update.message.reply_text(
                    emergency_text,
                    parse_mode="Markdown"
                )
                logger.warning(
                    f"CRISIS ALERT: Level={crisis_check['level']}, "
                    f"Type={crisis_type}, User={user_tg.id}"
                )

        # 6.8. НОВОЕ: Анализ настроения ПЕРЕД Claude (для смешанных эмоций)
        from ai.mood_analyzer import mood_analyzer

        mood_analysis = mood_analyzer.analyze(message_text)
        current_mood = {
            "mood_score": mood_analysis.mood_score,
            "primary_emotion": mood_analysis.primary_emotion,
            "secondary_emotions": mood_analysis.secondary_emotions,
            "energy_level": mood_analysis.energy_level,
            "anxiety_level": mood_analysis.anxiety_level,
            "triggers": mood_analysis.triggers,
            "confidence": mood_analysis.confidence,
        }

        # Добавляем текущее настроение в user_data для промпта
        user_data["current_mood"] = current_mood

        logger.debug(
            f"Mood analyzed: {mood_analysis.primary_emotion} "
            f"(secondary: {mood_analysis.secondary_emotions}), "
            f"score: {mood_analysis.mood_score}"
        )

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

        # 8.3. Трекаем вехи по количеству сообщений
        try:
            milestone = await event_tracker.track_message_milestone(user)
            if milestone:
                logger.info(f"User {user_tg.id} reached milestone: {milestone} messages")
        except Exception as e:
            logger.warning(f"Failed to track message milestone: {e}")

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

        # 8.7. Музыка отключена
        # try:
        #     await _maybe_send_music(
        #         update=update,
        #         context=context,
        #         mira_response=result["response"],
        #         user_message=message_text,
        #         mood=primary_mood,
        #     )
        # except Exception as e:
        #     logger.debug(f"Music send error: {e}")

        # 9. Добавляем кнопки при кризисе (если streaming уже отправил текст)
        if result["is_crisis"]:
            # Используем уровень кризиса из детектора
            crisis_level = crisis_check.get("level", "medium")
            keyboard = get_crisis_keyboard(crisis_level=crisis_level)

            # Отправляем кнопки только если НЕ отправляли экстренное сообщение
            # (для critical/high уровня экстренное сообщение уже содержит контакты)
            if crisis_level not in ["critical", "high"]:
                await update.message.reply_text(
                    "💛 Если нужна помощь прямо сейчас:",
                    reply_markup=keyboard,
                )

        # 9.5. Контекстные подсказки (20% шанс, только при вопросах)
        response_text = result["response"]
        # Показываем подсказки только если Мира задала вопрос и рандом < 20%
        if (not result["is_crisis"] and
            response_text.rstrip().endswith("?") and
            random.random() < 0.20):
            message_count = await conversation_repo.count_by_user(user.id)
            hints = hint_generator.generate(
                response_text=response_text,
                tags=result["tags"],
                mood_data=mood_entry,
                message_count=message_count,
                communication_style=user.communication_style,
                user_message=message_text,  # ВАЖНО: передаём текст пользователя для контекстной проверки
            )
            if hints:
                context.user_data["current_hints"] = [
                    {"text": h.text, "message": h.message}
                    for h in hints
                ]
                keyboard = get_hints_keyboard(hints)
                await update.message.reply_text("💬", reply_markup=keyboard)

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
    import asyncio

    # 1. Реалистичная задержка перед ответом (имитация "думает")
    delay = random.uniform(1.0, 5.0)

    # Показываем "typing..." во время задержки
    await update.message.chat.send_action("typing")
    await asyncio.sleep(delay)

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

        # Проверяем на наличие inline-кнопок [buttons:...]
        clean_text, buttons = parse_inline_buttons(final_text)
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

        # Проверяем на наличие голосового маркера [voice:...]
        clean_text, voice_text = parse_voice_marker(clean_text)

        if clean_text != last_sent_text:
            try:
                await bot_message.edit_text(
                    clean_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.debug(f"Final stream update error: {e}")
                # Попробуем без Markdown если ошибка парсинга
                try:
                    await bot_message.edit_text(
                        clean_text,
                        reply_markup=reply_markup,
                    )
                except Exception:
                    # Если не удалось отредактировать — отправляем новое сообщение
                    if not last_sent_text:
                        await update.message.reply_text(
                            clean_text,
                            reply_markup=reply_markup,
                        )

        # Отправляем голосовое сообщение если есть маркер
        if voice_text:
            try:
                await send_voice_message(
                    bot=update.get_bot(),
                    chat_id=update.effective_chat.id,
                    text=voice_text,
                    user_id=user_id,
                )
                logger.info(f"Voice message sent to {update.effective_user.id}")
            except Exception as e:
                logger.warning(f"Failed to send voice message: {e}")

        # Обновляем результат без маркеров кнопок (для сохранения в историю)
        result["response"] = clean_text
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

        # Проверяем, был ли пользователь приглашён по реферальной ссылке
        # Если да - отправляем уведомление рефереру
        try:
            from database.repositories.referral import ReferralRepository
            from services.referral import ReferralService

            referral_repo = ReferralRepository()
            referral_service = ReferralService()

            # Проверяем есть ли реферал для этого пользователя
            referral = await referral_repo.get_by_referred(user.id)
            if referral and referral.referrer_id:
                # Отправляем уведомление рефереру
                await referral_service.notify_referrer_about_friend(
                    referrer_id=referral.referrer_id,
                    friend_name=display_name
                )
        except Exception as e:
            logger.error(f"Failed to notify referrer: {e}")

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

            # Логируем завершение онбоардинга
            try:
                # Получаем информацию о реферале
                from database.repositories.referral import ReferralRepository
                referral_repo = ReferralRepository()
                referral = await referral_repo.get_by_referred_id(user.id)

                referrer_telegram_id = None
                referrer_username = None
                if referral and referral.referrer:
                    referrer_telegram_id = referral.referrer.telegram_id
                    referrer_username = referral.referrer.username

                await system_logger.log_user_onboarding_completed(
                    user_id=user.id,
                    telegram_id=user.telegram_id,
                    username=user.username,
                    first_name=user.first_name or "Unknown",
                    referrer_telegram_id=referrer_telegram_id,
                    referrer_username=referrer_username,
                )
            except Exception as e:
                logger.warning(f"Failed to log onboarding completion for user {user.telegram_id}: {e}")

            display_name = user.display_name or "дорогая"
            opening_question = _get_opening_question()

            text = f"""Хорошо, {display_name} 💛

Просто буду рядом. Можешь писать или отправлять голосовые 🎤

{opening_question}"""

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

        # Логируем завершение онбоардинга
        try:
            # Получаем информацию о реферале
            from database.repositories.referral import ReferralRepository
            referral_repo = ReferralRepository()
            referral = await referral_repo.get_by_referred_id(user.id)

            referrer_telegram_id = None
            referrer_username = None
            if referral and referral.referrer:
                referrer_telegram_id = referral.referrer.telegram_id
                referrer_username = referral.referrer.username

            await system_logger.log_user_onboarding_completed(
                user_id=user.id,
                telegram_id=user.telegram_id,
                username=user.username,
                first_name=user.first_name or "Unknown",
                referrer_telegram_id=referrer_telegram_id,
                referrer_username=referrer_username,
            )
        except Exception as e:
            logger.warning(f"Failed to log onboarding completion for user {user.telegram_id}: {e}")

        display_name = user.display_name or "дорогая"
        opening_question = _get_opening_question()

        text = f"""{display_name}, спасибо что поделилась 💛

Просто буду рядом. Можешь писать или отправлять голосовые 🎤

{opening_question}"""

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
        is_premium = subscription and subscription.plan in ("premium", "trial")

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

        # 6.1 Сохраняем в GCS (в фоне, не блокируем ответ)
        try:
            await file_storage_service.save_photo(
                photo_bytes=bytes(photo_bytes),
                user_id=user.id,
                telegram_id=user_tg.id,
                telegram_file_id=photo.file_id,
                file_size=photo.file_size or len(photo_bytes),
                message_id=update.message.message_id,
            )
        except Exception as e:
            logger.warning(f"Failed to save photo to GCS for user {user_tg.id}: {e}")

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
        user_data = await _get_fresh_user_data(user)

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

        # 12. Трекаем первое фото и вехи по сообщениям
        try:
            # Проверяем это первое фото
            await event_tracker.track_first_photo_message(user)
        except Exception as e:
            logger.warning(f"Failed to track first photo message: {e}")

        try:
            # Проверяем вехи по количеству сообщений
            milestone = await event_tracker.track_message_milestone(user)
            if milestone:
                logger.info(f"User {user_tg.id} reached milestone: {milestone} messages")
        except Exception as e:
            logger.warning(f"Failed to track message milestone: {e}")

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
    Отправляет музыку если Мира ЯВНО включает её в ответе.

    Музыка отправляется ТОЛЬКО когда Мира использует action-маркеры:
    - *включаю*, *ставлю*, *отправляю* и т.п.

    НЕ отправляется когда Мира просто упоминает музыку или спрашивает
    "хочешь музыку?"

    Returns:
        True если музыка была отправлена
    """
    import re

    response_lower = mira_response.lower()

    # ВАЖНО: Музыка отправляется ТОЛЬКО при явном action от Миры
    # Паттерны с action-маркерами (* или действие в настоящем времени)
    music_action_patterns = [
        r"\*включаю",      # *включаю музыку*
        r"\*ставлю",       # *ставлю трек*
        r"\*отправляю",    # *отправляю песню*
        r"\*переключаю",   # *переключаю на...*
        r"\*лови",         # *лови трек*
        r"\*держи",        # *держи музыку*
        r"лови!",          # Лови! (явная отправка)
        r"держи!",         # Держи! (явная отправка)
        r"включаю тебе",   # Включаю тебе...
        r"ставлю тебе",    # Ставлю тебе...
    ]

    # Проверяем только action-паттерны (явное действие)
    offers_music = any(re.search(pattern, response_lower) for pattern in music_action_patterns)

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
