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

    elif data == "privacy":
        await _show_privacy_info(query)

    elif data == "help":
        await _show_help_info(query)

    elif data.startswith("choice:"):
        await _handle_choice_callback(query, data, context)

    elif data.startswith("music_like:"):
        await _handle_music_feedback(query, data, "like", context)

    elif data.startswith("music_dislike:"):
        await _handle_music_feedback(query, data, "dislike", context)

    elif data.startswith("music_another:"):
        await _handle_music_another(query, data, context)

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
        from bot.handlers.message import _get_fresh_user_data
        user_data = await _get_fresh_user_data(user)

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
            user_message=message_text,  # ВАЖНО: передаём текст для контекстной проверки
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


async def _show_privacy_info(query) -> None:
    """Показывает информацию о конфиденциальности."""
    from telegram import WebAppInfo

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

    await query.answer()
    await query.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _show_help_info(query) -> None:
    """Показывает справку о боте."""

    text = """**Что я умею** 💛

Я — твой друг. Не психолог, не терапевт — просто тот, кто выслушает и поддержит.

**О чём можно говорить:**
• Отношения в браке
• Материнство и дети
• Самореализация
• Усталость и выгорание
• Всё, что на душе

**Команды:**
/exercises — упражнения (дыхание, релаксация, заземление)
/affirmation — аффирмация дня
/meditation — медитации (тексты для практики)
/settings — настройки бота
/subscription — твоя подписка
/referral — пригласи подругу
/rituals — настрой ритуалы
/privacy — соглашение о неразглашении

**Голосовые сообщения:**
Можешь говорить — я пойму! Отправь голосовое сообщение, я его расшифрую и отвечу 🎤

**Фото:**
Можешь отправить мне фото — я посмотрю и мы обсудим 📸

**Важно:**
Если тебе очень тяжело — я рядом. Но в серьёзных ситуациях я направлю тебя к людям, которые могут помочь профессионально. Это не слабость — это забота о себе.

Телефон доверия: 8-800-2000-122 (бесплатно, круглосуточно)

Просто напиши или скажи — я слушаю 💛"""

    await query.answer()
    await query.message.reply_text(text, parse_mode="Markdown")


async def _handle_choice_callback(query, data: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка выбора из inline-кнопок (choice:...).
    Когда пользователь нажимает кнопку, это как если бы он написал текст кнопки.
    """
    # Извлекаем текст выбора
    choice_text = data.replace("choice:", "", 1)

    # Убираем кнопки из сообщения
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Проверяем, не является ли это выбором музыкального жанра
    music_genres = {
        "🎹 классика": "classical",
        "классика": "classical",
        "🌊 ambient": "ambient",
        "ambient": "ambient",
        "🌧 звуки природы": "nature",
        "звуки природы": "nature",
        "🎷 джаз": "jazz",
        "джаз": "jazz",
    }

    choice_lower = choice_text.lower().strip()
    if choice_lower in music_genres:
        genre = music_genres[choice_lower]

        # Импортируем функцию отправки музыки по жанру
        from bot.handlers.music import send_music_by_genre
        from services.music_recommendation import music_recommendation

        # Отправляем выбор
        await query.message.chat.send_message(
            f"💬 _{choice_text}_",
            parse_mode="Markdown",
        )

        # Отправляем музыку по жанру
        result = await music_recommendation.recommend_music_by_genre(genre)

        if result["success"]:
            import urllib.parse

            track_name = result['track']
            message_text = f"{result['message']}\n\n🎵 **{track_name}**"

            # Создаём deep link для скачивания через UspMusicFinder
            # Формат: https://t.me/UspMusicFinder_bot?start=ENCODED_TRACK_NAME
            track_for_search = track_name.replace(" - ", " ")  # "Artist - Track" -> "Artist Track"
            encoded_track = urllib.parse.quote(track_for_search)
            download_link = f"https://t.me/UspMusicFinder_bot?start={encoded_track}"

            # Кнопки: YouTube + Скачать в Telegram + Feedback
            keyboard = [
                [InlineKeyboardButton("▶️ Слушать на YouTube", url=result['url'])],
                [InlineKeyboardButton("📥 Скачать в Telegram", url=download_link)],
                [
                    InlineKeyboardButton("👍", callback_data=f"music_like:{track_name[:40]}"),
                    InlineKeyboardButton("👎", callback_data=f"music_dislike:{track_name[:40]}"),
                    InlineKeyboardButton("🔄", callback_data=f"music_another:{genre}"),
                ],
            ]

            await query.message.chat.send_message(
                message_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True,
            )
            logger.info(f"Sent music by genre '{genre}' to user {query.from_user.id}")
        else:
            await query.message.chat.send_message(
                "Хм, что-то не нашла музыку этого жанра. Давай попробуем что-то другое?"
            )
        return

    # Отправляем выбор как "сообщение пользователя" и обрабатываем
    await query.message.chat.send_message(
        f"💬 _{choice_text}_",
        parse_mode="Markdown",
    )

    # Симулируем обработку как обычное сообщение
    user = await user_repo.get_by_telegram_id(query.from_user.id)
    if not user:
        return

    # Импортируем и вызываем обработку сообщения
    from ai.claude_client import ClaudeClient
    from database.repositories.subscription import SubscriptionRepository
    from database.repositories.conversation import ConversationRepository

    claude = ClaudeClient()
    conversation_repo = ConversationRepository()

    # Получаем данные пользователя
    user_data = {
        "persona": user.persona,
        "display_name": user.display_name,
        "partner_name": user.partner_name,
        "children_info": user.children_info,
        "marriage_years": user.marriage_years,
    }

    # Проверяем подписку
    subscription = await subscription_repo.get_active(user.id)
    is_premium = subscription and subscription.plan in ("premium", "trial")

    # Отправляем typing
    await query.message.chat.send_action("typing")

    try:
        # Генерируем ответ Claude
        result = await claude.generate_response(
            user_id=user.id,
            user_message=choice_text,
            user_data=user_data,
            is_premium=is_premium,
        )

        response_text = result.get("response", "Хм, что-то пошло не так...")

        # Парсим кнопки из ответа
        from bot.handlers.message import parse_inline_buttons
        clean_text, buttons = parse_inline_buttons(response_text)
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

        # Отправляем ответ
        try:
            await query.message.chat.send_message(
                clean_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
        except Exception:
            # Без Markdown если ошибка
            await query.message.chat.send_message(
                clean_text,
                reply_markup=reply_markup,
            )

        # Сохраняем в историю
        await conversation_repo.save_message(
            user_id=user.id,
            role="user",
            content=choice_text,
            tags=["button_choice"],
        )
        await conversation_repo.save_message(
            user_id=user.id,
            role="assistant",
            content=clean_text,
        )

    except Exception as e:
        logger.error(f"Error handling choice callback: {e}")
        await query.message.chat.send_message(
            "Прости, что-то пошло не так. Попробуй ещё раз 💛"
        )


async def _handle_music_feedback(query, data: str, feedback_type: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка обратной связи по музыке (👍 или 👎).
    Отправляет сообщение как от пользователя и обрабатывает через Claude.
    """
    # Извлекаем название трека из callback data
    if feedback_type == "like":
        track_name = data.replace("music_like:", "", 1)
        user_message = f"Мне понравилось 🎵 {track_name}"
    else:  # dislike
        track_name = data.replace("music_dislike:", "", 1)
        user_message = f"🎵 {track_name} не зашло"

    # Убираем кнопки из сообщения
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Отправляем "сообщение пользователя"
    await query.message.chat.send_message(
        f"💬 _{user_message}_",
        parse_mode="Markdown",
    )

    # Обрабатываем через Claude
    user = await user_repo.get_by_telegram_id(query.from_user.id)
    if not user:
        return

    from ai.claude_client import ClaudeClient
    from database.repositories.conversation import ConversationRepository

    claude = ClaudeClient()
    conversation_repo = ConversationRepository()

    user_data = {
        "persona": user.persona,
        "display_name": user.display_name,
        "partner_name": user.partner_name,
        "children_info": user.children_info,
        "marriage_years": user.marriage_years,
    }

    subscription = await subscription_repo.get_active(user.id)
    is_premium = subscription and subscription.plan in ("premium", "trial")

    await query.message.chat.send_action("typing")

    try:
        result = await claude.generate_response(
            user_id=user.id,
            user_message=user_message,
            user_data=user_data,
            is_premium=is_premium,
        )

        response_text = result.get("response", "Спасибо за отзыв! 💛")

        # Парсим кнопки из ответа
        from bot.handlers.message import parse_inline_buttons
        clean_text, buttons = parse_inline_buttons(response_text)
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

        try:
            await query.message.chat.send_message(
                clean_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
        except Exception:
            await query.message.chat.send_message(clean_text, reply_markup=reply_markup)

        # Сохраняем в историю
        await conversation_repo.save_message(
            user_id=user.id,
            role="user",
            content=user_message,
            tags=["music_feedback", feedback_type],
        )
        await conversation_repo.save_message(
            user_id=user.id,
            role="assistant",
            content=clean_text,
        )

    except Exception as e:
        logger.error(f"Error handling music feedback: {e}")
        if feedback_type == "like":
            await query.message.chat.send_message("Рада, что понравилось! 🎵💛")
        else:
            await query.message.chat.send_message("Поняла! Попробуем что-то другое в следующий раз 💛")


async def _handle_music_another(query, data: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка кнопки 🔄 — отправляет другой трек того же жанра.
    """
    genre = data.replace("music_another:", "", 1)

    # Убираем кнопки из старого сообщения
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Отправляем "сообщение пользователя"
    await query.message.chat.send_message(
        f"💬 _Пришли другое_",
        parse_mode="Markdown",
    )

    # Получаем новый трек того же жанра
    from services.music_recommendation import music_recommendation
    import urllib.parse

    result = await music_recommendation.recommend_music_by_genre(genre)

    if result["success"]:
        track_name = result['track']
        message_text = f"{result['message']}\n\n🎵 **{track_name}**"

        track_for_search = track_name.replace(" - ", " ")
        encoded_track = urllib.parse.quote(track_for_search)
        download_link = f"https://t.me/UspMusicFinder_bot?start={encoded_track}"

        keyboard = [
            [InlineKeyboardButton("▶️ Слушать на YouTube", url=result['url'])],
            [InlineKeyboardButton("📥 Скачать в Telegram", url=download_link)],
            [
                InlineKeyboardButton("👍", callback_data=f"music_like:{track_name[:40]}"),
                InlineKeyboardButton("👎", callback_data=f"music_dislike:{track_name[:40]}"),
                InlineKeyboardButton("🔄", callback_data=f"music_another:{genre}"),
            ],
        ]

        await query.message.chat.send_message(
            message_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True,
        )
        logger.info(f"Sent another music by genre '{genre}' to user {query.from_user.id}")
    else:
        await query.message.chat.send_message(
            "Хм, больше треков этого жанра не нашла... Попробуй выбрать другой жанр 💛"
        )
