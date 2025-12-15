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

    # Проверка праздников (дни рождения, годовщины) — каждое утро в 9:00
    scheduler.add_job(
        check_celebrations,
        trigger=CronTrigger(hour=9, minute=0),
        id="check_celebrations",
        replace_existing=True,
    )

    # Конвертация истёкших trial подписок в free — каждый час
    scheduler.add_job(
        convert_expired_trials,
        trigger=IntervalTrigger(hours=1),
        id="convert_trials",
        replace_existing=True,
    )

    # Bi-weekly прогресс-сводки — каждый понедельник в 19:00
    scheduler.add_job(
        send_biweekly_summaries,
        trigger=CronTrigger(day_of_week='mon', hour=19, minute=0),
        id="biweekly_summaries",
        replace_existing=True,
    )

    # Check-in по целям — каждый день в 20:00
    scheduler.add_job(
        send_goal_checkins,
        trigger=CronTrigger(hour=20, minute=0),
        id="goal_checkins",
        replace_existing=True,
    )

    # Follow-up вопросы — каждый час
    scheduler.add_job(
        send_followup_questions,
        trigger=IntervalTrigger(hours=1),
        id="followup_questions",
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
    """Генерирует персонализированный контент для ритуала."""

    if ritual_type in ["morning_checkin", "evening_checkin"]:
        # Персонализированная генерация через Claude
        try:
            from database.repositories.memory import MemoryRepository
            from database.repositories.mood import MoodRepository
            from database.repositories.conversation import ConversationRepository
            from ai.prompts.checkin import build_checkin_prompt
            from ai.claude_client import ClaudeClient

            memory_repo = MemoryRepository()
            mood_repo = MoodRepository()
            conversation_repo = ConversationRepository()

            # Собираем контекст
            recent_topics = await memory_repo.get_recent_topics(user.id, limit=3)
            recent_mood = await mood_repo.get_latest(user.id)
            last_message = await conversation_repo.get_last_message(user.id, role="user")

            # Строим промпт
            prompt = build_checkin_prompt(
                ritual_type=ritual_type,
                user=user,
                recent_topics=recent_topics,
                recent_mood=recent_mood,
                last_message=last_message,
            )

            # Генерируем через Claude
            claude = ClaudeClient()
            result = await claude.generate_simple(
                system_prompt=prompt["system"],
                user_prompt=prompt["user"],
                max_tokens=200,
            )

            logger.debug(f"Generated personalized check-in for user {user.id}")
            return result

        except Exception as e:
            logger.warning(f"Failed to generate personalized check-in: {e}, using fallback")
            # Fallback к шаблонным сообщениям
            if ritual_type == "morning_checkin":
                return random.choice(MORNING_CHECKIN_PROMPTS)
            else:
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


async def cancel_user_ritual(user_id: int, ritual_type: str) -> int:
    """
    Отменяет запланированные сообщения ритуала.

    Args:
        user_id: ID пользователя
        ritual_type: Тип ритуала (morning_checkin, evening_checkin, etc.)

    Returns:
        Количество отменённых сообщений
    """
    scheduled_repo = ScheduledMessageRepository()
    count = await scheduled_repo.cancel_by_user(user_id, type=ritual_type)
    logger.debug(f"Cancelled {count} {ritual_type} messages for user {user_id}")
    return count

async def check_celebrations() -> None:
    """
    Проверяет дни рождения и годовщины.
    Отправляет персонализированные поздравления.
    """
    global app

    if not app:
        return

    user_repo = UserRepository()

    today = datetime.now()
    month = today.month
    day = today.day

    logger.info(f"Checking celebrations for {day:02d}.{month:02d}")

    # Дни рождения
    birthday_users = await user_repo.get_by_celebration_date("birthday", month, day)

    for user in birthday_users:
        try:
            content = await _generate_birthday_message(user)
            await app.bot.send_message(chat_id=user.telegram_id, text=content)
            logger.info(f"Sent birthday greeting to user {user.id}")
        except Exception as e:
            logger.error(f"Failed to send birthday greeting to user {user.id}: {e}")

    # Годовщины
    anniversary_users = await user_repo.get_by_celebration_date("anniversary", month, day)

    for user in anniversary_users:
        try:
            content = await _generate_anniversary_message(user)
            await app.bot.send_message(chat_id=user.telegram_id, text=content)
            logger.info(f"Sent anniversary greeting to user {user.id}")
        except Exception as e:
            logger.error(f"Failed to send anniversary greeting to user {user.id}: {e}")

    logger.info(f"Celebrations check complete: {len(birthday_users)} birthdays, {len(anniversary_users)} anniversaries")


async def _generate_birthday_message(user) -> str:
    """Генерирует поздравление с днём рождения."""
    try:
        from ai.prompts.celebrations import build_birthday_prompt
        from ai.claude_client import ClaudeClient
        from database.repositories.memory import MemoryRepository

        # Получаем контекст из памяти
        memory_repo = MemoryRepository()
        recent_topics = await memory_repo.get_recent_topics(user.id, limit=5)
        context = ", ".join(recent_topics) if recent_topics else None

        prompt = build_birthday_prompt(user=user, context=context)

        claude = ClaudeClient()
        result = await claude.generate_simple(
            system_prompt=prompt["system"],
            user_prompt=prompt["user"],
            max_tokens=300,
        )

        return result

    except Exception as e:
        logger.warning(f"Failed to generate personalized birthday message: {e}")
        persona_name = "Мира" if user.persona == "mira" else "Марк"
        name = user.display_name or "подруга"
        return f"С днём рождения, {name}! 🎂 Это {persona_name}. Желаю тебе всего самого светлого в новом году жизни 💛"


async def _generate_anniversary_message(user) -> str:
    """Генерирует поздравление с годовщиной."""
    try:
        from ai.prompts.celebrations import build_anniversary_prompt
        from ai.claude_client import ClaudeClient
        from database.repositories.memory import MemoryRepository

        # Получаем контекст о браке из памяти
        memory_repo = MemoryRepository()
        entries = await memory_repo.get_by_user(
            user_id=user.id,
            category="family",
            limit=5,
        )
        context = "\n".join([e.content for e in entries]) if entries else None

        # Вычисляем годы вместе
        years = None
        if user.anniversary:
            years = datetime.now().year - user.anniversary.year

        prompt = build_anniversary_prompt(user=user, years=years, context=context)

        claude = ClaudeClient()
        result = await claude.generate_simple(
            system_prompt=prompt["system"],
            user_prompt=prompt["user"],
            max_tokens=300,
        )

        return result

    except Exception as e:
        logger.warning(f"Failed to generate personalized anniversary message: {e}")
        persona_name = "Мира" if user.persona == "mira" else "Марк"
        name = user.display_name or "подруга"
        return f"Привет, {name}! Сегодня особенный день — годовщина 💛 Это {persona_name}. Думаю о тебе."


async def convert_expired_trials() -> None:
    """Конвертирует истёкшие trial подписки в free."""
    from database.session import get_session_context
    from database.models import Subscription
    from sqlalchemy import select, and_

    async with get_session_context() as session:
        # Находим истёкшие trial подписки
        result = await session.execute(
            select(Subscription).where(
                and_(
                    Subscription.plan == "trial",
                    Subscription.status == "active",
                    Subscription.expires_at <= datetime.now()
                )
            )
        )
        expired_trials = result.scalars().all()

        for sub in expired_trials:
            # Конвертируем в free
            sub.plan = "free"
            sub.expires_at = None
            sub.messages_today = 0
            sub.messages_reset_at = datetime.now().date()
            logger.info(f"Converted trial subscription {sub.id} (user {sub.user_id}) to free")

        await session.commit()

        if expired_trials:
            logger.info(f"Converted {len(expired_trials)} expired trial subscriptions to free")


async def send_biweekly_summaries() -> None:
    """
    Отправляет bi-weekly сводки прогресса активным пользователям.
    Запускается каждый понедельник.
    """
    global app

    if not app:
        return

    from ai.summary_generator import summary_generator
    from database.repositories.memory import MemoryRepository

    user_repo = UserRepository()
    memory_repo = MemoryRepository()

    # Получаем всех активных пользователей
    active_users = await user_repo.get_active_users(days=14)

    summaries_sent = 0

    for user in active_users:
        try:
            # Проверяем нужно ли отправлять сводку
            should_send = await summary_generator.should_send_summary(user.id)

            if not should_send:
                logger.debug(f"Skipping summary for user {user.id}: not eligible")
                continue

            # Генерируем сводку
            summary_text = await summary_generator.generate_biweekly_summary(
                user_id=user.id,
                period_days=14,
            )

            if not summary_text:
                logger.debug(f"Could not generate summary for user {user.id}")
                continue

            # Отправляем пользователю
            await app.bot.send_message(
                chat_id=user.telegram_id,
                text=summary_text,
            )

            # Сохраняем в память что отправили сводку
            await memory_repo.create(
                user_id=user.id,
                category="progress_summary",
                content=f"Bi-weekly summary sent: {summary_text[:100]}...",
                importance=7,
            )

            summaries_sent += 1
            logger.info(f"Sent bi-weekly summary to user {user.id}")

        except Exception as e:
            logger.error(f"Failed to send summary to user {user.id}: {e}")

    logger.info(f"Bi-weekly summaries job complete: {summaries_sent} summaries sent")


async def send_goal_checkins() -> None:
    """
    Отправляет check-in сообщения по активным целям.
    Запускается каждый день.
    """
    global app

    if not app:
        return

    from database.repositories.goal import GoalRepository
    from database.repositories.user import UserRepository

    goal_repo = GoalRepository()
    user_repo = UserRepository()

    # Получаем цели которым нужен check-in
    goals_needing_checkin = await goal_repo.get_goals_needing_checkin(limit=50)

    checkins_sent = 0

    for goal in goals_needing_checkin:
        try:
            # Получаем пользователя
            user = await user_repo.get(goal.user_id)

            if not user:
                continue

            # Формируем сообщение check-in
            checkin_message = _build_checkin_message(goal)

            # Отправляем пользователю
            await app.bot.send_message(
                chat_id=user.telegram_id,
                text=checkin_message,
            )

            # Обновляем last_check_in и next_check_in
            goal.last_check_in = datetime.utcnow()

            # Вычисляем следующий check-in
            if goal.reminder_frequency:
                if goal.reminder_frequency == "daily":
                    goal.next_check_in = datetime.utcnow() + timedelta(days=1)
                elif goal.reminder_frequency == "weekly":
                    goal.next_check_in = datetime.utcnow() + timedelta(days=7)
                elif goal.reminder_frequency == "biweekly":
                    goal.next_check_in = datetime.utcnow() + timedelta(days=14)

            # Сохраняем изменения (через update_progress чтобы триггерить updated_at)
            await goal_repo.update_progress(
                goal_id=goal.id,
                progress=goal.progress,
                notes=None,
            )

            checkins_sent += 1
            logger.info(f"Sent goal check-in to user {user.id} for goal {goal.id}")

        except Exception as e:
            logger.error(f"Failed to send goal check-in for goal {goal.id}: {e}")

    logger.info(f"Goal check-ins job complete: {checkins_sent} check-ins sent")


def _build_checkin_message(goal) -> str:
    """
    Строит сообщение check-in для цели.

    Args:
        goal: Объект UserGoal

    Returns:
        Текст сообщения
    """
    parts = [
        f"Привет! Как дела с целью **{goal.smart_goal or goal.original_goal}**?",
        "",
    ]

    # Текущий прогресс
    progress_bar = "▓" * (goal.progress // 10) + "░" * (10 - goal.progress // 10)
    parts.append(f"Текущий прогресс: [{progress_bar}] {goal.progress}%")

    # Информация о дедлайне
    if goal.time_bound:
        days_left = (goal.time_bound - datetime.utcnow()).days
        if days_left < 0:
            parts.append(f"⚠️ Дедлайн просрочен на {abs(days_left)} дней")
        elif days_left <= 3:
            parts.append(f"🔥 Осталось всего {days_left} дней!")
        else:
            parts.append(f"До дедлайна: {days_left} дней")

    parts.append("")
    parts.append("Расскажи, что получилось за это время? Что-то мешает двигаться дальше?")

    return "\n".join(parts)


async def send_followup_questions() -> None:
    """
    Отправляет follow-up вопросы по обещаниям и планам пользователей.
    Запускается каждый час.
    """
    global app

    if not app:
        return

    from database.repositories.followup import FollowUpRepository
    from database.repositories.user import UserRepository

    followup_repo = FollowUpRepository()
    user_repo = UserRepository()

    # Получаем follow-ups которым пришло время
    followups_due = await followup_repo.get_followups_due(limit=30)

    followups_sent = 0

    for followup in followups_due:
        try:
            # Получаем пользователя
            user = await user_repo.get(followup.user_id)

            if not user:
                continue

            # Формируем сообщение follow-up
            followup_message = _build_followup_message(followup)

            # Отправляем пользователю
            await app.bot.send_message(
                chat_id=user.telegram_id,
                text=followup_message,
            )

            # Отмечаем что вопрос задан
            await followup_repo.mark_as_asked(followup.id)

            followups_sent += 1
            logger.info(f"Sent follow-up question to user {user.id} for action: {followup.action[:30]}...")

        except Exception as e:
            logger.error(f"Failed to send follow-up to user {followup.user_id}: {e}")

    if followups_sent > 0:
        logger.info(f"Follow-up questions job complete: {followups_sent} follow-ups sent")


def _build_followup_message(followup) -> str:
    """
    Строит сообщение follow-up для обещания/плана.

    Args:
        followup: Объект UserFollowUp

    Returns:
        Текст сообщения
    """
    parts = []

    # Приветствие зависит от категории
    if followup.category == "conversation":
        parts.append(f"Слушай, ты хотела **{followup.action}**.")
    elif followup.category == "task":
        parts.append(f"Помню, ты планировала **{followup.action}**.")
    elif followup.category == "decision":
        parts.append(f"Ты собиралась **{followup.action}**.")
    else:
        parts.append(f"Напоминаю, ты хотела **{followup.action}**.")

    parts.append("")

    # Контекст если есть
    if followup.context:
        parts.append(f"_{followup.context}_")
        parts.append("")

    # Вопрос
    parts.append("Как прошло? Получилось?")

    return "\n".join(parts)
