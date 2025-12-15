"""
Main bot entry point.
Запуск и конфигурация Telegram бота.
"""

import asyncio
import signal
import sys
import os
import fcntl
from pathlib import Path
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
from bot.handlers.message import handle_message, handle_photo
from bot.handlers.voice import handle_voice
from bot.handlers.commands import (
    settings_command,
    subscription_command,
    referral_command,
    rituals_command,
    privacy_command,
    goals_command,
    plans_command,
)
from bot.handlers.callbacks import handle_callback
from bot.handlers.payments import (
    handle_subscription_callback,
    handle_payment_callback,
)
from bot.handlers.content import (
    exercises_command,
    affirmation_command,
    meditation_command,
    handle_content_callback,
)
from services.scheduler import start_scheduler, stop_scheduler
from services.redis_client import redis_client
from services.health import health_server
from bot.handlers.admin import (
    admin_command,
    handle_admin_callback,
    receive_user_id,
    receive_days,
    receive_block_reason,
    receive_broadcast_message,
    receive_promo_code_input,
    receive_promo_value,
    receive_promo_max_uses,
    cancel_admin,
    WAITING_USER_ID,
    WAITING_DAYS,
    WAITING_BLOCK_REASON,
    WAITING_BROADCAST_MESSAGE,
    WAITING_PROMO_CODE,
    WAITING_PROMO_VALUE,
    WAITING_PROMO_MAX_USES,
)
from bot.handlers.promo import get_promo_handler
from services.music_forwarder import (
    handle_supergroup_message,
    MUSIC_SUPERGROUP_ID,
    music_forwarder,
)


# Глобальный экземпляр приложения
application: Application = None

# Флаг для отслеживания состояния shutdown
_shutdown_in_progress = False
_shutdown_timeout = 30  # секунд на завершение pending запросов

# PID-файл для контроля одного экземпляра
PID_FILE = Path(__file__).parent.parent / "mira_bot.pid"
_lock_file = None


def acquire_lock() -> bool:
    """
    Захватывает блокировку PID-файла.
    Гарантирует что запущен только один экземпляр бота.

    Returns:
        True если блокировка получена, False если уже запущен другой экземпляр
    """
    global _lock_file

    try:
        # Открываем файл для чтения+записи, создаём если не существует
        _lock_file = open(PID_FILE, "a+")
        # Пробуем получить эксклюзивную блокировку (non-blocking)
        fcntl.flock(_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Блокировка получена — очищаем файл и записываем наш PID
        _lock_file.seek(0)
        _lock_file.truncate()
        _lock_file.write(str(os.getpid()))
        _lock_file.flush()
        logger.info(f"PID lock acquired: {os.getpid()}")
        return True
    except (IOError, OSError) as e:
        if _lock_file:
            _lock_file.close()
            _lock_file = None
        logger.error(f"Another bot instance is already running! Error: {e}")
        return False


def release_lock() -> None:
    """Освобождает блокировку PID-файла."""
    global _lock_file

    if _lock_file:
        try:
            fcntl.flock(_lock_file.fileno(), fcntl.LOCK_UN)
            _lock_file.close()
            PID_FILE.unlink(missing_ok=True)
            logger.info("PID lock released")
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")


async def post_init(app: Application) -> None:
    """Инициализация после запуска бота."""
    logger.info("Initializing bot...")

    # Отключаем кнопку меню
    try:
        from telegram import MenuButtonDefault
        await app.bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        logger.info("Menu button disabled")
    except Exception as e:
        logger.warning(f"Failed to disable menu button: {e}")

    # Настраиваем команды бота для обычных пользователей
    try:
        from telegram import BotCommand
        commands = [
            BotCommand("start", "Начать общение с Мирой"),
            BotCommand("help", "Что я умею и как мне пользоваться"),
            BotCommand("exercises", "Упражнения: дыхание, релаксация, заземление"),
            BotCommand("affirmation", "Получить аффирмацию дня"),
            BotCommand("meditation", "Медитации и практики осознанности"),
            BotCommand("settings", "Настройки бота и персоны"),
            BotCommand("subscription", "Информация о подписке и Premium"),
            BotCommand("referral", "Пригласить подругу и получить бонусы"),
            BotCommand("rituals", "Настроить ежедневные ритуалы"),
        ]
        await app.bot.set_my_commands(commands)
        logger.info("Bot commands menu configured")
    except Exception as e:
        logger.warning(f"Failed to set bot commands: {e}")

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

    # Инициализируем music forwarder с ботом
    music_forwarder.set_bot(app.bot)
    logger.info("Music forwarder initialized")

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
    application.add_handler(CommandHandler("goals", goals_command))
    application.add_handler(CommandHandler("plans", plans_command))
    application.add_handler(CommandHandler("exercises", exercises_command))
    application.add_handler(CommandHandler("affirmation", affirmation_command))
    application.add_handler(CommandHandler("meditation", meditation_command))

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
            WAITING_BLOCK_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_block_reason),
                CommandHandler("cancel", cancel_admin),
            ],
            WAITING_BROADCAST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast_message),
                CommandHandler("cancel", cancel_admin),
            ],
            WAITING_PROMO_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_promo_code_input),
                CommandHandler("cancel", cancel_admin),
            ],
            WAITING_PROMO_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_promo_value),
                CommandHandler("cancel", cancel_admin),
            ],
            WAITING_PROMO_MAX_USES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_promo_max_uses),
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

    # Обработчик промокодов
    promo_handler = get_promo_handler()
    application.add_handler(promo_handler)

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
        handle_content_callback,
        pattern=r"^(ex:|aff:|med:)"  # Упражнения, аффирмации, медитации
    ))
    application.add_handler(CallbackQueryHandler(
        handle_callback,
        pattern=r"^(?!subscribe:|pay:|ex:|aff:|med:)"  # Все остальные
    ))
    
    # Обработчик голосовых сообщений
    application.add_handler(MessageHandler(
        filters.VOICE,
        handle_voice
    ))

    # Обработчик фотографий
    application.add_handler(MessageHandler(
        filters.PHOTO,
        handle_photo
    ))

    # Обработчик музыки из супергруппы (для кэширования)
    application.add_handler(MessageHandler(
        filters.Chat(MUSIC_SUPERGROUP_ID) & (filters.AUDIO | filters.VOICE | filters.VIDEO),
        handle_supergroup_message
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

    # Проверяем что не запущен другой экземпляр (только на Unix)
    if sys.platform != "win32":
        if not acquire_lock():
            logger.error("Bot is already running! Exiting.")
            sys.exit(1)

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
        # Освобождаем блокировку
        if sys.platform != "win32":
            release_lock()
        logger.info("Bot stopped")


if __name__ == "__main__":
    main()
