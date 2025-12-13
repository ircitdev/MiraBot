"""
Main bot entry point.
Запуск и конфигурация Telegram бота.
"""

import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from loguru import logger

from config.settings import settings
from database import init_db, close_db
from bot.handlers.start import start_command, help_command
from bot.handlers.message import handle_message
from bot.handlers.voice import handle_voice
from bot.handlers.commands import (
    settings_command,
    subscription_command,
    referral_command,
    rituals_command,
    privacy_command,
)
from bot.handlers.callbacks import handle_callback
from bot.handlers.payments import (
    handle_subscription_callback,
    handle_payment_callback,
)
from services.scheduler import start_scheduler, stop_scheduler
from bot.handlers.admin import (
    admin_command,
    handle_admin_callback,
    receive_user_id,
    receive_days,
    cancel_admin,
    WAITING_USER_ID,
    WAITING_DAYS,
)


# Глобальный экземпляр приложения
application: Application = None


async def post_init(app: Application) -> None:
    """Инициализация после запуска бота."""
    logger.info("Initializing bot...")
    
    # Инициализируем БД
    await init_db()
    
    # Запускаем планировщик
    start_scheduler(app)
    
    logger.info("Bot initialized successfully")


async def post_shutdown(app: Application) -> None:
    """Очистка при остановке бота."""
    logger.info("Shutting down bot...")
    
    # Останавливаем планировщик
    stop_scheduler()
    
    # Закрываем БД
    await close_db()
    
    logger.info("Bot shutdown complete")


def create_application() -> Application:
    """Создаёт и конфигурирует приложение бота."""
    global application
    
    # Создаём приложение
    application = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("subscription", subscription_command))
    application.add_handler(CommandHandler("referral", referral_command))
    application.add_handler(CommandHandler("rituals", rituals_command))
    application.add_handler(CommandHandler("privacy", privacy_command))

    # Админ-панель с ConversationHandler
    admin_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_command),
            CallbackQueryHandler(handle_admin_callback, pattern=r"^admin:"),
        ],
        states={
            WAITING_USER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id),
                CommandHandler("cancel", cancel_admin),
            ],
            WAITING_DAYS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_days),
                CommandHandler("cancel", cancel_admin),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_admin),
            CommandHandler("admin", admin_command),
        ],
        per_chat=True,
        per_user=True,
    )
    application.add_handler(admin_conv_handler)

    # Обработчики callback-кнопок
    application.add_handler(CallbackQueryHandler(
        handle_subscription_callback,
        pattern=r"^subscribe:"
    ))
    application.add_handler(CallbackQueryHandler(
        handle_payment_callback,
        pattern=r"^pay:"
    ))
    application.add_handler(CallbackQueryHandler(
        handle_callback,
        pattern=r"^(?!subscribe:|pay:)"  # Все остальные
    ))
    
    # Обработчик голосовых сообщений
    application.add_handler(MessageHandler(
        filters.VOICE,
        handle_voice
    ))

    # Обработчик текстовых сообщений (должен быть последним)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))

    return application


def main() -> None:
    """Точка входа."""
    # Настраиваем логирование
    logger.add(
        "logs/bot_{time}.log",
        rotation="1 day",
        retention="30 days",
        level=settings.LOG_LEVEL,
    )
    
    logger.info(f"Starting Mira Bot...")
    logger.info(f"Using Claude model: {settings.CLAUDE_MODEL}")
    
    # Создаём и запускаем приложение
    app = create_application()
    
    # Запускаем polling
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
