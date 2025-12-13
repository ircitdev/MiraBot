"""
Command handlers.
Обработчики команд бота.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from datetime import datetime

from database.repositories.user import UserRepository
from database.repositories.subscription import SubscriptionRepository
from services.referral import ReferralService
from config.settings import settings


user_repo = UserRepository()
subscription_repo = SubscriptionRepository()
referral_service = ReferralService()


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /settings."""
    
    user = await user_repo.get_by_telegram_id(update.effective_user.id)
    
    if not user:
        await update.message.reply_text("Сначала напиши /start 💛")
        return

    proactive = "✅" if user.proactive_messages else "❌"
    
    keyboard = [
        [InlineKeyboardButton(
            f"📬 Проактивные сообщения: {proactive}",
            callback_data="settings:toggle_proactive"
        )],
        [InlineKeyboardButton(
            "⏰ Время ритуалов",
            callback_data="settings:ritual_time"
        )],
        [InlineKeyboardButton(
            "📝 Изменить имя",
            callback_data="settings:change_name"
        )],
    ]
    
    text = f"""⚙️ Настройки

Твоё имя: {user.display_name or 'не указано'}
Проактивные сообщения: {'включены' if user.proactive_messages else 'отключены'}

Что хочешь изменить?"""

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def subscription_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /subscription."""
    
    user = await user_repo.get_by_telegram_id(update.effective_user.id)
    
    if not user:
        await update.message.reply_text("Сначала напиши /start 💛")
        return
    
    subscription = await subscription_repo.get_active(user.id)
    
    if not subscription or subscription.plan == "free":
        # Бесплатный план
        messages_left = settings.FREE_MESSAGES_PER_DAY - (subscription.messages_today if subscription else 0)
        
        keyboard = [
            [InlineKeyboardButton("✨ Подключить Premium", callback_data="subscribe:show")]
        ]
        
        text = f"""📊 **Твоя подписка:** Free

**Доступно сегодня:** {messages_left} сообщений из {settings.FREE_MESSAGES_PER_DAY}

**Что входит в Free:**
• {settings.FREE_MESSAGES_PER_DAY} сообщений в день
• Базовая персона
• 1 ритуал на выбор

**Что даёт Premium:**
• Безлимитное общение
• Полная память о наших разговорах
• Все ритуалы и проактивные сообщения
• Еженедельные рефлексии

Хочешь больше?"""
        
    else:
        # Премиум план
        days_left = (subscription.expires_at - datetime.now()).days if subscription.expires_at else "∞"
        auto_status = "✅ подключён" if subscription.auto_renew else "❌ отключён"
        
        keyboard = []
        
        if subscription.auto_renew:
            keyboard.append([InlineKeyboardButton(
                "🔄 Отключить автоплатёж",
                callback_data="subscription:cancel_auto"
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                "🔄 Включить автоплатёж",
                callback_data="subscription:enable_auto"
            )])
        
        keyboard.append([InlineKeyboardButton(
            "📜 История платежей",
            callback_data="subscription:history"
        )])
        
        expires_str = subscription.expires_at.strftime('%d.%m.%Y') if subscription.expires_at else "бессрочно"
        
        text = f"""📊 **Твоя подписка:** Premium ✨

⏳ **Осталось дней:** {days_left}
📅 **Действует до:** {expires_str}
🔄 **Автоплатёж:** {auto_status}

Спасибо, что ты со мной 💛"""
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /referral."""

    user = await user_repo.get_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Сначала напиши /start 💛")
        return

    stats = await referral_service.get_stats(user.id)

    code = stats["code"]
    invited = stats["invited_count"]
    bonus_days = stats["bonus_earned_days"]
    next_milestone = stats["next_milestone"]

    # Формируем ссылку
    bot_username = (await context.bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start={code}"

    milestone_text = f"До бонуса за 3 подруг осталось: {next_milestone}" if next_milestone else "Ты получила бонус за 3 подруг!"

    text = f"""👯‍♀️ Реферальная программа

Твой код: {code}

📊 Статистика:
• Приглашено подруг: {invited}
• Заработано дней: {bonus_days}

🎁 Как это работает:
1. Поделись ссылкой с подругой
2. Когда она зарегистрируется — вы обе получите +7 дней Premium
3. После 3 подруг — ещё месяц бесплатно!

{milestone_text}

Ссылка для приглашения:
{invite_link}"""

    keyboard = [
        [InlineKeyboardButton("📤 Поделиться", url=f"https://t.me/share/url?url={invite_link}")],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def rituals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /rituals."""
    
    user = await user_repo.get_by_telegram_id(update.effective_user.id)
    
    if not user:
        await update.message.reply_text("Сначала напиши /start 💛")
        return
    
    rituals = user.rituals_enabled or []
    
    morning_status = "✅" if "morning" in rituals else "❌"
    evening_status = "✅" if "evening" in rituals else "❌"
    gratitude_status = "✅" if "gratitude" in rituals else "❌"
    letter_status = "✅" if "letter" in rituals else "❌"
    
    keyboard = [
        [InlineKeyboardButton(
            f"{morning_status} Утренний check-in",
            callback_data="ritual:toggle:morning"
        )],
        [InlineKeyboardButton(
            f"{evening_status} Вечерний check-in",
            callback_data="ritual:toggle:evening"
        )],
        [InlineKeyboardButton(
            f"{gratitude_status} Благодарность дня",
            callback_data="ritual:toggle:gratitude"
        )],
        [InlineKeyboardButton(
            f"{letter_status} Письмо себе (раз в неделю)",
            callback_data="ritual:toggle:letter"
        )],
        [InlineKeyboardButton(
            "⏰ Настроить время",
            callback_data="ritual:set_time"
        )],
    ]
    
    morning_time = user.preferred_time_morning or settings.RITUAL_MORNING_DEFAULT
    evening_time = user.preferred_time_evening or settings.RITUAL_EVENING_DEFAULT
    
    text = f"""🌅 Ритуалы

Ритуалы — это маленькие практики, которые помогают замечать своё состояние и заботиться о себе.

Текущее время:
• Утренний: {morning_time}
• Вечерний: {evening_time}

Выбери, какие ритуалы хочешь включить:"""

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /privacy."""

    privacy_url = "https://tools.uspeshnyy.ru/mirabot/privacy.html"

    keyboard = [
        [InlineKeyboardButton(
            "🔐 Открыть",
            web_app=WebAppInfo(url=privacy_url)
        )],
    ]

    text = """🔐 Конфиденциальность и безопасность

Твоя безопасность — мой приоритет.
Все наши переписки защищены шифрованием.

Нажми кнопку, чтобы узнать подробнее:"""

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
