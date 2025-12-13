"""
Payment handlers.
Обработчики платежей и подписок.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from database.repositories.user import UserRepository
from services.payment.yookassa_service import YooKassaService
from config.settings import settings


user_repo = UserRepository()
yookassa = YooKassaService()


async def handle_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка выбора подписки."""
    
    query = update.callback_query
    await query.answer()
    
    data = query.data
    action = data.split(":")[1]
    
    if action == "show":
        await _show_subscription_options(query)
    
    elif action in ["monthly", "quarterly", "yearly"]:
        await _ask_auto_renew(query, action)
    
    elif action == "back":
        await _show_subscription_options(query)
    
    elif action == "cancel":
        await query.edit_message_text(
            "Оплата отменена. Если передумаешь — напиши /subscription 💛"
        )


async def handle_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка создания платежа."""
    
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split(":")
    plan = parts[1]
    auto_renew = parts[2] == "auto"
    
    user = await user_repo.get_by_telegram_id(query.from_user.id)
    
    if not user:
        await query.edit_message_text("Ошибка. Попробуй /start")
        return
    
    try:
        # Создаём платёж
        result = await yookassa.create_payment(
            user_id=user.id,
            plan=plan,
            save_payment_method=auto_renew,
        )
        
        keyboard = [
            [InlineKeyboardButton("💳 Перейти к оплате", url=result["confirmation_url"])],
            [InlineKeyboardButton("« Отмена", callback_data="subscribe:cancel")],
        ]
        
        text = """Отлично! Нажми кнопку ниже, чтобы перейти к оплате.

После успешной оплаты я сразу активирую твою подписку 💛

_Оплата безопасна и защищена ЮKassa_"""
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        
        logger.info(f"Payment created for user {user.id}, plan={plan}, yookassa_id={result['yookassa_id']}")
        
    except Exception as e:
        logger.error(f"Error creating payment for user {user.id}: {e}")
        await query.edit_message_text(
            "Не удалось создать платёж. Попробуй позже или напиши в поддержку."
        )


async def _show_subscription_options(query) -> None:
    """Показывает варианты подписки."""
    
    keyboard = [
        [InlineKeyboardButton(
            f"💎 1 месяц — {settings.PRICE_MONTHLY} ₽",
            callback_data="subscribe:monthly"
        )],
        [InlineKeyboardButton(
            f"💎 3 месяца — {settings.PRICE_QUARTERLY} ₽ (экономия 15%)",
            callback_data="subscribe:quarterly"
        )],
        [InlineKeyboardButton(
            f"💎 1 год — {settings.PRICE_YEARLY} ₽ (экономия 30%)",
            callback_data="subscribe:yearly"
        )],
    ]
    
    text = """✨ **Premium подписка**

Что ты получишь:
• Безлимитное общение — никаких ограничений
• Полная память — я помню всё о наших разговорах
• Все ритуалы — утренние и вечерние check-in
• Еженедельные рефлексии и письма о прогрессе
• Приоритетные ответы

Выбери удобный вариант:"""
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def _ask_auto_renew(query, plan: str) -> None:
    """Спрашивает про автоплатёж."""
    
    plan_names = {
        "monthly": f"1 месяц — {settings.PRICE_MONTHLY} ₽",
        "quarterly": f"3 месяца — {settings.PRICE_QUARTERLY} ₽",
        "yearly": f"1 год — {settings.PRICE_YEARLY} ₽",
    }
    
    keyboard = [
        [InlineKeyboardButton(
            "✅ Да, подключить автоплатёж",
            callback_data=f"pay:{plan}:auto"
        )],
        [InlineKeyboardButton(
            "❌ Нет, разовый платёж",
            callback_data=f"pay:{plan}:once"
        )],
        [InlineKeyboardButton("« Назад", callback_data="subscribe:back")],
    ]
    
    text = f"""Ты выбрала: **{plan_names[plan]}**

Подключить автоматическое продление?

Так тебе не придётся каждый раз оплачивать вручную, а я продолжу быть рядом без перерывов 💛

_Ты сможешь отключить автоплатёж в любой момент_"""
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


def get_plan_name(plan: str) -> str:
    """Возвращает название плана."""
    names = {
        "monthly": f"1 месяц — {settings.PRICE_MONTHLY} ₽",
        "quarterly": f"3 месяца — {settings.PRICE_QUARTERLY} ₽",
        "yearly": f"1 год — {settings.PRICE_YEARLY} ₽",
    }
    return names.get(plan, plan)
