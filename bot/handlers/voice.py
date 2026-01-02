"""
Voice message handler.
Обработчик голосовых сообщений с транскрибацией через Whisper.
"""

from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from config.settings import settings
from ai.whisper_client import whisper_client
from ai.claude_client import ClaudeClient
from database.repositories.user import UserRepository
from database.repositories.subscription import SubscriptionRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.api_cost import ApiCostRepository
from bot.keyboards.inline import get_premium_keyboard, get_crisis_keyboard
from services.storage.file_storage import file_storage_service
from services.tts_yandex import send_voice_message
from utils.event_tracker import event_tracker


# Инициализируем сервисы
claude = ClaudeClient()
user_repo = UserRepository()
subscription_repo = SubscriptionRepository()
conversation_repo = ConversationRepository()
api_cost_repo = ApiCostRepository()


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик голосовых сообщений."""

    user_tg = update.effective_user
    voice = update.message.voice

    # ВРЕМЕННО: Логирование file_id для медитаций
    logger.info(f"🎤 VOICE MESSAGE from {user_tg.id}")
    logger.info(f"   file_id: {voice.file_id}")
    logger.info(f"   duration: {voice.duration}s")
    logger.info(f"   file_size: {voice.file_size} bytes")

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
                "Сначала давай познакомимся! Напиши /start 💛"
            )
            return

        # 4. Проверяем наличие OpenAI API ключа
        if not settings.OPENAI_API_KEY:
            await update.message.reply_text(
                "Голосовые сообщения временно недоступны. "
                "Пожалуйста, напиши текстом 💛"
            )
            return

        # 5. Проверяем лимиты
        subscription = await subscription_repo.get_active(user.id)
        is_premium = subscription and subscription.plan == "premium"

        if not is_premium:
            if subscription and subscription.messages_today >= settings.FREE_MESSAGES_PER_DAY:
                await _send_limit_reached(update)
                return

            if subscription:
                await subscription_repo.increment_messages(subscription.id)

        # 6. Показываем статус
        status_message = await update.message.reply_text("🎤 Слушаю...")

        # 7. Скачиваем голосовое сообщение
        voice_file = await voice.get_file()
        voice_bytes = await voice_file.download_as_bytearray()

        # 7.1 Сохраняем в GCS
        try:
            await file_storage_service.save_voice(
                voice_bytes=bytes(voice_bytes),
                user_id=user.id,
                telegram_id=user_tg.id,
                telegram_file_id=voice.file_id,
                file_size=voice.file_size or len(voice_bytes),
                duration=voice.duration,
                message_id=update.message.message_id,
            )
        except Exception as e:
            logger.warning(f"Failed to save voice to GCS for user {user_tg.id}: {e}")

        # 8. Транскрибируем
        await status_message.edit_text("✍️ Расшифровываю...")

        transcribed_text, whisper_cost_info = await whisper_client.transcribe_bytes(
            bytes(voice_bytes),
            file_extension="ogg",
            language="ru",
            audio_duration_seconds=voice.duration,
        )

        # 8.1. Сохраняем расходы на транскрибацию
        if whisper_cost_info['cost_usd'] > 0:
            try:
                await api_cost_repo.create(
                    user_id=user.id,
                    provider='openai',
                    operation='speech_to_text',
                    cost_usd=whisper_cost_info['cost_usd'],
                    audio_seconds=whisper_cost_info['audio_seconds'],
                    model=whisper_cost_info['model'],
                )
                logger.info(
                    f"Logged Whisper API cost for user {user.id}: "
                    f"${whisper_cost_info['cost_usd']:.6f} "
                    f"({whisper_cost_info['audio_seconds']}s)"
                )
            except Exception as e:
                logger.error(f"Failed to log Whisper API cost: {e}")

        if not transcribed_text:
            await status_message.edit_text(
                "Не удалось распознать голосовое сообщение 😔\n"
                "Попробуй ещё раз или напиши текстом."
            )
            return

        # 9. Показываем распознанный текст
        await status_message.edit_text(f"💬 Ты сказал(а): «{transcribed_text}»")

        # 10. Обновляем last_active
        await user_repo.update_last_active(user.id)

        # 11. Показываем "печатает..."
        await update.message.chat.send_action("typing")

        # 12. Подготавливаем данные пользователя
        from bot.handlers.message import _get_fresh_user_data
        user_data = await _get_fresh_user_data(user)

        # 13. Получаем ответ от Claude
        result = await claude.generate_response(
            user_id=user.id,
            user_message=transcribed_text,
            user_data=user_data,
            is_premium=is_premium,
        )

        # 14. Сохраняем сообщения
        await conversation_repo.save_message(
            user_id=user.id,
            role="user",
            content=f"[Голосовое сообщение] {transcribed_text}",
            tags=["voice"],
            message_type="voice",
        )

        await conversation_repo.save_message(
            user_id=user.id,
            role="assistant",
            content=result["response"],
            tags=result["tags"],
            tokens_used=result["tokens_used"],
        )

        # 15. Отправляем ответ
        await _send_response(update, result)

        # 16. Проверяем это первое голосовое — отвечаем голосом!
        voice_count = await conversation_repo.count_by_user_and_type(user.id, "voice")
        if voice_count <= 1:
            # Логируем первое голосовое сообщение
            try:
                await event_tracker.track_first_voice_message(user, duration=voice.duration)
            except Exception as e:
                logger.warning(f"Failed to track first voice message: {e}")

            # Это первое голосовое сообщение — отвечаем голосом
            try:
                voice_response = (
                    f"Привет! Рада слышать твой голос. "
                    f"Теперь ты знаешь, что я тоже умею говорить. "
                    f"Можешь писать или отправлять голосовые — как тебе удобнее."
                )
                await send_voice_message(
                    bot=context.bot,
                    chat_id=update.effective_chat.id,
                    text=voice_response,
                    user_id=user.id,
                )
                logger.info(f"Sent first voice response to user {user_tg.id}")
            except Exception as e:
                logger.warning(f"Failed to send voice response: {e}")

        # 17. Проверяем вехи по количеству сообщений
        try:
            milestone = await event_tracker.track_message_milestone(user)
            if milestone:
                logger.info(f"User {user_tg.id} reached milestone: {milestone} messages")
        except Exception as e:
            logger.warning(f"Failed to track message milestone: {e}")

        logger.info(
            f"Voice message processed for user {user_tg.id}, "
            f"duration={voice.duration}s, "
            f"transcribed_len={len(transcribed_text)}, "
            f"tokens={result['tokens_used']}"
        )

    except Exception as e:
        logger.error(f"Error handling voice from {user_tg.id}: {e}")
        await update.message.reply_text(
            "Прости, что-то пошло не так... Попробуй ещё раз через минутку 💛"
        )


async def _send_response(update: Update, result: dict) -> None:
    """Отправляет ответ пользователю."""

    response_text = result["response"]
    parts = response_text.split("---")

    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue

        if result["is_crisis"] and i == len(parts) - 1:
            keyboard = get_crisis_keyboard()
            await update.message.reply_text(part, reply_markup=keyboard)
        else:
            await update.message.reply_text(part)


async def _send_limit_reached(update: Update) -> None:
    """Отправляет сообщение о достижении лимита."""

    text = """Наш разговор сегодня подходит к паузе...
Но я здесь, и завтра мы продолжим 💛

Если хочешь общаться без ограничений — есть премиум-доступ."""

    keyboard = get_premium_keyboard()
    await update.message.reply_text(text, reply_markup=keyboard)
