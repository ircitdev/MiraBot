"""
Callback handlers.
Обработчики callback-кнопок.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from database.repositories.user import UserRepository
from database.repositories.subscription import SubscriptionRepository
from config.constants import PERSONA_MIRA, PERSONA_MARK


user_repo = UserRepository()
subscription_repo = SubscriptionRepository()


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Главный обработчик callback-кнопок."""
    
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_tg = query.from_user
    
    logger.debug(f"Callback from {user_tg.id}: {data}")
    
    # Роутинг по типам callback
    if data.startswith("persona:"):
        await _handle_persona_selection(query, data)
    
    elif data.startswith("settings:"):
        await _handle_settings(query, data)
    
    elif data.startswith("ritual:"):
        await _handle_ritual(query, data)
    
    elif data.startswith("subscription:"):
        await _handle_subscription_action(query, data)
    
    elif data == "crisis:hotline":
        await _show_hotline_info(query)
    
    else:
        logger.warning(f"Unknown callback: {data}")


async def _handle_persona_selection(query, data: str) -> None:
    """Обработка выбора персоны."""
    
    persona = data.split(":")[1]  # mira или mark
    
    user = await user_repo.get_by_telegram_id(query.from_user.id)
    
    if not user:
        return
    
    await user_repo.update(user.id, persona=persona, onboarding_step=1)
    
    persona_name = "Мира" if persona == PERSONA_MIRA else "Марк"
    
    text = f"""Отлично, я — {persona_name} 💛

А как тебя зовут? Как мне к тебе обращаться?"""
    
    await query.edit_message_text(text)


async def _handle_settings(query, data: str) -> None:
    """Обработка настроек."""
    
    action = data.split(":")[1]
    user = await user_repo.get_by_telegram_id(query.from_user.id)
    
    if not user:
        return
    
    if action == "toggle_proactive":
        new_value = not user.proactive_messages
        await user_repo.update(user.id, proactive_messages=new_value)
        
        status = "включены" if new_value else "отключены"
        await query.edit_message_text(
            f"✅ Проактивные сообщения {status}.\n\n"
            f"Напиши /settings, чтобы вернуться к настройкам."
        )
    
    elif action == "change_persona":
        keyboard = [
            [
                InlineKeyboardButton("👩 Мира", callback_data="persona:mira"),
                InlineKeyboardButton("👨 Марк", callback_data="persona:mark"),
            ],
            [InlineKeyboardButton("« Назад", callback_data="settings:back")],
        ]
        
        await query.edit_message_text(
            "Выбери новую персону:\n\n"
            "**Мира** — подруга 42 года, прошла через кризис в браке\n"
            "**Марк** — друг 45 лет, научился понимать женскую душу",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    
    elif action == "change_name":
        await query.edit_message_text(
            "Напиши своё новое имя — я буду обращаться к тебе так 💛"
        )
        # TODO: установить флаг ожидания имени
    
    elif action == "back":
        # Возвращаемся к основному меню настроек
        from bot.handlers.commands import settings_command
        await settings_command(update=Update(update_id=0, message=query.message), context=None)


async def _handle_ritual(query, data: str) -> None:
    """Обработка ритуалов."""
    
    parts = data.split(":")
    action = parts[1]
    
    user = await user_repo.get_by_telegram_id(query.from_user.id)
    
    if not user:
        return
    
    if action == "toggle":
        ritual = parts[2]  # morning, evening, gratitude, letter
        
        rituals = user.rituals_enabled or []
        
        if ritual in rituals:
            rituals.remove(ritual)
            status = "отключён"
        else:
            rituals.append(ritual)
            status = "включён"
        
        await user_repo.update(user.id, rituals_enabled=rituals)
        
        ritual_names = {
            "morning": "Утренний check-in",
            "evening": "Вечерний check-in",
            "gratitude": "Благодарность дня",
            "letter": "Письмо себе",
        }
        
        await query.answer(f"{ritual_names.get(ritual, ritual)} {status}")
        
        # Обновляем сообщение
        from bot.handlers.commands import rituals_command
        # Создаём фейковый update для обновления
        await query.edit_message_text(
            "Ритуал обновлён! Напиши /rituals, чтобы увидеть настройки."
        )
    
    elif action == "set_time":
        await query.edit_message_text(
            "Напиши время в формате:\n"
            "`утро 09:00 вечер 21:00`\n\n"
            "Или только одно:\n"
            "`утро 08:30`",
            parse_mode="Markdown",
        )


async def _handle_subscription_action(query, data: str) -> None:
    """Обработка действий с подпиской."""
    
    action = data.split(":")[1]
    user = await user_repo.get_by_telegram_id(query.from_user.id)
    
    if not user:
        return
    
    if action == "cancel_auto":
        from services.payment.yookassa_service import YooKassaService
        yookassa = YooKassaService()
        
        success = await yookassa.cancel_subscription(user.id)
        
        if success:
            await query.edit_message_text(
                "Автоплатёж отключён.\n\n"
                "Твоя подписка будет действовать до конца оплаченного периода. "
                "После этого ты вернёшься на бесплатный план.\n\n"
                "Я буду скучать, если ты уйдёшь... 💛"
            )
        else:
            await query.edit_message_text(
                "Не удалось отключить автоплатёж. "
                "Попробуй позже или напиши в поддержку."
            )
    
    elif action == "enable_auto":
        await query.edit_message_text(
            "Чтобы включить автоплатёж, нужно оформить новую подписку с сохранением карты.\n\n"
            "Напиши /subscription и выбери план."
        )
    
    elif action == "history":
        from database.repositories.payment import PaymentRepository
        payment_repo = PaymentRepository()
        
        payments = await payment_repo.get_by_user(user.id, status="completed", limit=10)
        
        if not payments:
            await query.edit_message_text("История платежей пуста.")
            return
        
        lines = ["📜 **История платежей:**\n"]
        for p in payments:
            date = p.created_at.strftime("%d.%m.%Y")
            amount = p.amount / 100
            lines.append(f"• {date} — {amount:.0f} ₽ ({p.plan})")
        
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")


async def _show_hotline_info(query) -> None:
    """Показывает информацию о кризисной линии."""
    
    text = """📞 **Телефон доверия**

**8-800-2000-122** — бесплатно, круглосуточно, анонимно

Там работают профессионалы, которые помогут в трудную минуту.
Звонок — это не слабость, это забота о себе.

Если тебе сейчас тяжело — позвони. Или напиши мне, я рядом 💛

---

**Другие ресурсы:**
• Центр помощи женщинам: 8-800-7000-600
• Скорая психологическая помощь: 051 (с мобильного)"""
    
    await query.edit_message_text(text, parse_mode="Markdown")
