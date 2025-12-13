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
WAITING_BLOCK_REASON = 3
WAITING_BROADCAST_MESSAGE = 4

# Сегменты для рассылки
BROADCAST_SEGMENTS = {
    "all": "👥 Все пользователи",
    "premium": "💎 Только Premium",
    "free": "🆓 Только Free",
    "active_week": "🔥 Активные за неделю",
    "active_month": "📅 Активные за месяц",
    "inactive": "😴 Неактивные (>30 дней)",
}

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
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton("🚫 Заблокированные", callback_data="admin:blocked")],
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

    elif data == "admin:blocked":
        return await _show_blocked_users(query, context)

    elif data.startswith("admin:blocked:page:"):
        page = int(data.split(":")[-1])
        return await _show_blocked_users(query, context, page=page)

    elif data.startswith("admin:block:"):
        telegram_id = int(data.split(":")[-1])
        return await _start_block_user(query, context, telegram_id)

    elif data.startswith("admin:unblock:"):
        telegram_id = int(data.split(":")[-1])
        return await _unblock_user(query, context, telegram_id)

    elif data == "admin:broadcast":
        return await _show_broadcast_menu(query, context)

    elif data.startswith("admin:broadcast:segment:"):
        segment = data.split(":")[-1]
        return await _start_broadcast(query, context, segment)

    elif data == "admin:broadcast:confirm":
        return await _confirm_broadcast(query, context)

    elif data == "admin:broadcast:cancel":
        context.user_data.clear()
        return await _show_main_menu(query, context)

    return ConversationHandler.END


async def _show_main_menu(query, context) -> int:
    """Показать главное меню."""

    keyboard = [
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton("👯 Рефералы", callback_data="admin:referrals")],
        [InlineKeyboardButton("🎁 Выдать Premium", callback_data="admin:give_premium")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton("🚫 Заблокированные", callback_data="admin:blocked")],
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

    # Статус блокировки
    block_status = ""
    if user.is_blocked:
        block_reason = user.block_reason or "не указана"
        block_status = f"\n\n🚫 ЗАБЛОКИРОВАН\nПричина: {block_reason}"

    text = f"""👤 {name}

📋 Информация:
• Username: {username}
• Telegram ID: {telegram_id}
• Зарегистрирован: {created}
• Последняя активность: {last_active}
• Подписка: {plan}{block_status}

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

    # Кнопки действий
    if user.is_blocked:
        block_button = InlineKeyboardButton(
            "✅ Разблокировать",
            callback_data=f"admin:unblock:{telegram_id}"
        )
    else:
        block_button = InlineKeyboardButton(
            "🚫 Заблокировать",
            callback_data=f"admin:block:{telegram_id}"
        )

    keyboard = [
        [InlineKeyboardButton("🎁 Выдать Premium", callback_data="admin:give_premium")],
        [block_button],
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


async def _show_blocked_users(query, context, page: int = 1) -> int:
    """Показать список заблокированных пользователей."""

    # Аудит
    await audit_service.log_view_blocked(query.from_user.id, page)

    per_page = 10
    users, total = await user_repo.get_blocked_users(page=page, per_page=per_page)

    total_pages = max(1, (total + per_page - 1) // per_page)

    lines = [f"🚫 Заблокированные ({total} всего)\n"]

    if not users:
        lines.append("Нет заблокированных пользователей")
    else:
        for user in users:
            name = user.display_name or user.first_name or "—"
            reason = user.block_reason[:30] + "..." if user.block_reason and len(user.block_reason) > 30 else (user.block_reason or "—")
            lines.append(f"• {name} (ID: {user.telegram_id})")
            lines.append(f"  Причина: {reason}")

    # Кнопки пользователей для разблокировки
    user_buttons = []
    for user in users:
        user_buttons.append(
            InlineKeyboardButton(
                f"✅ {user.telegram_id}",
                callback_data=f"admin:unblock:{user.telegram_id}"
            )
        )

    keyboard = []

    # Кнопки разблокировки по 2 в ряд
    for i in range(0, len(user_buttons), 2):
        row = user_buttons[i:i + 2]
        keyboard.append(row)

    # Пагинация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"admin:blocked:page:{page - 1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"admin:blocked:page:{page + 1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("« Назад", callback_data="admin:back")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


async def _start_block_user(query, context, telegram_id: int) -> int:
    """Начать процесс блокировки пользователя."""

    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        await query.edit_message_text("⚠️ Пользователь не найден")
        return ConversationHandler.END

    if user.is_blocked:
        await query.edit_message_text("⚠️ Пользователь уже заблокирован")
        return ConversationHandler.END

    # Сохраняем данные для блокировки
    context.user_data["block_target_telegram_id"] = telegram_id
    context.user_data["block_target_name"] = user.display_name or user.first_name or "Пользователь"

    await query.edit_message_text(
        f"🚫 Блокировка пользователя\n\n"
        f"👤 {context.user_data['block_target_name']}\n"
        f"ID: {telegram_id}\n\n"
        "Укажи причину блокировки:\n"
        "(или отправь '-' для блокировки без причины)\n\n"
        "Отправь /cancel для отмены"
    )

    return WAITING_BLOCK_REASON


async def receive_block_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение причины блокировки."""

    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip()

    if text == "/cancel":
        await update.message.reply_text("❌ Блокировка отменена")
        context.user_data.clear()
        return ConversationHandler.END

    telegram_id = context.user_data.get("block_target_telegram_id")
    user_name = context.user_data.get("block_target_name")

    if not telegram_id:
        await update.message.reply_text("⚠️ Ошибка. Начни сначала /admin")
        return ConversationHandler.END

    # Определяем причину
    reason = None if text == "-" else text

    # Блокируем пользователя
    user = await user_repo.block_user(telegram_id, reason)

    if not user:
        await update.message.reply_text("⚠️ Не удалось заблокировать пользователя")
        context.user_data.clear()
        return ConversationHandler.END

    # Аудит
    await audit_service.log_block_user(
        admin_telegram_id=update.effective_user.id,
        target_telegram_id=telegram_id,
        reason=reason,
    )

    logger.info(f"Admin blocked user {telegram_id}, reason: {reason}")

    reason_text = reason if reason else "не указана"
    await update.message.reply_text(
        f"🚫 Пользователь заблокирован\n\n"
        f"👤 {user_name}\n"
        f"ID: {telegram_id}\n"
        f"Причина: {reason_text}"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def _unblock_user(query, context, telegram_id: int) -> int:
    """Разблокировать пользователя."""

    user = await user_repo.unblock_user(telegram_id)

    if not user:
        await query.edit_message_text("⚠️ Пользователь не найден")
        return ConversationHandler.END

    # Аудит
    await audit_service.log_unblock_user(
        admin_telegram_id=query.from_user.id,
        target_telegram_id=telegram_id,
    )

    logger.info(f"Admin unblocked user {telegram_id}")

    name = user.display_name or user.first_name or "Пользователь"

    keyboard = [
        [InlineKeyboardButton("👤 К профилю", callback_data=f"admin:user:{telegram_id}")],
        [InlineKeyboardButton("🚫 Заблокированные", callback_data="admin:blocked")],
        [InlineKeyboardButton("« Главное меню", callback_data="admin:back")],
    ]

    await query.edit_message_text(
        f"✅ Пользователь разблокирован\n\n"
        f"👤 {name}\n"
        f"ID: {telegram_id}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return ConversationHandler.END


async def _show_broadcast_menu(query, context) -> int:
    """Показать меню рассылки с сегментами."""

    lines = ["📢 Рассылка сообщений\n", "Выбери сегмент получателей:\n"]

    keyboard = []
    for segment_key, segment_name in BROADCAST_SEGMENTS.items():
        count = await user_repo.count_by_segment(segment_key)
        keyboard.append([
            InlineKeyboardButton(
                f"{segment_name} ({count})",
                callback_data=f"admin:broadcast:segment:{segment_key}"
            )
        ])

    keyboard.append([InlineKeyboardButton("« Назад", callback_data="admin:back")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


async def _start_broadcast(query, context, segment: str) -> int:
    """Начать создание рассылки для выбранного сегмента."""

    count = await user_repo.count_by_segment(segment)
    segment_name = BROADCAST_SEGMENTS.get(segment, segment)

    if count == 0:
        keyboard = [[InlineKeyboardButton("« Назад", callback_data="admin:broadcast")]]
        await query.edit_message_text(
            f"⚠️ В сегменте «{segment_name}» нет пользователей",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return ConversationHandler.END

    # Сохраняем данные для рассылки
    context.user_data["broadcast_segment"] = segment
    context.user_data["broadcast_segment_name"] = segment_name
    context.user_data["broadcast_count"] = count

    await query.edit_message_text(
        f"📢 Рассылка: {segment_name}\n"
        f"👥 Получателей: {count}\n\n"
        "Отправь текст сообщения для рассылки.\n"
        "Поддерживается HTML-разметка:\n"
        "• <b>жирный</b>\n"
        "• <i>курсив</i>\n"
        "• <code>код</code>\n\n"
        "Отправь /cancel для отмены"
    )

    return WAITING_BROADCAST_MESSAGE


async def receive_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение текста рассылки."""

    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip()

    if text == "/cancel":
        await update.message.reply_text("❌ Рассылка отменена")
        context.user_data.clear()
        return ConversationHandler.END

    segment = context.user_data.get("broadcast_segment")
    segment_name = context.user_data.get("broadcast_segment_name")
    count = context.user_data.get("broadcast_count")

    if not segment:
        await update.message.reply_text("⚠️ Ошибка. Начни сначала /admin")
        return ConversationHandler.END

    # Сохраняем текст
    context.user_data["broadcast_message"] = text

    # Показываем превью и запрос подтверждения
    preview = text[:500] + "..." if len(text) > 500 else text

    keyboard = [
        [InlineKeyboardButton("✅ Отправить", callback_data="admin:broadcast:confirm")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin:broadcast:cancel")],
    ]

    await update.message.reply_text(
        f"📢 Подтверждение рассылки\n\n"
        f"Сегмент: {segment_name}\n"
        f"Получателей: {count}\n\n"
        f"━━━ Превью ━━━\n{preview}\n━━━━━━━━━━━━\n\n"
        f"Подтвердить отправку?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

    return ConversationHandler.END


async def _confirm_broadcast(query, context) -> int:
    """Подтверждение и выполнение рассылки."""
    import asyncio

    segment = context.user_data.get("broadcast_segment")
    segment_name = context.user_data.get("broadcast_segment_name")
    message_text = context.user_data.get("broadcast_message")

    if not segment or not message_text:
        await query.edit_message_text("⚠️ Ошибка. Начни сначала /admin")
        return ConversationHandler.END

    # Получаем список получателей
    telegram_ids = await user_repo.get_all_telegram_ids(segment=segment)
    total = len(telegram_ids)

    # Аудит начала рассылки
    await audit_service.log_broadcast_start(
        admin_telegram_id=query.from_user.id,
        segment=segment,
        total_users=total,
        message_preview=message_text,
    )

    await query.edit_message_text(
        f"📢 Рассылка началась...\n\n"
        f"Сегмент: {segment_name}\n"
        f"Всего получателей: {total}\n\n"
        f"⏳ Отправка..."
    )

    # Счётчики
    sent = 0
    failed = 0
    blocked_by_user = 0

    # Отправляем сообщения
    for i, telegram_id in enumerate(telegram_ids):
        try:
            await context.bot.send_message(
                chat_id=telegram_id,
                text=message_text,
                parse_mode="HTML",
            )
            sent += 1
        except Exception as e:
            error_str = str(e).lower()
            if "blocked" in error_str or "deactivated" in error_str:
                blocked_by_user += 1
            else:
                failed += 1
            logger.warning(f"Broadcast failed for {telegram_id}: {e}")

        # Задержка между сообщениями (избегаем rate limit)
        if (i + 1) % 25 == 0:
            await asyncio.sleep(1)

        # Обновляем прогресс каждые 50 сообщений
        if (i + 1) % 50 == 0:
            try:
                await query.edit_message_text(
                    f"📢 Рассылка в процессе...\n\n"
                    f"Сегмент: {segment_name}\n"
                    f"Прогресс: {i + 1}/{total}\n"
                    f"✅ Отправлено: {sent}\n"
                    f"❌ Ошибок: {failed}\n"
                    f"🚫 Заблокировали бота: {blocked_by_user}"
                )
            except Exception:
                pass  # Игнорируем ошибки обновления

    # Аудит завершения
    await audit_service.log_broadcast_complete(
        admin_telegram_id=query.from_user.id,
        segment=segment,
        sent=sent,
        failed=failed,
        blocked_by_user=blocked_by_user,
    )

    logger.info(
        f"Broadcast complete: segment={segment}, sent={sent}, "
        f"failed={failed}, blocked={blocked_by_user}"
    )

    keyboard = [[InlineKeyboardButton("« Главное меню", callback_data="admin:back")]]

    await query.edit_message_text(
        f"📢 Рассылка завершена!\n\n"
        f"Сегмент: {segment_name}\n"
        f"Всего: {total}\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}\n"
        f"🚫 Заблокировали бота: {blocked_by_user}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    context.user_data.clear()
    return ConversationHandler.END
