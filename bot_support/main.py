"""
Support Bot Main Entry Point.
Главный файл бота технической поддержки.
"""

import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)
from loguru import logger

from config.settings import settings
from bot_support.handlers.start import start_handler
from bot_support.handlers.messages import (
    user_message_handler,
    user_photo_handler,
    user_video_handler,
    user_voice_handler,
    user_video_note_handler,
    user_document_handler,
    user_sticker_handler,
)
from bot_support.handlers.admin_messages import admin_reply_handler
from bot_support.utils.rate_limiter import rate_limiter


async def setup_bot() -> Application:
    """
    Настройка и инициализация бота.

    Returns:
        Application: Настроенный экземпляр приложения
    """
    # Создаём приложение
    application = (
        Application.builder()
        .token(settings.SUPPORT_BOT_TOKEN)
        .build()
    )

    # === Команды ===
    application.add_handler(CommandHandler("start", start_handler))

    # === Сообщения от пользователей (личные чаты) ===
    # Текстовые сообщения
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
            user_message_handler,
        )
    )

    # Фото
    application.add_handler(
        MessageHandler(
            filters.PHOTO & filters.ChatType.PRIVATE,
            user_photo_handler,
        )
    )

    # Видео
    application.add_handler(
        MessageHandler(
            filters.VIDEO & filters.ChatType.PRIVATE,
            user_video_handler,
        )
    )

    # Голосовые
    application.add_handler(
        MessageHandler(
            filters.VOICE & filters.ChatType.PRIVATE,
            user_voice_handler,
        )
    )

    # Видеосообщения (кружки)
    application.add_handler(
        MessageHandler(
            filters.VIDEO_NOTE & filters.ChatType.PRIVATE,
            user_video_note_handler,
        )
    )

    # Документы
    application.add_handler(
        MessageHandler(
            filters.Document.ALL & filters.ChatType.PRIVATE,
            user_document_handler,
        )
    )

    # Стикеры
    application.add_handler(
        MessageHandler(
            filters.Sticker.ALL & filters.ChatType.PRIVATE,
            user_sticker_handler,
        )
    )

    # === Сообщения от админов (супергруппа) ===
    # Все типы сообщений из супергруппы
    application.add_handler(
        MessageHandler(
            filters.Chat(chat_id=settings.SUPPORT_GROUP_ID) & ~filters.COMMAND,
            admin_reply_handler,
        )
    )

    logger.info("Bot handlers registered successfully")

    return application


async def cleanup_rate_limiter():
    """
    Периодическая очистка rate limiter от старых записей.
    Запускается в фоне каждый час.
    """
    while True:
        try:
            await asyncio.sleep(3600)  # 1 час
            rate_limiter.cleanup()
            logger.debug("Rate limiter cleanup completed")
        except Exception as e:
            logger.error(f"Error in rate limiter cleanup: {e}")


async def start_bot():
    """
    Запуск бота поддержки.
    """
    logger.info("Starting Support Bot...")
    logger.info(f"Bot token: {settings.SUPPORT_BOT_TOKEN[:10]}...")
    logger.info(f"Support group ID: {settings.SUPPORT_GROUP_ID}")
    logger.info(f"Support enabled: {settings.SUPPORT_ENABLED}")

    if not settings.SUPPORT_ENABLED:
        logger.warning("Support bot is disabled in settings. Exiting.")
        return

    if not settings.SUPPORT_BOT_TOKEN:
        logger.error("SUPPORT_BOT_TOKEN is not set. Cannot start bot.")
        return

    if not settings.SUPPORT_GROUP_ID:
        logger.error("SUPPORT_GROUP_ID is not set. Cannot start bot.")
        return

    # Настраиваем бота
    application = await setup_bot()

    # Запускаем задачу очистки rate limiter
    asyncio.create_task(cleanup_rate_limiter())

    # Запускаем polling
    logger.info("Bot is running... Press Ctrl+C to stop.")

    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            allowed_updates=["message", "edited_message"],
            drop_pending_updates=True,
        )

        # Держим бота запущенным
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received stop signal")
    except Exception as e:
        logger.error(f"Error running bot: {e}", exc_info=True)
    finally:
        logger.info("Stopping bot...")
        await application.stop()
        await application.shutdown()
        logger.info("Bot stopped")


def main():
    """
    Точка входа для запуска бота.
    """
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
