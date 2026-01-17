"""
Onboarding handler with ConversationHandler.
Новый процесс онбординга с диалоговой логикой.
"""

import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger

from database.repositories.user import UserRepository
from database.repositories.onboarding_event import OnboardingEventRepository
from config.constants import PERSONA_MIRA
from bot.utils.typing import send_with_typing, send_typing_only
from ai.crisis_detector import CrisisDetector
from ai.crisis_protocol import requires_emergency_message, get_emergency_message, detect_crisis_type


user_repo = UserRepository()
onboarding_event_repo = OnboardingEventRepository()
crisis_detector = CrisisDetector()

# Состояния диалога (экспортируются для main.py)
WAITING_NAME = 0
CONFIRMING_NAME = 1
SELECTING_PROBLEM = 2
SOCIAL_PORTRAIT = 3
FAMILY_STATUS = 4
FAMILY_DETAILS = 5

__all__ = [
    'start_onboarding',
    'receive_name',
    'handle_name_confirmation',
    'handle_problem_selection',
    'receive_social_portrait',
    'handle_family_status',
    'receive_family_details',
    'handle_skip_details',
    'cancel_onboarding',
    'WAITING_NAME',
    'CONFIRMING_NAME',
    'SELECTING_PROBLEM',
    'SOCIAL_PORTRAIT',
    'FAMILY_STATUS',
    'FAMILY_DETAILS',
]


def get_time_of_day_greeting() -> str:
    """
    Возвращает приветствие в зависимости от времени суток.

    Returns:
        Строка с приветствием (например: "Доброе утро! ☀️")
    """
    # Получаем московское время (UTC+3)
    # Telegram пользователи бота в основном из России
    moscow_hour = (datetime.utcnow().hour + 3) % 24

    if 5 <= moscow_hour < 12:
        # Утро (5:00 - 11:59)
        return "Доброе утро! ☀️"
    elif 12 <= moscow_hour < 18:
        # День (12:00 - 17:59)
        return "Добрый день! 🌤"
    elif 18 <= moscow_hour < 23:
        # Вечер (18:00 - 22:59)
        return "Добрый вечер! 🌙"
    else:
        # Ночь (23:00 - 4:59)
        return "Привет! 🌜 Ты не спишь?"


def get_progress_message(step: int, total: int = 4) -> str:
    """
    Генерирует сообщение с прогресс-баром для онбординга.

    Args:
        step: Текущий шаг (1-4)
        total: Общее количество шагов

    Returns:
        Строка с прогрессом, например: "Знакомство: 50% 🌟🌟"
    """
    percentage = int((step / total) * 100)

    # Звёздочки для визуализации
    filled_stars = '🌟' * step
    empty_stars = '⭐' * (total - step)

    if step == total:
        # Финальное сообщение
        return f"✨ Знакомство завершено: {percentage}% ✨"
    else:
        return f"Знакомство: {percentage}% {filled_stars}{empty_stars}"


async def check_crisis_in_message(update: Update, message_text: str) -> bool:
    """
    Проверяет сообщение на кризисные маркеры и отправляет экстренное сообщение если нужно.

    Returns:
        True если обнаружен кризис уровня high/critical (нужно прервать онбординг)
        False если кризиса нет или уровень low/medium (можно продолжить)
    """
    crisis_result = crisis_detector.check(message_text)

    if crisis_result["is_crisis"]:
        crisis_level = crisis_result["level"]
        logger.warning(
            f"Crisis detected during onboarding: level={crisis_level}, "
            f"keywords={crisis_result['matched_keywords']}"
        )

        # Если критический уровень - отправляем экстренное сообщение
        if requires_emergency_message(crisis_level):
            crisis_type = detect_crisis_type(crisis_result["matched_keywords"])
            emergency_msg = get_emergency_message(crisis_level, crisis_type)

            if emergency_msg:
                await update.message.reply_text(
                    emergency_msg,
                    parse_mode='Markdown'
                )

            # Возвращаем True - нужно прервать онбординг и перейти к кризисному диалогу
            return True

    return False


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начало онбординга - приветствие и запрос имени.

    Согласно новому подходу: один экран — одна мысль — одно действие.
    """
    from database.repositories.user import UserRepository
    from telegram.ext import ConversationHandler

    user_repo = UserRepository()
    user_tg = update.effective_user

    # Получаем пользователя из БД
    user, created = await user_repo.get_or_create(
        telegram_id=user_tg.id,
        username=user_tg.username,
        first_name=user_tg.first_name,
    )

    # Если пользователь уже завершил онбординг - приветствуем и выходим
    if user.onboarding_completed:
        user_name = user.display_name or "дорогая"
        greeting = get_time_of_day_greeting()

        text = f"""{greeting}

Это Мира. Рада тебя видеть снова, {user_name} 💛

Как ты? Что на душе? Можешь написать или отправить голосовое 🎤"""

        await update.message.reply_text(text)
        return ConversationHandler.END

    # ВАЖНО: Проверяем не начал ли пользователь уже онбординг
    # Если у него есть display_name — значит он уже вводил имя
    # В этом случае НЕ начинаем заново, а напоминаем продолжить
    if user.display_name and not user.onboarding_completed:
        user_name = user.display_name
        greeting = get_time_of_day_greeting()

        text = f"""{greeting}

{user_name}, мы не закончили знакомство 💛

Продолжим с того места, где остановились?

Напиши что у тебя сейчас на душе, и я помогу."""

        await update.message.reply_text(text)
        return ConversationHandler.END

    # Логируем начало онбординга (только для новых пользователей)
    await onboarding_event_repo.log_event(
        user_id=user.id,
        event_name="onboarding_started",
        event_data={"telegram_id": user_tg.id, "username": user_tg.username}
    )

    # Первое сообщение с персонализацией по времени суток
    greeting = get_time_of_day_greeting()
    await send_with_typing(update, f"{greeting} Я Мира 💛", delay=1.0)

    # Второе сообщение с паузой
    await send_with_typing(
        update,
        "Я здесь, чтобы просто выслушать — без осуждения.",
        delay=1.5
    )

    # Третье сообщение - вопрос
    await send_with_typing(
        update,
        "Как я могу к тебе обращаться?",
        delay=1.0
    )

    # СТОП. Ждём ответа пользователя
    return WAITING_NAME


def extract_name_from_text(text: str) -> str:
    """
    Извлекает имя из ответа пользователя.

    Примеры:
    - "Ко мне можешь обращаться Вячеслав" -> "Вячеслав"
    - "Зови меня Маша" -> "Маша"
    - "Меня зовут Анна" -> "Анна"
    - "Александр" -> "Александр"
    """
    text = text.strip()

    # Паттерны для извлечения имени (сортированы от более специфичных к менее)
    patterns = [
        ("друзья зовут меня", 0),  # "Друзья зовут меня Люсей"
        ("друзья зовут", 0),  # "Друзья зовут Люсей"
        ("меня зовут", 0),  # "Меня зовут Анна"
        ("можешь обращаться", 0),  # "Можешь обращаться Вячеслав"
        ("можешь звать меня", 0),  # "Можешь звать меня Катя"
        ("можешь звать", 0),  # "Можешь звать Катя"
        ("зови меня", 0),   # "Зови меня Маша"
        ("называй меня", 0),  # "Называй меня Света"
        ("зовут", 0),  # "Зовут Анна"
        ("зови", 0),   # "Зови Маша"
        ("обращаться", 0),  # "Обращаться Петр"
        ("называй", 0),  # "Называй Света"
    ]

    text_lower = text.lower()

    # Пробуем найти имя после ключевых фраз
    for pattern, skip_words in patterns:
        if pattern in text_lower:
            # Находим позицию паттерна
            idx = text_lower.find(pattern)
            # Берём текст после паттерна
            after_pattern = text[idx + len(pattern):].strip()
            # Убираем "меня", "мне" и т.д.
            words = after_pattern.split()
            if len(words) > 0:
                # Берём первое слово (имя)
                # Очищаем от знаков препинания
                name = words[0].strip('.,!?;:')
                if len(name) > 0:
                    return name

    # Если паттернов нет, берём первые 1-2 слова
    words = text.split()
    if len(words) <= 2:
        return text
    else:
        # Если слов больше 2, берём первые 2
        return ' '.join(words[:2])


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Получение имени пользователя.

    После получения имени переходим к подтверждению.
    """
    raw_text = update.message.text.strip()

    # Проверка на кризис
    is_crisis = await check_crisis_in_message(update, raw_text)
    if is_crisis:
        # Прерываем онбординг, завершаем ConversationHandler
        return ConversationHandler.END

    # Извлекаем имя из ответа
    name = extract_name_from_text(raw_text)

    # Валидация: имя не должно быть слишком длинным
    if len(name) > 50:
        await send_with_typing(
            update,
            "Кажется, это слишком длинное имя 😅\n\n"
            "Просто напиши, как тебя зовут — одним-двумя словами.",
            delay=1.0
        )
        return WAITING_NAME

    # Сохраняем имя в контексте
    context.user_data['name'] = name

    # Логируем ввод имени
    user_tg = update.effective_user
    user, _ = await user_repo.get_or_create(
        telegram_id=user_tg.id,
        username=user_tg.username,
        first_name=user_tg.first_name,
    )
    await onboarding_event_repo.log_event(
        user_id=user.id,
        event_name="name_entered",
        event_data={"name": name, "raw_input": raw_text}
    )

    # Показываем что печатаем
    await send_typing_only(update, delay=1.0)

    # Уточняем имя с кнопками подтверждения
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, всё верно", callback_data="confirm_name:yes"),
            InlineKeyboardButton("✏️ Исправить", callback_data="confirm_name:no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Правильно ли я поняла — тебя зовут {name}?",
        reply_markup=reply_markup
    )

    return CONFIRMING_NAME


async def handle_name_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка подтверждения или исправления имени.
    """
    query = update.callback_query
    await query.answer()

    action = query.data.split(':')[1]  # "yes" или "no"
    name = context.user_data.get('name', '')

    if action == 'no':
        # Пользователь хочет исправить имя
        await send_with_typing(
            query,
            "Хорошо, давай попробуем ещё раз.\n\n"
            "Просто напиши своё имя — так, как тебе удобно, чтобы я к тебе обращалась.",
            delay=1.0
        )
        return WAITING_NAME

    # action == "yes" - имя подтверждено
    try:
        # Удаляем кнопки
        await query.edit_message_reply_markup(reply_markup=None)

        # Логируем подтверждение имени
        user_tg = update.effective_user
        user, _ = await user_repo.get_or_create(
            telegram_id=user_tg.id,
            username=user_tg.username,
            first_name=user_tg.first_name,
        )
        await onboarding_event_repo.log_event(
            user_id=user.id,
            event_name="name_confirmed",
            event_data={"name": name}
        )

        logger.info(f"User {user.id} confirmed name: {name}")

        # Показываем что печатаем
        await send_typing_only(query, delay=1.0)

        logger.info(f"Sending welcome message to {user.id}")
        # Приветствие по имени
        await query.message.reply_text(f"Очень приятно, {name}! 🌷")

        # Показываем прогресс (Шаг 1 из 4)
        await asyncio.sleep(0.5)
        progress_msg = get_progress_message(step=1, total=4)
        await query.message.reply_text(progress_msg)

        # Пауза
        await send_typing_only(query, delay=1.5)

        # Информация о конфиденциальности
        await query.message.reply_text(
            "Чтобы тебе было спокойно: наш чат **полностью зашифрован** 🔒",
            parse_mode='Markdown'
        )

        # Пауза
        await send_typing_only(query, delay=1.5)

        # Немного о Мире
        await query.message.reply_text(
            "Немного обо мне: мне 42, я мама двоих детей и 18 лет в браке. "
            "Сама прошла через выгорание, поэтому понимаю, как бывает непросто."
        )

        # Пауза перед главным вопросом
        await send_typing_only(query, delay=2.0)

        # Предлагаем выбрать "боль" вместо категорий
        keyboard = [
            [InlineKeyboardButton("Чувствую себя выжатой, как лимон", callback_data='pain_burnout')],
            [InlineKeyboardButton("Всё раздражает, особенно близкие", callback_data='pain_irritation')],
            [InlineKeyboardButton("Внутри тревога и пустота", callback_data='pain_anxiety')],
            [InlineKeyboardButton("Стыдно — срываюсь на детей", callback_data='pain_guilt')],
            [InlineKeyboardButton("Просто нужно выговориться", callback_data='pain_talk')],
            [InlineKeyboardButton("Другое (напишу сама)", callback_data='pain_other')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            "С чем ты сейчас? Выбери, что ближе всего:",
            reply_markup=reply_markup
        )

        logger.info(f"Problem selection menu sent to {user.id}")
        return SELECTING_PROBLEM

    except Exception as e:
        logger.error(f"Error in handle_name_confirmation: {e}", exc_info=True)
        await query.message.reply_text(
            "Произошла ошибка. Попробуйте начать заново с команды /start"
        )
        return ConversationHandler.END


async def handle_problem_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка выбора проблемы (кнопки-боли).
    """
    query = update.callback_query
    await query.answer()

    problem = query.data.replace('pain_', '')
    context.user_data['problem'] = problem

    user_tg = update.effective_user
    name = context.user_data.get('name', 'дорогая')

    # Сохраняем данные в БД
    user, _ = await user_repo.get_or_create(
        telegram_id=user_tg.id,
        username=user_tg.username,
        first_name=user_tg.first_name,
    )

    await user_repo.update(
        user.id,
        display_name=name,
        persona=PERSONA_MIRA,
        onboarding_step=2,
    )

    # Логируем выбор проблемы
    await onboarding_event_repo.log_event(
        user_id=user.id,
        event_name="problem_selected",
        event_data={"problem": problem}
    )

    # Эмпатичный отклик в зависимости от выбора
    responses = {
        'burnout': f"{name}, я вижу, как ты устала 💛",
        'irritation': f"{name}, это нормально — чувствовать раздражение.",
        'anxiety': f"{name}, тревога может быть невыносимой. Я рядом.",
        'guilt': f"{name}, материнская вина — это так тяжело.",
        'talk': f"{name}, я слушаю 💛",
        'other': f"{name}, расскажи, что тебя беспокоит.",
    }

    response = responses.get(problem, f"{name}, расскажи, что у тебя на душе.")

    # Показываем typing
    await asyncio.sleep(1.0)
    await query.message.reply_text(response)

    # Показываем прогресс (Шаг 2 из 4)
    await asyncio.sleep(0.5)
    progress_msg = get_progress_message(step=2, total=4)
    await query.message.reply_text(progress_msg)

    # Пауза перед касанием 2
    await asyncio.sleep(1.5)

    # Касание 2: Социальный портрет (свободный ответ для AI-парсинга)
    await query.message.reply_text(
        "Расскажи немного о себе: *сколько тебе лет, из какого города и чем занимаешься?*\n\n"
        "Можешь написать свободно — я пойму 🌷",
        parse_mode='Markdown'
    )

    logger.info(f"User {user_tg.id} selected problem: {problem}, moving to social portrait")

    # Переходим к касанию 2
    return SOCIAL_PORTRAIT


async def receive_social_portrait(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Касание 2: Получение социального портрета (возраст, город, работа, хобби).

    Использует AI-парсинг для извлечения структурированных данных.
    """
    from ai.profile_parser import parse_social_portrait
    from database.repositories.user_profile import UserProfileRepository

    user_input = update.message.text.strip()

    # Проверка на кризис
    is_crisis = await check_crisis_in_message(update, user_input)
    if is_crisis:
        return ConversationHandler.END

    context.user_data['social_info'] = user_input

    name = context.user_data.get('name', 'дорогая')
    user_tg = update.effective_user

    # Получаем пользователя для логирования
    user, _ = await user_repo.get_or_create(
        telegram_id=user_tg.id,
        username=user_tg.username,
        first_name=user_tg.first_name,
    )

    # Логируем ввод социального портрета
    await onboarding_event_repo.log_event(
        user_id=user.id,
        event_name="social_portrait_entered",
        event_data={"social_info": social_info}
    )

    # Показываем что печатаем (typing indicator)
    await send_typing_only(update, delay=1.5)

    # AI-парсинг данных профиля
    try:
        logger.info(f"Parsing social portrait for user {user_tg.id}: {social_info}")
        parsed_data = await parse_social_portrait(social_info)
        logger.info(f"Parsed data: {parsed_data}")

        # Сохраняем данные в user_profiles
        profile_repo = UserProfileRepository()
        profile = await profile_repo.get_or_create_profile(user.id)

        # Обновляем профиль
        await profile_repo.update_profile(
            user.id,
            age=parsed_data.get('age'),
            city=parsed_data.get('city'),
            occupation=parsed_data.get('job'),
            # Хобби можно сохранить в отдельное поле или в JSON
        )

        # Логируем успешный парсинг
        await onboarding_event_repo.log_event(
            user_id=user.id,
            event_name="social_portrait_parsed",
            event_data=parsed_data
        )

        logger.info(f"Profile updated for user {user_tg.id}")

    except Exception as e:
        logger.error(f"Error during profile parsing: {e}")
        # Продолжаем онбординг даже если парсинг не удался

    # Благодарим за открытость
    await update.message.reply_text(f"Спасибо, {name} 🌷")

    # Показываем прогресс (Шаг 3 из 4)
    await asyncio.sleep(0.5)
    progress_msg = get_progress_message(step=3, total=4)
    await update.message.reply_text(progress_msg)

    # Пауза
    await send_typing_only(update, delay=1.5)

    # Касание 3: Статус отношений (с кнопками)
    keyboard = [
        [InlineKeyboardButton("Замужем", callback_data='status_married')],
        [InlineKeyboardButton("В отношениях", callback_data='status_relationship')],
        [InlineKeyboardButton("Свободна", callback_data='status_single')],
        [InlineKeyboardButton("Всё сложно", callback_data='status_complicated')],
        [InlineKeyboardButton("↪️ Расскажу позже", callback_data='skip_family')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "А как у тебя на личном фронте?",
        reply_markup=reply_markup
    )

    return FAMILY_STATUS


async def handle_family_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Касание 3: Обработка статуса отношений.
    """
    query = update.callback_query
    await query.answer()

    status = query.data.replace('status_', '').replace('skip_', '')
    context.user_data['family_status'] = status

    name = context.user_data.get('name', 'дорогая')

    # Логируем выбор семейного статуса
    user_tg = update.effective_user
    user, _ = await user_repo.get_or_create(
        telegram_id=user_tg.id,
        username=user_tg.username,
        first_name=user_tg.first_name,
    )
    await onboarding_event_repo.log_event(
        user_id=user.id,
        event_name="family_status_selected",
        event_data={"status": status}
    )

    # Если пропустили - увеличиваем счетчик и сразу к подарку Premium
    if status == 'family':
        # Увеличиваем счетчик пропусков
        skip_count = context.user_data.get('skip_count', 0)
        context.user_data['skip_count'] = skip_count + 1

        await asyncio.sleep(1.0)
        await query.message.reply_text(f"Хорошо, {name}. Можешь рассказать когда захочешь 💛")
        return await finish_onboarding(query, context)

    # Уточнение для замужних/в отношениях
    if status in ['married', 'relationship']:
        await asyncio.sleep(1.0)
        await query.message.reply_text(
            "Расскажи немного: *как зовут твоего партнёра? Есть ли дети?*\n\n"
            "Или нажми ↪️ если пока не хочешь говорить об этом.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↪️ Расскажу позже", callback_data='skip_details')]]),
            parse_mode='Markdown'
        )
        return FAMILY_DETAILS
    else:
        # Для свободных/сложных сразу к подарку
        return await finish_onboarding(query, context)


async def receive_family_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Касание 4: Получение деталей о семье (партнёр, дети).

    Использует AI-парсинг для извлечения данных о семье.
    """
    from ai.profile_parser import parse_family_details
    from database.repositories.user_profile import UserProfileRepository

    user_input = update.message.text.strip()

    # Проверка на кризис
    is_crisis = await check_crisis_in_message(update, user_input)
    if is_crisis:
        return ConversationHandler.END

    context.user_data['family_details'] = user_input

    user_tg = update.effective_user

    # Получаем пользователя для логирования
    user, _ = await user_repo.get_or_create(
        telegram_id=user_tg.id,
        username=user_tg.username,
        first_name=user_tg.first_name,
    )

    # Логируем ввод семейных данных
    await onboarding_event_repo.log_event(
        user_id=user.id,
        event_name="family_details_entered",
        event_data={"family_details": family_details}
    )

    # Показываем typing
    await send_typing_only(update, delay=1.5)

    # AI-парсинг данных о семье
    try:
        logger.info(f"Parsing family details for user {user_tg.id}: {family_details}")
        parsed_data = await parse_family_details(family_details)
        logger.info(f"Parsed family data: {parsed_data}")

        # Обновляем профиль
        profile_repo = UserProfileRepository()
        await profile_repo.update_profile(
            user.id,
            partner_name=parsed_data.get('partner_name'),
            partner_occupation=parsed_data.get('partner_job'),
            children=parsed_data.get('children'),
            has_partner=bool(parsed_data.get('partner_name')),
            has_children=bool(parsed_data.get('children')),
            children_count=len(parsed_data.get('children', [])) if parsed_data.get('children') else 0,
        )

        # Логируем успешный парсинг семейных данных
        await onboarding_event_repo.log_event(
            user_id=user.id,
            event_name="family_details_parsed",
            event_data=parsed_data
        )

        logger.info(f"Family profile updated for user {user_tg.id}")

    except Exception as e:
        logger.error(f"Error during family parsing: {e}")
        # Продолжаем онбординг даже если парсинг не удался

    return await finish_onboarding(update, context, is_message=True)


async def handle_skip_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка кнопки 'Пропустить' для деталей семьи."""
    query = update.callback_query
    await query.answer()

    name = context.user_data.get('name', 'дорогая')

    # Увеличиваем счетчик пропусков
    skip_count = context.user_data.get('skip_count', 0)
    context.user_data['skip_count'] = skip_count + 1

    # Логируем пропуск
    user_tg = update.effective_user
    user, _ = await user_repo.get_or_create(
        telegram_id=user_tg.id,
        username=user_tg.username,
        first_name=user_tg.first_name,
    )
    await onboarding_event_repo.log_event(
        user_id=user.id,
        event_name="onboarding_skipped",
        event_data={"skipped_step": "family_details", "skip_count": context.user_data['skip_count']}
    )

    await asyncio.sleep(1.0)
    await query.message.reply_text(f"Хорошо, {name}. Когда захочешь — расскажешь 💛")

    return await finish_onboarding(query, context)


async def finish_onboarding(update_or_query, context: ContextTypes.DEFAULT_TYPE, is_message: bool = False) -> int:
    """
    Завершение онбординга: эмпатичный отклик + подарок Premium.
    """
    user_tg = update_or_query.effective_user if hasattr(update_or_query, 'effective_user') else update_or_query.message.chat
    name = context.user_data.get('name', 'дорогая')

    # Получаем user из БД
    user, _ = await user_repo.get_or_create(
        telegram_id=user_tg.id if hasattr(user_tg, 'id') else user_tg,
        username=getattr(user_tg, 'username', None),
        first_name=getattr(user_tg, 'first_name', None),
    )

    # Проверяем количество пропусков
    skip_count = context.user_data.get('skip_count', 0)

    # Закрепляющий эмпатичный отклик (показывает что Мира запомнила)
    social_info = context.user_data.get('social_info', '')

    # Если пропусков 2+ → переход сразу к эмоциональной поддержке
    if skip_count >= 2:
        await asyncio.sleep(1.5)
        message_obj = update_or_query.message if is_message else update_or_query.message
        await message_obj.reply_text(
            f"{name}, я понимаю — иногда непросто делиться личным сразу 💛\n\n"
            "Это нормально. Мы узнаем друг друга постепенно, в своём темпе.\n\n"
            "Что у тебя сейчас на душе?"
        )
    elif social_info:
        await asyncio.sleep(1.5)
        message_obj = update_or_query.message if is_message else update_or_query.message
        await message_obj.reply_text(
            f"{name}, спасибо, что поделилась. Теперь я вижу тебя 💛\n\n"
            "Буду рядом."
        )

    # Показываем финальный прогресс (Шаг 4 из 4) с достижением
    await asyncio.sleep(1.0)
    message_obj = update_or_query.message if is_message else update_or_query.message

    # Финальный прогресс
    progress_msg = get_progress_message(step=4, total=4)
    await message_obj.reply_text(progress_msg)

    # Достижение с подарком
    await asyncio.sleep(1.0)
    await message_obj.reply_text(
        "🏆 **Поздравляю!** Ты завершила знакомство!\n\n"
        "Хочу, чтобы нас ничего не прерывало — дарю тебе **3 дня без ограничений** 💛\n\n"
        "Можешь писать сколько хочешь, отправлять голосовые — я всегда отвечу.",
        parse_mode='Markdown'
    )

    # Выдаём Premium на 3 дня
    from datetime import datetime, timedelta
    premium_until = datetime.utcnow() + timedelta(days=3)
    await user_repo.update(
        user.id,
        premium_until=premium_until,
        onboarding_completed=True,
        onboarding_step=4,
    )

    # Логируем завершение онбординга
    await onboarding_event_repo.log_event(
        user_id=user.id,
        event_name="onboarding_completed",
        event_data={
            "premium_granted": True,
            "premium_until": premium_until.isoformat(),
            "skip_count": skip_count,
            "completed_with_minimal_info": skip_count >= 2
        }
    )

    logger.info(f"User {user_tg.id if hasattr(user_tg, 'id') else user_tg} completed full onboarding")

    # Завершаем ConversationHandler
    return ConversationHandler.END


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена онбординга."""
    await update.message.reply_text(
        "Ты всегда можешь вернуться командой /start 💛"
    )
    return ConversationHandler.END
