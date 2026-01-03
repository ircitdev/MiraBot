"""
Admin Messages Handler.
Обработчик сообщений от администраторов для пересылки пользователям.
"""

from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from database.repositories.support_user import SupportUserRepository
from bot_support.services.message_service import MessageService
from config.settings import settings


async def admin_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик ответов администраторов из супергруппы.

    Функционал:
    1. Проверяет, что сообщение из супергруппы поддержки
    2. Определяет topic_id из message_thread_id
    3. Находит пользователя по topic_id
    4. Пересылает сообщение пользователю

    Args:
        update: Объект Update от Telegram
        context: Контекст бота
    """
    # Проверяем, что это сообщение из группы
    if not update.message or not update.effective_chat:
        return

    message = update.message
    chat_id = update.effective_chat.id

    # Проверяем, что это наша супергруппа поддержки
    if chat_id != settings.SUPPORT_GROUP_ID:
        return

    # Проверяем, что у сообщения есть topic_id (отправлено в топик)
    if not message.message_thread_id:
        logger.debug(
            f"Message in support group without topic_id (general chat), ignoring"
        )
        return

    topic_id = message.message_thread_id

    # Игнорируем топик с отзывами
    if topic_id == settings.REVIEWS_TOPIC_ID:
        logger.debug(f"Message in reviews topic {topic_id}, ignoring")
        return

    logger.info(
        f"Received admin reply in topic {topic_id} "
        f"from user {update.effective_user.id if update.effective_user else 'unknown'}"
    )

    try:
        # Находим пользователя по topic_id
        user_repo = SupportUserRepository()
        user = await user_repo.get_by_topic_id(topic_id)

        if not user:
            logger.warning(
                f"No user found for topic {topic_id}. "
                "This might be a system topic or topic was deleted."
            )
            # Не отправляем ответ в группу, чтобы не спамить
            return

        # Проверяем, не заблокировал ли пользователь бота
        if user.is_bot_blocked:
            logger.warning(
                f"User {user.telegram_id} has blocked the bot. "
                f"Cannot send message from topic {topic_id}"
            )
            await message.reply_text(
                "⚠️ Пользователь заблокировал бота. "
                "Сообщение не может быть доставлено."
            )
            return

        # Пересылаем сообщение пользователю
        message_service = MessageService()
        success = await message_service.forward_to_user(
            bot=context.bot,
            message=message,
            user=user,
        )

        if not success:
            logger.error(
                f"Failed to forward admin reply to user {user.telegram_id} "
                f"from topic {topic_id}"
            )
            await message.reply_text(
                "❌ Не удалось отправить сообщение пользователю. "
                "Возможно, пользователь заблокировал бота."
            )
            return

        # Отправляем подтверждение в топик (опционально, можно убрать)
        logger.info(
            f"Successfully forwarded admin reply from topic {topic_id} "
            f"to user {user.telegram_id}"
        )

    except Exception as e:
        logger.error(f"Error in admin_reply_handler: {e}", exc_info=True)
        # Отправляем сообщение об ошибке в топик
        try:
            await message.reply_text(
                "❌ Произошла ошибка при отправке сообщения пользователю."
            )
        except Exception:
            pass
