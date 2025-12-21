"""
Admin handlers.
Команды администратора бота.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
from loguru import logger

from database.repositories.user import UserRepository
from database.repositories.subscription import SubscriptionRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.referral import ReferralRepository
from database.repositories.promo import promo_repo
from config.settings import settings
from services.audit import audit_service
from services.export import export_service


# Telegram ID администратора
ADMIN_ID = 65876198

# Состояния для ConversationHandler
WAITING_USER_ID = 1
WAITING_DAYS = 2
WAITING_BLOCK_REASON = 3
WAITING_BROADCAST_MESSAGE = 4
WAITING_PROMO_CODE = 5
WAITING_PROMO_TYPE = 6
WAITING_PROMO_VALUE = 7
WAITING_PROMO_MAX_USES = 8

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
        [InlineKeyboardButton("🌐 Web-админка", callback_data="admin:web_admin")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton("👯 Рефералы", callback_data="admin:referrals")],
        [InlineKeyboardButton("🎁 Выдать Premium", callback_data="admin:give_premium")],
        [InlineKeyboardButton("🎟️ Промокоды", callback_data="admin:promos")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton("📥 Экспорт", callback_data="admin:export")],
        [InlineKeyboardButton("🚫 Заблокированные", callback_data="admin:blocked")],
    ]

    text = """🔧 Админ-панель

Выбери действие:"""

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def web_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /web_admin - отправляет ссылку на веб-админку с токеном."""

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ У тебя нет доступа к этой команде.")
        return

    admin_url = f"https://mira.uspeshnyy.ru/admin?token={settings.ADMIN_TOKEN}"

    await update.message.reply_text(
        f"🌐 <b>Web-админка</b>\n\n"
        f"<a href=\"{admin_url}\">Открыть админ-панель</a>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик callback-кнопок админки."""

    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔ У тебя нет доступа.")
        return ConversationHandler.END

    data = query.data

    if data == "admin:web_admin":
        admin_url = f"https://mira.uspeshnyy.ru/admin?token={settings.ADMIN_TOKEN}"
        await query.message.reply_text(
            f"🌐 <b>Web-админка</b>\n\n"
            f"<a href=\"{admin_url}\">Открыть админ-панель</a>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return ConversationHandler.END

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

    elif data == "admin:export":
        return await _show_export_menu(query, context)

    elif data.startswith("admin:export:"):
        return await _handle_export(query, context, data)

    elif data.startswith("admin:broadcast:segment:"):
        segment = data.split(":")[-1]
        return await _start_broadcast(query, context, segment)

    elif data == "admin:broadcast:confirm":
        return await _confirm_broadcast(query, context)

    elif data == "admin:broadcast:cancel":
        context.user_data.clear()
        return await _show_main_menu(query, context)

    elif data.startswith("admin:history:"):
        parts = data.split(":")
        telegram_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 1
        return await _show_conversation_history(query, context, telegram_id, page)

    elif data == "admin:promos":
        return await _show_promos_menu(query, context)

    elif data == "admin:promos:create":
        return await _start_create_promo(query, context)

    elif data.startswith("admin:promos:list:"):
        page = int(data.split(":")[-1])
        return await _show_promos_list(query, context, page)

    elif data.startswith("admin:promo:view:"):
        promo_id = int(data.split(":")[-1])
        return await _show_promo_detail(query, context, promo_id)

    elif data.startswith("admin:promo:toggle:"):
        promo_id = int(data.split(":")[-1])
        return await _toggle_promo(query, context, promo_id)

    elif data.startswith("admin:promo:delete:"):
        promo_id = int(data.split(":")[-1])
        return await _delete_promo(query, context, promo_id)

    elif data.startswith("admin:promo:type:"):
        promo_type = data.split(":")[-1]
        return await _receive_promo_type(query, context, promo_type)

    return ConversationHandler.END


async def _show_main_menu(query, context) -> int:
    """Показать главное меню."""

    keyboard = [
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton("👯 Рефералы", callback_data="admin:referrals")],
        [InlineKeyboardButton("🎁 Выдать Premium", callback_data="admin:give_premium")],
        [InlineKeyboardButton("🎟️ Промокоды", callback_data="admin:promos")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton("📥 Экспорт", callback_data="admin:export")],
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
        [InlineKeyboardButton("💬 История диалога", callback_data=f"admin:history:{telegram_id}")],
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


async def _show_export_menu(query, context) -> int:
    """Показать меню экспорта."""

    keyboard = [
        [InlineKeyboardButton("📊 Сводка (CSV)", callback_data="admin:export:summary:csv")],
        [InlineKeyboardButton("👥 Пользователи (CSV)", callback_data="admin:export:users:csv")],
        [InlineKeyboardButton("👥 Пользователи (Excel)", callback_data="admin:export:users:xlsx")],
        [InlineKeyboardButton("👯 Рефералы (CSV)", callback_data="admin:export:referrals:csv")],
        [InlineKeyboardButton("« Назад", callback_data="admin:back")],
    ]

    text = """📥 Экспорт статистики

Выбери тип отчёта:

• **Сводка** — общая статистика
• **Пользователи** — список всех пользователей
• **Рефералы** — топ рефереров"""

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def _handle_export(query, context, data: str) -> int:
    """Обработка экспорта статистики."""

    await query.answer("⏳ Генерирую отчёт...")

    parts = data.split(":")
    export_type = parts[2]  # summary, users, referrals
    export_format = parts[3]  # csv, xlsx

    now = datetime.now()
    date_str = now.strftime("%Y%m%d_%H%M")

    try:
        if export_type == "summary" and export_format == "csv":
            file_bytes = await export_service.export_summary_csv()
            filename = f"mira_summary_{date_str}.csv"
            caption = "📊 Сводная статистика"

        elif export_type == "users" and export_format == "csv":
            file_bytes = await export_service.export_users_csv()
            filename = f"mira_users_{date_str}.csv"
            caption = "👥 Список пользователей (CSV)"

        elif export_type == "users" and export_format == "xlsx":
            file_bytes = await export_service.export_users_excel()
            filename = f"mira_users_{date_str}.xlsx"
            caption = "👥 Список пользователей (Excel)"

        elif export_type == "referrals" and export_format == "csv":
            file_bytes = await export_service.export_referrals_csv()
            filename = f"mira_referrals_{date_str}.csv"
            caption = "👯 Топ рефереров"

        else:
            await query.edit_message_text("⚠️ Неизвестный тип экспорта")
            return ConversationHandler.END

        # Отправляем файл
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=file_bytes,
            filename=filename,
            caption=f"{caption}\n📅 {now.strftime('%d.%m.%Y %H:%M')}",
        )

        # Аудит
        logger.info(f"Admin {query.from_user.id} exported {export_type} as {export_format}")

        # Показываем меню экспорта снова
        keyboard = [
            [InlineKeyboardButton("📥 Ещё экспорт", callback_data="admin:export")],
            [InlineKeyboardButton("« Главное меню", callback_data="admin:back")],
        ]

        await query.edit_message_text(
            f"✅ Отчёт отправлен!\n\n📄 {filename}",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        logger.error(f"Export error: {e}")
        await query.edit_message_text(
            f"❌ Ошибка экспорта: {str(e)[:100]}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Назад", callback_data="admin:export")]
            ]),
        )

    return ConversationHandler.END


async def _show_conversation_history(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
    page: int = 1,
) -> int:
    """Показывает историю диалога пользователя."""
    from database.repositories.user import UserRepository
    from database.repositories.conversation import ConversationRepository
    from database.session import async_session_factory

    per_page = 10

    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        conversation_repo = ConversationRepository(session)

        # Получаем пользователя
        user = await user_repo.get_by_telegram_id(telegram_id)
        if not user:
            await query.answer("Пользователь не найден", show_alert=True)
            return ConversationHandler.END

        # Получаем сообщения с пагинацией
        messages, total = await conversation_repo.get_paginated(
            user_id=user.id,
            page=page,
            per_page=per_page,
        )

        total_pages = (total + per_page - 1) // per_page if total > 0 else 1

        # Формируем текст
        display_name = user.display_name or user.first_name or f"ID:{telegram_id}"
        text = f"💬 История диалога: {display_name}\n"
        text += f"📄 Страница {page}/{total_pages} (всего: {total})\n"
        text += "─" * 30 + "\n\n"

        if not messages:
            text += "📭 Сообщений нет"
        else:
            for msg in messages:
                # Иконка роли
                role_icon = "👤" if msg.role == "user" else "🤖"

                # Время сообщения
                time_str = msg.created_at.strftime("%d.%m %H:%M") if msg.created_at else ""

                # Тип сообщения
                type_icon = ""
                if hasattr(msg, 'is_voice') and msg.is_voice:
                    type_icon = "🎤 "

                # Текст сообщения (обрезаем длинные)
                content = msg.content or ""
                if len(content) > 200:
                    content = content[:200] + "..."

                text += f"{role_icon} {type_icon}[{time_str}]\n{content}\n\n"

        # Клавиатура пагинации
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton("« Назад", callback_data=f"admin:history:{telegram_id}:{page-1}")
            )
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton("Вперёд »", callback_data=f"admin:history:{telegram_id}:{page+1}")
            )

        keyboard = []
        if nav_buttons:
            keyboard.append(nav_buttons)
        keyboard.append([
            InlineKeyboardButton("« К профилю", callback_data=f"admin:user:{telegram_id}")
        ])
        keyboard.append([
            InlineKeyboardButton("« Главное меню", callback_data="admin:back")
        ])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    return ConversationHandler.END


# ==================== ПРОМОКОДЫ ====================

PROMO_TYPES = {
    "free_days": "🎁 Бесплатные дни Premium",
    "free_trial": "🆓 Trial период",
    "discount_percent": "💰 Скидка %",
    "discount_amount": "💵 Скидка ₽",
}


async def _show_promos_menu(query, context) -> int:
    """Показать меню промокодов."""

    # Получаем статистику
    promos, total = await promo_repo.get_all(page=1, per_page=1)
    active_promos, active_total = await promo_repo.get_all(active_only=True, page=1, per_page=1)

    text = f"""🎟️ Управление промокодами

📊 Статистика:
• Всего промокодов: {total}
• Активных: {active_total}

Выбери действие:"""

    keyboard = [
        [InlineKeyboardButton("➕ Создать промокод", callback_data="admin:promos:create")],
        [InlineKeyboardButton("📋 Список промокодов", callback_data="admin:promos:list:1")],
        [InlineKeyboardButton("« Назад", callback_data="admin:back")],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


async def _show_promos_list(query, context, page: int = 1) -> int:
    """Показать список промокодов."""

    per_page = 8
    promos, total = await promo_repo.get_all(page=page, per_page=per_page)

    total_pages = max(1, (total + per_page - 1) // per_page)

    lines = [f"📋 Промокоды ({total} всего)\n"]

    if not promos:
        lines.append("Нет промокодов. Создай первый!")
    else:
        for promo in promos:
            status = "✅" if promo.is_active else "❌"
            type_emoji = "🎁" if promo.promo_type in ("free_days", "free_trial") else "💰"
            uses = f"{promo.current_uses}/{promo.max_uses}" if promo.max_uses else f"{promo.current_uses}/∞"
            lines.append(f"{status} {type_emoji} {promo.code}")
            lines.append(f"   Использовано: {uses}")

    # Кнопки промокодов
    promo_buttons = []
    for promo in promos:
        status = "✅" if promo.is_active else "❌"
        promo_buttons.append(
            InlineKeyboardButton(
                f"{status} {promo.code}",
                callback_data=f"admin:promo:view:{promo.id}"
            )
        )

    keyboard = []
    for i in range(0, len(promo_buttons), 2):
        row = promo_buttons[i:i + 2]
        keyboard.append(row)

    # Пагинация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"admin:promos:list:{page - 1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"admin:promos:list:{page + 1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("➕ Создать", callback_data="admin:promos:create")])
    keyboard.append([InlineKeyboardButton("« Назад", callback_data="admin:promos")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


async def _show_promo_detail(query, context, promo_id: int) -> int:
    """Показать детали промокода."""

    promo = await promo_repo.get_by_id(promo_id)

    if not promo:
        await query.answer("Промокод не найден", show_alert=True)
        return ConversationHandler.END

    # Получаем статистику использования
    stats = await promo_repo.get_usage_stats(promo_id)

    status = "✅ Активен" if promo.is_active else "❌ Неактивен"
    type_name = PROMO_TYPES.get(promo.promo_type, promo.promo_type)

    # Форматируем значение в зависимости от типа
    if promo.promo_type == "discount_percent":
        value_str = f"{promo.value}%"
    elif promo.promo_type == "discount_amount":
        value_str = f"{promo.value}₽"
    else:
        value_str = f"{promo.value} дней"

    uses_str = f"{promo.current_uses}/{promo.max_uses}" if promo.max_uses else f"{promo.current_uses}/∞"

    # Срок действия
    valid_str = "Бессрочно"
    if promo.valid_until:
        valid_str = f"До {promo.valid_until.strftime('%d.%m.%Y %H:%M')}"

    text = f"""🎟️ Промокод: {promo.code}

📋 Информация:
• Статус: {status}
• Тип: {type_name}
• Значение: {value_str}
• Описание: {promo.description or "—"}

📊 Использование:
• Всего: {uses_str}
• Уникальных пользователей: {stats['unique_users']}
• Макс. на пользователя: {promo.max_uses_per_user}

⏰ Срок действия: {valid_str}

📈 Результаты:
• Выдано бесплатных дней: {stats['total_free_days'] or 0}
• Сумма скидок: {stats['total_discount'] or 0}₽"""

    # Кнопки действий
    toggle_text = "❌ Деактивировать" if promo.is_active else "✅ Активировать"

    keyboard = [
        [InlineKeyboardButton(toggle_text, callback_data=f"admin:promo:toggle:{promo.id}")],
    ]

    # Удаление только если не использовался
    if promo.current_uses == 0:
        keyboard.append([
            InlineKeyboardButton("🗑 Удалить", callback_data=f"admin:promo:delete:{promo.id}")
        ])

    keyboard.append([InlineKeyboardButton("« К списку", callback_data="admin:promos:list:1")])
    keyboard.append([InlineKeyboardButton("« Главное меню", callback_data="admin:back")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


async def _toggle_promo(query, context, promo_id: int) -> int:
    """Включить/выключить промокод."""

    promo = await promo_repo.get_by_id(promo_id)

    if not promo:
        await query.answer("Промокод не найден", show_alert=True)
        return ConversationHandler.END

    if promo.is_active:
        await promo_repo.deactivate(promo_id)
        await query.answer("❌ Промокод деактивирован")
    else:
        await promo_repo.activate(promo_id)
        await query.answer("✅ Промокод активирован")

    logger.info(f"Admin toggled promo {promo.code}: active={not promo.is_active}")

    return await _show_promo_detail(query, context, promo_id)


async def _delete_promo(query, context, promo_id: int) -> int:
    """Удалить промокод."""

    success = await promo_repo.delete(promo_id)

    if success:
        await query.answer("🗑 Промокод удалён")
        logger.info(f"Admin deleted promo {promo_id}")
        return await _show_promos_list(query, context, page=1)
    else:
        await query.answer("⚠️ Невозможно удалить промокод (уже использовался)", show_alert=True)
        return await _show_promo_detail(query, context, promo_id)


async def _start_create_promo(query, context) -> int:
    """Начать создание промокода."""

    await query.edit_message_text(
        "🎟️ Создание промокода\n\n"
        "Введи код промокода (латиница, цифры):\n"
        "Например: SUMMER2024, WELCOME, VIP50\n\n"
        "Отправь /cancel для отмены"
    )

    return WAITING_PROMO_CODE


async def receive_promo_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение кода промокода."""

    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip().upper()

    if text == "/CANCEL":
        await update.message.reply_text("❌ Создание отменено")
        context.user_data.clear()
        return ConversationHandler.END

    # Валидация кода
    import re
    if not re.match(r'^[A-Z0-9_-]{3,30}$', text):
        await update.message.reply_text(
            "⚠️ Код должен содержать только латиницу, цифры, _ и -\n"
            "Длина: 3-30 символов\n\n"
            "Попробуй снова:"
        )
        return WAITING_PROMO_CODE

    # Проверяем уникальность
    existing = await promo_repo.get_by_code(text)
    if existing:
        await update.message.reply_text(
            f"⚠️ Промокод {text} уже существует!\n"
            "Введи другой код:"
        )
        return WAITING_PROMO_CODE

    # Сохраняем код
    context.user_data["new_promo_code"] = text

    # Спрашиваем тип
    keyboard = [
        [InlineKeyboardButton("🎁 Бесплатные дни", callback_data="admin:promo:type:free_days")],
        [InlineKeyboardButton("🆓 Trial период", callback_data="admin:promo:type:free_trial")],
        [InlineKeyboardButton("💰 Скидка %", callback_data="admin:promo:type:discount_percent")],
        [InlineKeyboardButton("💵 Скидка ₽", callback_data="admin:promo:type:discount_amount")],
    ]

    await update.message.reply_text(
        f"✅ Код: {text}\n\n"
        "Выбери тип промокода:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return ConversationHandler.END


async def _receive_promo_type(query, context, promo_type: str) -> int:
    """Получение типа промокода."""

    context.user_data["new_promo_type"] = promo_type

    type_name = PROMO_TYPES.get(promo_type, promo_type)
    code = context.user_data.get("new_promo_code", "???")

    if promo_type in ("free_days", "free_trial"):
        prompt = "Сколько дней Premium/Trial дать?"
        example = "Например: 7, 14, 30"
    elif promo_type == "discount_percent":
        prompt = "Какой процент скидки?"
        example = "Например: 10, 25, 50"
    else:
        prompt = "Какая скидка в рублях?"
        example = "Например: 100, 200, 500"

    await query.edit_message_text(
        f"🎟️ Создание: {code}\n"
        f"Тип: {type_name}\n\n"
        f"{prompt}\n{example}\n\n"
        "Отправь /cancel для отмены"
    )

    return WAITING_PROMO_VALUE


async def receive_promo_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение значения промокода."""

    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip()

    if text.lower() == "/cancel":
        await update.message.reply_text("❌ Создание отменено")
        context.user_data.clear()
        return ConversationHandler.END

    try:
        value = int(text)
        if value <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Введи положительное число")
        return WAITING_PROMO_VALUE

    promo_type = context.user_data.get("new_promo_type")

    # Валидация значений
    if promo_type == "discount_percent" and value > 100:
        await update.message.reply_text("⚠️ Скидка не может быть больше 100%")
        return WAITING_PROMO_VALUE

    context.user_data["new_promo_value"] = value

    code = context.user_data.get("new_promo_code", "???")
    type_name = PROMO_TYPES.get(promo_type, promo_type)

    if promo_type in ("free_days", "free_trial"):
        value_str = f"{value} дней"
    elif promo_type == "discount_percent":
        value_str = f"{value}%"
    else:
        value_str = f"{value}₽"

    await update.message.reply_text(
        f"🎟️ Создание: {code}\n"
        f"Тип: {type_name}\n"
        f"Значение: {value_str}\n\n"
        "Сколько раз можно использовать?\n"
        "Введи число или - для безлимита\n\n"
        "Отправь /cancel для отмены"
    )

    return WAITING_PROMO_MAX_USES


async def receive_promo_max_uses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение лимита использований и создание промокода."""

    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip()

    if text.lower() == "/cancel":
        await update.message.reply_text("❌ Создание отменено")
        context.user_data.clear()
        return ConversationHandler.END

    max_uses = None
    if text != "-":
        try:
            max_uses = int(text)
            if max_uses <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Введи положительное число или - для безлимита")
            return WAITING_PROMO_MAX_USES

    # Создаём промокод
    code = context.user_data.get("new_promo_code")
    promo_type = context.user_data.get("new_promo_type")
    value = context.user_data.get("new_promo_value")

    try:
        promo = await promo_repo.create(
            code=code,
            promo_type=promo_type,
            value=value,
            max_uses=max_uses,
            created_by_admin_id=update.effective_user.id,
        )

        type_name = PROMO_TYPES.get(promo_type, promo_type)

        if promo_type in ("free_days", "free_trial"):
            value_str = f"{value} дней"
        elif promo_type == "discount_percent":
            value_str = f"{value}%"
        else:
            value_str = f"{value}₽"

        uses_str = str(max_uses) if max_uses else "∞"

        await update.message.reply_text(
            f"✅ Промокод создан!\n\n"
            f"🎟️ Код: {promo.code}\n"
            f"📋 Тип: {type_name}\n"
            f"💫 Значение: {value_str}\n"
            f"🔢 Лимит: {uses_str}\n\n"
            f"Пользователи могут активировать его командой:\n"
            f"/promo {promo.code}"
        )

        logger.info(f"Admin created promo: {promo.code} ({promo_type}={value})")

    except Exception as e:
        logger.error(f"Failed to create promo: {e}")
        await update.message.reply_text(f"❌ Ошибка создания: {str(e)[:100]}")

    context.user_data.clear()
    return ConversationHandler.END
