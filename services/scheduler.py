"""
Scheduler Service.
Планировщик задач для ритуалов и напоминаний.
"""

from datetime import datetime, timedelta
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from telegram.ext import Application
from loguru import logger

from database.repositories.user import UserRepository
from database.repositories.scheduled_message import ScheduledMessageRepository
from database.repositories.subscription import SubscriptionRepository
from ai.prompts.rituals import MORNING_CHECKIN_PROMPTS, EVENING_CHECKIN_PROMPTS


# Глобальный планировщик
scheduler: AsyncIOScheduler = None
app: Application = None


def start_scheduler(application: Application) -> None:
    """Запускает планировщик задач."""
    global scheduler, app
    
    app = application
    scheduler = AsyncIOScheduler()
    
    # Обработка запланированных сообщений — каждую минуту
    scheduler.add_job(
        process_scheduled_messages,
        trigger=IntervalTrigger(minutes=1),
        id="process_scheduled",
        replace_existing=True,
    )
    
    # Очистка старых сообщений — раз в день в 3:00
    scheduler.add_job(
        cleanup_old_messages,
        trigger=CronTrigger(hour=3, minute=0),
        id="cleanup_messages",
        replace_existing=True,
    )
    
    # Напоминания об истечении подписки — раз в день в 10:00
    scheduler.add_job(
        send_expiration_reminders,
        trigger=CronTrigger(hour=10, minute=0),
        id="expiration_reminders",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler() -> None:
    """Останавливает планировщик."""
    global scheduler
    
    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


async def process_scheduled_messages() -> None:
    """Обрабатывает запланированные сообщения."""
    global app
    
    if not app:
        return
    
    scheduled_repo = ScheduledMessageRepository()
    user_repo = UserRepository()
    
    pending = await scheduled_repo.get_pending()
    
    for msg in pending:
        try:
            user = await user_repo.get(msg.user_id)
            
            if not user:
                await scheduled_repo.cancel(msg.id)
                continue
            
            # Проверяем, включены ли проактивные сообщения
            if not user.proactive_messages:
                await scheduled_repo.cancel(msg.id)
                continue
            
            # Определяем текст сообщения
            content = msg.content
            if not content:
                content = await _generate_ritual_content(msg.type, user)
            
            # Отправляем
            await app.bot.send_message(
                chat_id=user.telegram_id,
                text=content,
            )
            
            await scheduled_repo.mark_sent(msg.id)
            
            # Планируем следующее сообщение этого типа
            await _reschedule_ritual(user, msg.type)
            
            logger.debug(f"Sent scheduled message {msg.id} to user {user.id}")
            
        except Exception as e:
            logger.error(f"Failed to send scheduled message {msg.id}: {e}")


async def _generate_ritual_content(ritual_type: str, user) -> str:
    """Генерирует контент для ритуала."""
    
    if ritual_type == "morning_checkin":
        return random.choice(MORNING_CHECKIN_PROMPTS)
    
    elif ritual_type == "evening_checkin":
        return random.choice(EVENING_CHECKIN_PROMPTS)
    
    elif ritual_type == "followup":
        # Для followup нужен контекст, используем дефолт
        persona_name = "Мира" if user.persona == "mira" else "Марк"
        return f"Привет 💛 Это {persona_name}. Думала о тебе. Как ты?"
    
    else:
        return "Привет 💛 Как ты сегодня?"


async def _reschedule_ritual(user, ritual_type: str) -> None:
    """Планирует следующее сообщение ритуала."""
    
    from config.settings import settings
    
    scheduled_repo = ScheduledMessageRepository()
    
    now = datetime.now()
    
    if ritual_type == "morning_checkin":
        # Следующее утро (через 1-2 дня, случайно)
        days_ahead = random.choice([1, 2, 3])
        time_str = user.preferred_time_morning or settings.RITUAL_MORNING_DEFAULT
        hour, minute = map(int, time_str.split(":"))
        
        next_time = now.replace(hour=hour, minute=minute, second=0) + timedelta(days=days_ahead)
        
    elif ritual_type == "evening_checkin":
        # Следующий вечер
        time_str = user.preferred_time_evening or settings.RITUAL_EVENING_DEFAULT
        hour, minute = map(int, time_str.split(":"))
        
        next_time = now.replace(hour=hour, minute=minute, second=0) + timedelta(days=1)
        
    else:
        # Дефолт — через день
        next_time = now + timedelta(days=1)
    
    await scheduled_repo.create(
        user_id=user.id,
        type=ritual_type,
        scheduled_for=next_time,
    )


async def cleanup_old_messages() -> None:
    """Очищает старые запланированные сообщения."""
    
    scheduled_repo = ScheduledMessageRepository()
    
    deleted = await scheduled_repo.delete_old(days=30)
    
    if deleted > 0:
        logger.info(f"Cleaned up {deleted} old scheduled messages")


async def send_expiration_reminders() -> None:
    """Отправляет напоминания об истечении подписки."""
    global app
    
    if not app:
        return
    
    subscription_repo = SubscriptionRepository()
    user_repo = UserRepository()
    
    # За 7 дней
    expiring_7 = await subscription_repo.get_expiring(days=7, exact=True)
    for sub in expiring_7:
        if sub.auto_renew:
            continue
        
        user = await user_repo.get(sub.user_id)
        if user:
            text = (
                "💛 Привет! Хотела напомнить — твоя подписка заканчивается через неделю.\n\n"
                "Если хочешь продолжить общаться без ограничений — можешь продлить заранее. "
                "А если что-то не так — напиши, я выслушаю."
            )
            try:
                await app.bot.send_message(chat_id=user.telegram_id, text=text)
            except Exception as e:
                logger.error(f"Failed to send reminder to user {user.id}: {e}")
    
    # За 3 дня
    expiring_3 = await subscription_repo.get_expiring(days=3, exact=True)
    for sub in expiring_3:
        if sub.auto_renew:
            continue
        
        user = await user_repo.get(sub.user_id)
        if user:
            text = (
                "Твоя подписка заканчивается через 3 дня.\n\n"
                "Напиши /subscription, чтобы продлить.\n"
                "Или, если хочешь, включи автоплатёж — так не придётся каждый раз помнить 💛"
            )
            try:
                await app.bot.send_message(chat_id=user.telegram_id, text=text)
            except Exception as e:
                logger.error(f"Failed to send reminder to user {user.id}: {e}")
    
    # За 1 день
    expiring_1 = await subscription_repo.get_expiring(days=1, exact=True)
    for sub in expiring_1:
        if sub.auto_renew:
            continue
        
        user = await user_repo.get(sub.user_id)
        if user:
            text = (
                "⏰ Завтра заканчивается твоя Premium подписка.\n\n"
                "После этого я по-прежнему буду рядом, но с ограничениями free-плана.\n"
                "Напиши /subscription, если хочешь продлить."
            )
            try:
                await app.bot.send_message(chat_id=user.telegram_id, text=text)
            except Exception as e:
                logger.error(f"Failed to send reminder to user {user.id}: {e}")


async def schedule_user_rituals(user_id: int) -> None:
    """Планирует ритуалы для пользователя."""
    
    from config.settings import settings
    
    user_repo = UserRepository()
    scheduled_repo = ScheduledMessageRepository()
    
    user = await user_repo.get(user_id)
    
    if not user or not user.proactive_messages:
        return
    
    rituals = user.rituals_enabled or []
    
    now = datetime.now()
    
    # Утренний check-in
    if "morning" in rituals:
        time_str = user.preferred_time_morning or settings.RITUAL_MORNING_DEFAULT
        hour, minute = map(int, time_str.split(":"))
        
        # Выбираем случайные дни недели (2-3 раза)
        next_time = now.replace(hour=hour, minute=minute, second=0)
        if next_time <= now:
            next_time += timedelta(days=1)
        
        await scheduled_repo.create(
            user_id=user_id,
            type="morning_checkin",
            scheduled_for=next_time,
        )
    
    # Вечерний check-in
    if "evening" in rituals:
        time_str = user.preferred_time_evening or settings.RITUAL_EVENING_DEFAULT
        hour, minute = map(int, time_str.split(":"))
        
        next_time = now.replace(hour=hour, minute=minute, second=0)
        if next_time <= now:
            next_time += timedelta(days=1)
        
        await scheduled_repo.create(
            user_id=user_id,
            type="evening_checkin",
            scheduled_for=next_time,
        )
    
    logger.info(f"Scheduled rituals for user {user_id}")
