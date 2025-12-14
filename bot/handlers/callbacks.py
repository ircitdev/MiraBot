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

    elif data.startswith("hint:"):
        await _handle_hint_selection(query, data, context)

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

        # Маппинг ritual → scheduled_message type
        ritual_type_map = {
            "morning": "morning_checkin",
            "evening": "evening_checkin",
            "gratitude": "ritual_gratitude",
            "letter": "ritual_letter",
        }

        if ritual in rituals:
            rituals.remove(ritual)
            status = "отключён"

            # Отменяем запланированные сообщения этого типа
            from services.scheduler import cancel_user_ritual
            if ritual in ritual_type_map:
                await cancel_user_ritual(user.id, ritual_type_map[ritual])
        else:
            rituals.append(ritual)
            status = "включён"

            # Планируем ритуал
            from services.scheduler import schedule_user_rituals
            await schedule_user_rituals(user.id)

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


async def _handle_hint_selection(query, data: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка нажатия на кнопку подсказки.
    Отправляет сохранённое сообщение как от пользователя.
    """
    try:
        # Парсим индекс подсказки
        hint_index = int(data.split(":")[1])

        # Получаем сохранённые подсказки из контекста
        hints = context.user_data.get("current_hints", [])

        if not hints or hint_index >= len(hints):
            await query.answer("Подсказка устарела, напиши сообщение сам 💛")
            return

        hint = hints[hint_index]
        message_text = hint.get("message", "")

        if not message_text:
            await query.answer("Ошибка подсказки")
            return

        # Удаляем сообщение с кнопками
        try:
            await query.message.delete()
        except Exception:
            pass

        # Очищаем текущие подсказки
        context.user_data["current_hints"] = []

        # Отправляем текст подсказки от имени пользователя
        # Создаём "фейковое" сообщение и обрабатываем его через message handler
        from bot.handlers.message import handle_message
        from telegram import Message as TelegramMessage

        # Для простоты — просто отправляем текст как новое сообщение от бота,
        # показывая что выбрал пользователь, и потом обрабатываем
        await query.message.chat.send_message(
            f"💬 _{message_text}_",
            parse_mode="Markdown",
        )

        # Создаём симуляцию Update с текстом подсказки
        # Это хак — лучше было бы использовать send_and_process, но так проще
        from telegram import Update as TelegramUpdate

        # Используем обычную отправку сообщения, которое пользователь мог бы написать сам
        # Но для полноценной обработки — симулируем ввод

        # Альтернативный подход: просто сохраняем текст и ждём следующего сообщения
        # Но лучше — отправить текст в обработчик напрямую

        # Получаем пользователя
        user = await user_repo.get_by_telegram_id(query.from_user.id)
        if not user:
            return

        # Импортируем необходимое
        from ai.claude_client import ClaudeClient
        from database.repositories.conversation import ConversationRepository
        from ai.hint_generator import hint_generator
        from bot.keyboards.inline import get_hints_keyboard

        claude = ClaudeClient()
        conversation_repo = ConversationRepository()

        # Проверяем лимиты
        subscription = await subscription_repo.get_active(user.id)
        is_premium = subscription and subscription.plan == "premium"

        if not is_premium:
            if subscription and subscription.messages_today >= 5:  # settings.FREE_MESSAGES_PER_DAY
                await query.message.chat.send_message(
                    "На сегодня лимит сообщений исчерпан... "
                    "Но я здесь, и завтра мы продолжим 💛"
                )
                return
            if subscription:
                await subscription_repo.increment_messages(subscription.id)

        # Подготавливаем данные
        user_data = {
            "persona": user.persona,
            "display_name": user.display_name,
            "partner_name": user.partner_name,
            "children_info": user.children_info,
            "marriage_years": user.marriage_years,
            "partner_gender": getattr(user, "partner_gender", None),
        }

        # Отправляем "печатает..."
        await query.message.chat.send_action("typing")

        # Генерируем ответ
        result = await claude.generate_response(
            user_id=user.id,
            user_message=message_text,
            user_data=user_data,
            is_premium=is_premium,
        )

        # Отправляем ответ
        await query.message.chat.send_message(result["response"])

        # Сохраняем сообщения
        await conversation_repo.save_message(
            user_id=user.id,
            role="user",
            content=message_text,
            tags=["hint"],  # Помечаем что это из подсказки
        )

        await conversation_repo.save_message(
            user_id=user.id,
            role="assistant",
            content=result["response"],
            tags=result["tags"],
            tokens_used=result["tokens_used"],
        )

        # Генерируем новые подсказки
        message_count = await conversation_repo.count_by_user(user.id)
        hints = hint_generator.generate(
            response_text=result["response"],
            tags=result["tags"],
            message_count=message_count,
        )

        if hints:
            context.user_data["current_hints"] = [
                {"text": h.text, "message": h.message}
                for h in hints
            ]
            keyboard = get_hints_keyboard(hints)
            await query.message.chat.send_message("💬", reply_markup=keyboard)

        logger.info(f"Hint processed for user {query.from_user.id}: '{hint.get('text')}'")

    except Exception as e:
        logger.error(f"Error handling hint: {e}")
        await query.answer("Произошла ошибка, попробуй написать сообщение сам 💛")
