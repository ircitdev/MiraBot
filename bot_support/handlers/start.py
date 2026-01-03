"""
Start Handler.
Обработчик команды /start для бота поддержки.
"""

from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from bot_support.services.user_service import UserService


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /start.

    При первом обращении:
    1. Создаёт пользователя в БД
    2. Создаёт топик в супергруппе
    3. Отправляет карточку пользователя в топик

    Args:
        update: Объект Update от Telegram
        context: Контекст бота
    """
    # Проверяем, что это личное сообщение
    if not update.message or not update.effective_user:
        return

    # Игнорируем команды из групп
    if update.message.chat.type != "private":
        return

    telegram_user = update.effective_user

    logger.info(f"Start command from user {telegram_user.id}")

    try:
        # Получаем или создаём пользователя
        user_service = UserService()
        user = await user_service.get_or_create_user(
            bot=context.bot,
            telegram_user=telegram_user,
        )

        if not user:
            # Не удалось создать пользователя
            await update.message.reply_text(
                "❌ К сожалению, произошла ошибка. "
                "Попробуйте позже или обратитесь к администратору."
            )
            logger.error(f"Failed to create user for {telegram_user.id}")
            return

        # Отправляем приветственное сообщение
        welcome_message = (
            "👋 Добро пожаловать в службу поддержки!\n\n"
            "📝 Напишите ваш вопрос или обращение, и мы обязательно вам поможем.\n"
            "⏰ Обычно мы отвечаем в течение нескольких минут.\n\n"
            "💬 Вы можете отправлять:\n"
            "• Текстовые сообщения\n"
            "• Фотографии и видео\n"
            "• Документы\n"
            "• Голосовые сообщения\n\n"
            "⚠️ Пожалуйста, не отправляйте более 10 сообщений в минуту."
        )

        await update.message.reply_text(welcome_message)

        logger.info(
            f"Successfully handled /start for user {telegram_user.id}, "
            f"topic_id={user.topic_id}"
        )

    except Exception as e:
        logger.error(f"Error in start_handler: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте позже."
        )
