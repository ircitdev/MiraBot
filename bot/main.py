"""
Main bot entry point.
Запуск и конфигурация Telegram бота.
"""

import asyncio
import signal
import sys
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
from services.redis_client import redis_client
from services.health import health_server
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

# Флаг для отслеживания состояния shutdown
_shutdown_in_progress = False
_shutdown_timeout = 30  # секунд на завершение pending запросов


async def post_init(app: Application) -> None:
    """Инициализация после запуска бота."""
    logger.info("Initializing bot...")

    # Подключаемся к Redis
    await redis_client.connect()

    # Инициализируем БД
    await init_db()

    # Запускаем планировщик
    start_scheduler(app)

    # Запускаем health check сервер
    try:
        await health_server.start()
        health_server.set_bot_running(True)
    except Exception as e:
        logger.warning(f"Failed to start health check server: {e}")

    logger.info("Bot initialized successfully")


async def post_shutdown(app: Application) -> None:
    """Очистка при остановке бота."""
    global _shutdown_in_progress

    if _shutdown_in_progress:
        logger.warning("Shutdown already in progress, skipping...")
        return

    _shutdown_in_progress = True
    logger.info("Shutting down bot gracefully...")

    # Помечаем бот как остановленный для health check
    health_server.set_bot_running(False)

    # Останавливаем health check сервер
    try:
        await health_server.stop()
    except Exception as e:
        logger.error(f"Error stopping health server: {e}")

    # Останавливаем планировщик
    try:
        stop_scheduler()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")

    # Отключаемся от Redis
    try:
        await redis_client.disconnect()
        logger.info("Redis disconnected")
    except Exception as e:
        logger.error(f"Error disconnecting Redis: {e}")

    # Закрываем БД
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")

    logger.info("Bot shutdown complete")


def _handle_signal(signum: int, frame) -> None:
    """Обработчик сигналов SIGTERM и SIGINT."""
    signal_name = signal.Signals(signum).name
    logger.info(f"Received signal {signal_name}, initiating graceful shutdown...")

    # Если приложение запущено, останавливаем его
    if application and application.running:
        # Создаём задачу для остановки в event loop
        asyncio.create_task(_graceful_stop())
    else:
        logger.info("Application not running, exiting immediately")
        sys.exit(0)


async def _graceful_stop() -> None:
    """Корректная остановка приложения."""
    global application

    if not application:
        return

    try:
        logger.info(f"Waiting up to {_shutdown_timeout}s for pending requests...")

        # Останавливаем polling/webhook
        await application.stop()

        # Ждём завершения обработчиков
        await asyncio.sleep(1)

        # Вызываем shutdown
        await application.shutdown()

        logger.info("Graceful stop completed")

    except Exception as e:
        logger.error(f"Error during graceful stop: {e}")
    finally:
        # Выходим
        sys.exit(0)


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

    # Регистрируем обработчики сигналов для graceful shutdown
    # SIGTERM — от systemd при остановке сервиса
    # SIGINT — при Ctrl+C
    if sys.platform != "win32":
        # На Unix используем signal напрямую
        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)
        logger.info("Signal handlers registered (SIGTERM, SIGINT)")
    else:
        # На Windows только SIGINT (Ctrl+C)
        signal.signal(signal.SIGINT, _handle_signal)
        logger.info("Signal handler registered (SIGINT)")

    # Создаём и запускаем приложение
    app = create_application()

    try:
        # Запускаем polling
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    main()
