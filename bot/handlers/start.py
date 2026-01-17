"""
Start command handler.
Онбординг новых пользователей.
"""

from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from database.repositories.user import UserRepository
from database.repositories.referral import ReferralRepository
from config.constants import PERSONA_MIRA, PERSONA_MARK, ONBOARDING_STEP_START
from services.avatar_service import avatar_service


user_repo = UserRepository()
referral_repo = ReferralRepository()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /start.
    Начинает онбординг или приветствует возвращающегося пользователя.
    """
    user_tg = update.effective_user

    # Проверяем реферальный код
    referral_code = None
    if context.args:
        referral_code = context.args[0]

    # Получаем или создаём пользователя
    user, created = await user_repo.get_or_create(
        telegram_id=user_tg.id,
        username=user_tg.username,
        first_name=user_tg.first_name,
    )

    # Обрабатываем реферальный код
    referrer_telegram_id = None
    if referral_code and created:
        referrer_telegram_id = await _process_referral(user.id, referral_code)

    # Логируем регистрацию нового пользователя в admin logs
    if created:
        try:
            from database.repositories.admin_log import AdminLogRepository
            admin_log_repo = AdminLogRepository()

            details = {
                "telegram_id": user_tg.id,
                "username": user_tg.username,
                "first_name": user_tg.first_name,
            }

            if referral_code and referrer_telegram_id:
                details["referral_code"] = referral_code
                details["referrer_telegram_id"] = referrer_telegram_id

            await admin_log_repo.create(
                admin_user_id=1,  # Системное событие
                action="new_user_registration",
                resource_type="user",
                resource_id=user_tg.id,
                details=details,
                success=True,
            )
        except Exception as e:
            logger.warning(f"Failed to log new user registration: {e}")

    # Загружаем аватарку если её нет
    if not user.avatar_url:
        try:
            avatar_url = await avatar_service.fetch_and_save_avatar(
                bot=context.bot,
                telegram_id=user_tg.id,
                user_id=user.id,
            )
            if avatar_url:
                await user_repo.update(user.id, avatar_url=avatar_url)
        except Exception as e:
            logger.warning(f"Failed to fetch avatar for user {user_tg.id}: {e}")

    if created or not user.onboarding_completed:
        # Новый пользователь — начинаем онбординг
        await _start_onboarding(update, user)
    else:
        # Возвращающийся пользователь
        await _welcome_back(update, user)

    logger.info(f"User {user_tg.id} started bot (created={created})")


async def _start_onboarding(update: Update, user) -> None:
    """
    Начинает процесс онбординга.

    Примечание: Фактический онбординг теперь обрабатывается через ConversationHandler
    в bot/handlers/onboarding.py. Эта функция вызывается для совместимости.
    """
    # Устанавливаем Миру по умолчанию и переходим к шагу 1 (ввод имени)
    await user_repo.update(
        user.id,
        persona=PERSONA_MIRA,
        onboarding_step=1,
    )

    # Старый текст закомментирован - теперь используется ConversationHandler
    # который отправляет сообщения постепенно с паузами
    pass


async def _welcome_back(update: Update, user) -> None:
    """Приветствует возвращающегося пользователя."""

    user_name = user.display_name or "дорогая"

    text = f"""Привет, {user_name} 💛

Это Мира. Рада тебя видеть снова.

Как ты? Что на душе? Можешь написать или отправить голосовое 🎤"""

    await update.message.reply_text(text)


async def _process_referral(user_id: int, code: str) -> int | None:
    """
    Обрабатывает реферальный код.

    Returns:
        telegram_id реферера если успешно, иначе None
    """
    from services.referral import ReferralService

    referral_service = ReferralService()
    result = await referral_service.apply_referral(user_id, code)

    if result.get("success"):
        logger.info(f"Referral {code} applied for user {user_id}")
        return result.get("referrer_telegram_id")

    return None


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""

    text = """**Что я умею** 💛

Я — твой друг. Не психолог, не терапевт — просто тот, кто выслушает и поддержит.

**О чём можно говорить:**
• Отношения в браке
• Материнство и дети
• Самореализация
• Усталость и выгорание
• Всё, что на душе

**Голосовые сообщения:**
Можешь говорить — я пойму! Отправь голосовое сообщение, я его расшифрую и отвечу 🎤

**Фото:**
Можешь отправить мне фото — я посмотрю и мы обсудим 📸

**Важно:**
Если тебе очень тяжело — я рядом. Но в серьёзных ситуациях я направлю тебя к людям, которые могут помочь профессионально. Это не слабость — это забота о себе.

Телефон доверия: 8-800-2000-122 (бесплатно, круглосуточно)

Просто напиши или скажи — я слушаю 💛

_Подсказка: все команды находятся в меню бота (кнопка слева от строки ввода) ⌨️_"""

    await update.message.reply_text(text, parse_mode="Markdown")
