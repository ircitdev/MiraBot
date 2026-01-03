"""
User Messages Handler.
Обработчик сообщений от пользователей для пересылки в поддержку.
"""

from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from bot_support.services.user_service import UserService
from bot_support.services.message_service import MessageService
from bot_support.utils.rate_limiter import rate_limiter
from config.settings import settings


async def user_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик всех сообщений от пользователей.

    Функционал:
    1. Проверяет rate limit
    2. Получает/создаёт пользователя в БД
    3. Пересылает сообщение в топик поддержки
    4. Отправляет автоответ (если настроен)

    Args:
        update: Объект Update от Telegram
        context: Контекст бота
    """
    # Проверяем, что это личное сообщение и не команда
    if not update.message or not update.effective_user:
        return

    # Игнорируем сообщения из групп
    if update.message.chat.type != "private":
        return

    # Игнорируем команды (они обрабатываются отдельно)
    if update.message.text and update.message.text.startswith("/"):
        return

    telegram_user = update.effective_user
    user_id = telegram_user.id

    logger.info(f"Received message from user {user_id}")

    try:
        # Проверяем rate limit
        if not rate_limiter.check_limit(user_id):
            logger.warning(f"Rate limit exceeded for user {user_id}")
            await update.message.reply_text(
                "⏳ Вы отправляете сообщения слишком быстро. "
                f"Пожалуйста, подождите немного.\n"
                f"Лимит: {settings.SUPPORT_RATE_LIMIT} сообщений в минуту."
            )
            return

        # Получаем или создаём пользователя
        user_service = UserService()
        user = await user_service.get_or_create_user(
            bot=context.bot,
            telegram_user=telegram_user,
        )

        if not user:
            logger.error(f"Failed to get/create user {user_id}")
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке вашего сообщения. "
                "Попробуйте позже."
            )
            return

        # Пересылаем сообщение в поддержку
        message_service = MessageService()
        success = await message_service.forward_to_support(
            bot=context.bot,
            message=update.message,
            user=user,
        )

        if not success:
            logger.error(f"Failed to forward message from user {user_id}")
            await update.message.reply_text(
                "❌ Не удалось отправить сообщение в поддержку. "
                "Попробуйте позже."
            )
            return

        # Увеличиваем счётчик rate limiter
        rate_limiter.increment(user_id)

        # Отправляем автоответ, если он настроен
        if settings.SUPPORT_AUTO_REPLY:
            await update.message.reply_text(settings.SUPPORT_AUTO_REPLY)

        logger.info(
            f"Successfully forwarded message from user {user_id} to topic {user.topic_id}"
        )

    except Exception as e:
        logger.error(f"Error in user_message_handler: {e}", exc_info=True)
        # Не отправляем сообщение об ошибке пользователю, чтобы не спамить
        # в случае системной проблемы


async def user_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик фото от пользователей.
    Использует общий handler для всех типов сообщений.
    """
    await user_message_handler(update, context)


async def user_video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик видео от пользователей.
    Использует общий handler для всех типов сообщений.
    """
    await user_message_handler(update, context)


async def user_voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик голосовых сообщений от пользователей.
    Использует общий handler для всех типов сообщений.
    """
    await user_message_handler(update, context)


async def user_video_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик видеосообщений от пользователей.
    Использует общий handler для всех типов сообщений.
    """
    await user_message_handler(update, context)


async def user_document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик документов от пользователей.
    Использует общий handler для всех типов сообщений.
    """
    await user_message_handler(update, context)


async def user_sticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик стикеров от пользователей.
    Использует общий handler для всех типов сообщений.
    """
    await user_message_handler(update, context)
