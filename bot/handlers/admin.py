"""
Admin handlers.
Команды администратора бота.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
from loguru import logger

from database.repositories.user import UserRepository
from database.repositories.subscription import SubscriptionRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.referral import ReferralRepository
from config.settings import settings
from services.audit import audit_service


# Telegram ID администратора
ADMIN_ID = 65876198

# Состояния для ConversationHandler
WAITING_USER_ID = 1
WAITING_DAYS = 2

user_repo = UserRepository()
subscription_repo = SubscriptionRepository()
conversation_repo = ConversationRepository()
referral_repo = ReferralRepository()


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == ADMIN_ID


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Главное меню администратора /admin."""

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ У тебя нет доступа к этой команде.")
        return

    keyboard = [
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton("👯 Рефералы", callback_data="admin:referrals")],
        [InlineKeyboardButton("🎁 Выдать Premium", callback_data="admin:give_premium")],
    ]

    text = """🔧 Админ-панель

Выбери действие:"""

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик callback-кнопок админки."""

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔ У тебя нет доступа.")
        return ConversationHandler.END

    data = query.data

    if data == "admin:users":
        return await _show_users(query, context)

    elif data == "admin:stats":
        return await _show_stats(query, context)

    elif data == "admin:referrals":
        return await _show_referrals(query, context)

    elif data == "admin:give_premium":
        return await _start_give_premium(query, context)

    elif data == "admin:back":
        return await _show_main_menu(query, context)

    elif data.startswith("admin:users:page:"):
        page = int(data.split(":")[-1])
        return await _show_users(query, context, page=page)

    elif data.startswith("admin:user:"):
        telegram_id = int(data.split(":")[-1])
        return await _show_user_detail(query, context, telegram_id)

    elif data.startswith("admin:referrals:page:"):
        page = int(data.split(":")[-1])
        return await _show_referrals(query, context, page=page)

    return ConversationHandler.END


async def _show_main_menu(query, context) -> int:
    """Показать главное меню."""

    keyboard = [
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton("👯 Рефералы", callback_data="admin:referrals")],
        [InlineKeyboardButton("🎁 Выдать Premium", callback_data="admin:give_premium")],
    ]

    await query.edit_message_text(
        "🔧 Админ-панель\n\nВыбери действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


async def _show_users(query, context, page: int = 1) -> int:
    """Показать список пользователей."""

    # Аудит
    await audit_service.log_view_users(query.from_user.id, page)

    per_page = 8
    users, total = await user_repo.get_paginated(page=page, per_page=per_page)

    total_pages = (total + per_page - 1) // per_page

    lines = [f"👥 Пользователи ({total} всего)\n"]
    lines.append("Нажми на ID для подробной статистики:\n")

    user_buttons = []
    for user in users:
        sub = await subscription_repo.get_active(user.id)
        plan = "💎" if sub and sub.plan == "premium" else "🆓"
        name = user.display_name or user.first_name or "—"
        username = f"@{user.username}" if user.username else ""
        lines.append(f"{plan} {name} {username}")
        lines.append(f"   ID: {user.telegram_id}")

        # Кнопка для каждого пользователя
        user_buttons.append(
            InlineKeyboardButton(
                f"{plan} {user.telegram_id}",
                callback_data=f"admin:user:{user.telegram_id}"
            )
        )

    # Разбиваем кнопки по 2 в ряд
    keyboard = []
    for i in range(0, len(user_buttons), 2):
        row = user_buttons[i:i+2]
        keyboard.append(row)

    # Пагинация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"admin:users:page:{page-1}"))
    nav_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"admin:users:page:{page+1}"))

    keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("« Назад", callback_data="admin:back")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


async def _show_user_detail(query, context, telegram_id: int) -> int:
    """Показать детальную статистику пользователя."""

    # Аудит
    await audit_service.log_view_user_detail(query.from_user.id, telegram_id)

    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        await query.edit_message_text("⚠️ Пользователь не найден")
        return ConversationHandler.END

    # Получаем подписку
    sub = await subscription_repo.get_active(user.id)
    plan = "Premium 💎" if sub and sub.plan == "premium" else "Free 🆓"

    # Получаем статистику сообщений
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    stats_all = await conversation_repo.get_user_message_stats(user.id)
    stats_today = await conversation_repo.get_user_message_stats(user.id, since=today)
    stats_week = await conversation_repo.get_user_message_stats(user.id, since=week_ago)

    # Получаем рефералов пользователя
    referral_count = await referral_repo.count_by_referrer(user.id)

    # Формируем текст
    name = user.display_name or user.first_name or "—"
    username = f"@{user.username}" if user.username else "—"
    created = user.created_at.strftime("%d.%m.%Y") if user.created_at else "—"
    last_active = user.last_active_at.strftime("%d.%m.%Y %H:%M") if user.last_active_at else "—"

    text = f"""👤 {name}

📋 Информация:
• Username: {username}
• Telegram ID: {telegram_id}
• Зарегистрирован: {created}
• Последняя активность: {last_active}
• Подписка: {plan}

📊 Сообщения (всего):
• Всего: {stats_all['total']}
• Текст: {stats_all['text']} 📝
• Голос: {stats_all['voice']} 🎤

📅 За сегодня:
• Всего: {stats_today['total']}
• Текст: {stats_today['text']} / Голос: {stats_today['voice']}

📆 За неделю:
• Всего: {stats_week['total']}
• Текст: {stats_week['text']} / Голос: {stats_week['voice']}

👯 Рефералы: {referral_count}"""

    keyboard = [
        [InlineKeyboardButton("🎁 Выдать Premium", callback_data="admin:give_premium")],
        [InlineKeyboardButton("« К списку", callback_data="admin:users")],
        [InlineKeyboardButton("« Главное меню", callback_data="admin:back")],
    ]

    # Сохраняем данные для выдачи премиума
    context.user_data["premium_target_id"] = user.id
    context.user_data["premium_target_telegram_id"] = telegram_id
    context.user_data["premium_target_name"] = name

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


async def _show_stats(query, context) -> int:
    """Показать общую статистику."""

    # Аудит
    await audit_service.log_view_stats(query.from_user.id)

    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Получаем данные
    _, total_users = await user_repo.get_paginated(per_page=1)

    new_today = await user_repo.get_new_count(today)
    new_week = await user_repo.get_new_count(week_ago)
    new_month = await user_repo.get_new_count(month_ago)

    active_today = await user_repo.get_active_count(today)
    active_week = await user_repo.get_active_count(week_ago)

    premium_count = await subscription_repo.get_premium_count()
    free_count = await subscription_repo.get_free_count()

    # Статистика рефералов
    total_referrals = await referral_repo.get_total_count()
    referrals_week = await referral_repo.get_count_since(week_ago)

    text = f"""📊 Общая статистика

👥 Всего пользователей: {total_users}

📈 Новые:
• Сегодня: {new_today}
• За неделю: {new_week}
• За месяц: {new_month}

🔥 Активные:
• Сегодня: {active_today}
• За неделю: {active_week}

💎 Подписки:
• Premium: {premium_count}
• Free: {free_count}
• Конверсия: {premium_count / max(total_users, 1) * 100:.1f}%

👯 Рефералы:
• Всего активировано: {total_referrals}
• За неделю: {referrals_week}"""

    keyboard = [
        [InlineKeyboardButton("« Назад", callback_data="admin:back")],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


async def _show_referrals(query, context, page: int = 1) -> int:
    """Показать топ рефереров."""

    per_page = 10

    # Получаем топ рефереров
    top_referrers = await referral_repo.get_top_referrers(limit=50)

    total = len(top_referrers)
    total_pages = max(1, (total + per_page - 1) // per_page)

    # Пагинируем
    start = (page - 1) * per_page
    end = start + per_page
    page_data = top_referrers[start:end]

    lines = [f"👯 Топ рефереров ({total} всего)\n"]

    for i, ref in enumerate(page_data, start=start + 1):
        name = ref.get("display_name") or ref.get("username") or "—"
        count = ref.get("referral_count", 0)
        lines.append(f"{i}. {name} — {count} чел.")

    if not page_data:
        lines.append("Пока нет рефералов")

    # Пагинация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"admin:referrals:page:{page-1}"))
    nav_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"admin:referrals:page:{page+1}"))

    keyboard = []
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("« Назад", callback_data="admin:back")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


async def _start_give_premium(query, context) -> int:
    """Начало процесса выдачи премиума."""

    # Проверяем, есть ли уже выбранный пользователь
    if context.user_data.get("premium_target_id"):
        name = context.user_data.get("premium_target_name", "Пользователь")
        telegram_id = context.user_data.get("premium_target_telegram_id")

        await query.edit_message_text(
            f"🎁 Выдача Premium для {name}\n"
            f"Telegram ID: {telegram_id}\n\n"
            "Сколько дней Premium выдать?\n"
            "(Введи число, например: 30)\n\n"
            "Отправь /cancel для отмены"
        )
        return WAITING_DAYS

    await query.edit_message_text(
        "🎁 Выдача Premium\n\n"
        "Отправь Telegram ID пользователя:\n\n"
        "(Можно найти в списке пользователей)\n\n"
        "Отправь /cancel для отмены"
    )

    return WAITING_USER_ID


async def receive_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение ID пользователя для выдачи премиума."""

    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip()

    if text == "/cancel":
        await update.message.reply_text("❌ Отменено")
        return ConversationHandler.END

    try:
        telegram_id = int(text)
    except ValueError:
        await update.message.reply_text("⚠️ Введи числовой Telegram ID")
        return WAITING_USER_ID

    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        await update.message.reply_text(
            f"⚠️ Пользователь с ID {telegram_id} не найден.\n"
            "Попробуй другой ID или /cancel для отмены."
        )
        return WAITING_USER_ID

    # Сохраняем данные в context
    context.user_data["premium_target_id"] = user.id
    context.user_data["premium_target_telegram_id"] = telegram_id
    context.user_data["premium_target_name"] = user.display_name or user.first_name or "Пользователь"

    await update.message.reply_text(
        f"✅ Найден: {context.user_data['premium_target_name']}\n"
        f"Telegram ID: {telegram_id}\n\n"
        "Сколько дней Premium выдать?\n"
        "(Введи число, например: 30)\n\n"
        "Отправь /cancel для отмены"
    )

    return WAITING_DAYS


async def receive_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение количества дней и выдача премиума."""

    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip()

    if text == "/cancel":
        await update.message.reply_text("❌ Отменено")
        context.user_data.clear()
        return ConversationHandler.END

    try:
        days = int(text)
        if days <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Введи положительное число дней")
        return WAITING_DAYS

    user_id = context.user_data.get("premium_target_id")
    telegram_id = context.user_data.get("premium_target_telegram_id")
    user_name = context.user_data.get("premium_target_name")

    if not user_id:
        await update.message.reply_text("⚠️ Ошибка. Начни сначала /admin")
        return ConversationHandler.END

    # Выдаём премиум
    subscription = await subscription_repo.get_active(user_id)

    if subscription and subscription.plan in ["premium", "trial"]:
        # Продлеваем
        await subscription_repo.extend_days(subscription.id, days)
        action = "продлён"
    else:
        # Создаём новую
        await subscription_repo.create(
            user_id=user_id,
            plan="premium",
            duration_days=days,
        )
        action = "выдан"

    # Отправляем уведомление пользователю
    try:
        gift_message = f"""<code>🎁 Подарок от администратора!

Вам подарено {days} дней Premium-подписки.

Теперь доступно:
✨ Безлимитное общение
🧠 Полная память разговоров
🌅 Все ритуалы
📬 Проактивные сообщения

Приятного общения! 💛</code>"""

        await context.bot.send_message(
            chat_id=telegram_id,
            text=gift_message,
            parse_mode="HTML",
        )
        notification_sent = "✅ Уведомление отправлено"
    except Exception as e:
        logger.error(f"Failed to send premium notification: {e}")
        notification_sent = "⚠️ Не удалось отправить уведомление"

    await update.message.reply_text(
        f"✅ Premium {action}!\n\n"
        f"👤 {user_name}\n"
        f"📅 Дней: {days}\n\n"
        f"{notification_sent}"
    )

    logger.info(f"Admin gave {days} days premium to user {telegram_id}")

    # Аудит выдачи премиума
    is_extension = action == "продлён"
    await audit_service.log_give_premium(
        admin_telegram_id=update.effective_user.id,
        target_telegram_id=telegram_id,
        days=days,
        is_extension=is_extension,
    )

    # Очищаем данные
    context.user_data.clear()

    return ConversationHandler.END


async def cancel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена админ-операции."""
    context.user_data.clear()
    await update.message.reply_text("❌ Операция отменена")
    return ConversationHandler.END
