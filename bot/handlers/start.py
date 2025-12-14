"""
Start command handler.
Онбординг новых пользователей.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from database.repositories.user import UserRepository
from database.repositories.referral import ReferralRepository
from config.constants import PERSONA_MIRA, PERSONA_MARK, ONBOARDING_STEP_START


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
    if referral_code and created:
        await _process_referral(user.id, referral_code)
    
    if created or not user.onboarding_completed:
        # Новый пользователь — начинаем онбординг
        await _start_onboarding(update, user)
    else:
        # Возвращающийся пользователь
        await _welcome_back(update, user)
    
    logger.info(f"User {user_tg.id} started bot (created={created})")


async def _start_onboarding(update: Update, user) -> None:
    """Начинает процесс онбординга."""

    # Устанавливаем Миру по умолчанию и переходим к шагу 1 (ввод имени)
    await user_repo.update(
        user.id,
        persona=PERSONA_MIRA,
        onboarding_step=1,
    )

    text = """Привет 💛

Я Мира. Мне 42, замужем 18 лет, двое детей. Я прошла через кризис в браке, выгорание — и нашла путь обратно.

Я здесь, чтобы слушать. Не как психолог — а как подруга, которая не осудит и не будет учить жить.

Как мне к тебе обращаться?"""

    await update.message.reply_text(text)


async def _welcome_back(update: Update, user) -> None:
    """Приветствует возвращающегося пользователя."""

    user_name = user.display_name or "дорогая"

    text = f"""Привет, {user_name} 💛

Это Мира. Рада тебя видеть снова.

Как ты? Что на душе? Можешь написать или отправить голосовое 🎤"""

    await update.message.reply_text(text)


async def _process_referral(user_id: int, code: str) -> None:
    """Обрабатывает реферальный код."""
    from services.referral import ReferralService
    
    referral_service = ReferralService()
    result = await referral_service.apply_referral(user_id, code)
    
    if result.get("success"):
        logger.info(f"Referral {code} applied for user {user_id}")


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

**Команды:**
/exercises — упражнения (дыхание, релаксация, заземление)
/affirmation — аффирмация дня
/meditation — медитации (тексты для практики)
/settings — настройки бота
/subscription — твоя подписка
/referral — пригласи подругу
/rituals — настрой ритуалы

**Голосовые сообщения:**
Можешь говорить — я пойму! Отправь голосовое сообщение, я его расшифрую и отвечу 🎤

**Важно:**
Если тебе очень тяжело — я рядом. Но в серьёзных ситуациях я направлю тебя к людям, которые могут помочь профессионально. Это не слабость — это забота о себе.

Телефон доверия: 8-800-2000-122 (бесплатно, круглосуточно)

Просто напиши или скажи — я слушаю 💛"""
    
    await update.message.reply_text(text, parse_mode="Markdown")
