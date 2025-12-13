"""
Message handler.
Основной обработчик текстовых сообщений.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger
from datetime import datetime

from config.settings import settings
from ai.claude_client import ClaudeClient
from database.repositories.user import UserRepository
from database.repositories.subscription import SubscriptionRepository
from database.repositories.conversation import ConversationRepository
from services.referral import ReferralService
from bot.keyboards.inline import get_premium_keyboard, get_crisis_keyboard
from bot.handlers.photos import send_photos
from utils.text_parser import extract_name_from_text


# Инициализируем сервисы
claude = ClaudeClient()
user_repo = UserRepository()
subscription_repo = SubscriptionRepository()
conversation_repo = ConversationRepository()
referral_service = ReferralService()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Основной обработчик текстовых сообщений."""
    
    user_tg = update.effective_user
    message_text = update.message.text
    
    try:
        # 1. Получаем пользователя
        user, _ = await user_repo.get_or_create(
            telegram_id=user_tg.id,
            username=user_tg.username,
            first_name=user_tg.first_name,
        )
        
        # 2. Проверяем блокировку
        if user.is_blocked:
            await update.message.reply_text(
                "К сожалению, доступ ограничен. "
                "Если считаешь, что это ошибка — напиши в поддержку."
            )
            return
        
        # 3. Проверяем онбординг
        if not user.onboarding_completed:
            await _handle_onboarding(update, context, user, message_text)
            return

        # 3.5. Проверяем запрос на фотографии
        if await send_photos(update, context):
            return

        # 4. Проверяем лимиты
        subscription = await subscription_repo.get_active(user.id)
        is_premium = subscription and subscription.plan == "premium"
        
        if not is_premium:
            # Проверяем дневной лимит
            if subscription and subscription.messages_today >= settings.FREE_MESSAGES_PER_DAY:
                await _send_limit_reached(update)
                return
            
            # Увеличиваем счётчик
            if subscription:
                await subscription_repo.increment_messages(subscription.id)
        
        # 5. Обновляем last_active
        await user_repo.update_last_active(user.id)
        
        # 6. Показываем "печатает..."
        await update.message.chat.send_action("typing")
        
        # 7. Подготавливаем данные пользователя
        user_data = {
            "persona": user.persona,
            "display_name": user.display_name,
            "partner_name": user.partner_name,
            "children_info": user.children_info,
            "marriage_years": user.marriage_years,
            "partner_gender": getattr(user, "partner_gender", None),
        }
        
        # 8. Получаем ответ от Claude
        result = await claude.generate_response(
            user_id=user.id,
            user_message=message_text,
            user_data=user_data,
            is_premium=is_premium,
        )
        
        # 9. Сохраняем сообщения
        await conversation_repo.save_message(
            user_id=user.id,
            role="user",
            content=message_text,
            tags=[],
        )
        
        await conversation_repo.save_message(
            user_id=user.id,
            role="assistant",
            content=result["response"],
            tags=result["tags"],
            tokens_used=result["tokens_used"],
        )
        
        # 10. Отправляем ответ
        await _send_response(update, result)
        
        # 11. Проверяем триггеры реферала
        if not is_premium:
            await _check_referral_trigger(update, user, result)
        
        logger.info(
            f"Message processed for user {user_tg.id}, "
            f"tokens={result['tokens_used']}, "
            f"is_crisis={result['is_crisis']}"
        )
        
    except Exception as e:
        logger.error(f"Error handling message from {user_tg.id}: {e}")
        await update.message.reply_text(
            "Прости, что-то пошло не так... Попробуй ещё раз через минутку 💛"
        )


async def _handle_onboarding(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user,
    message_text: str,
) -> None:
    """Обработка сообщений во время онбординга."""
    
    step = user.onboarding_step
    
    if step == 1:
        # Ожидаем имя пользователя
        display_name = extract_name_from_text(message_text)
        
        if not display_name:
            await update.message.reply_text(
                "Как мне к тебе обращаться? Напиши своё имя 💛"
            )
            return
        
        await user_repo.update(
            user.id,
            display_name=display_name,
            onboarding_step=2,
            onboarding_completed=True,
        )

        text = f"""{display_name}, очень приятно 💛

Просто буду рядом. Можешь писать или отправлять голосовые 🎤

Расскажи, что тебя сюда привело? Или начни с чего угодно — как прошёл день, что на душе..."""

        await update.message.reply_text(text)
        
    else:
        # Неожиданное состояние — отправляем на выбор персоны
        from bot.handlers.start import _start_onboarding
        await _start_onboarding(update, user)


async def _send_response(update: Update, result: dict) -> None:
    """Отправляет ответ пользователю."""
    
    response_text = result["response"]
    
    # Разбиваем на части если есть разделитель
    parts = response_text.split("---")
    
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        
        # Для последней части добавляем кнопки при кризисе
        if result["is_crisis"] and i == len(parts) - 1:
            keyboard = get_crisis_keyboard()
            await update.message.reply_text(part, reply_markup=keyboard)
        else:
            await update.message.reply_text(part)


async def _send_limit_reached(update: Update) -> None:
    """Отправляет сообщение о достижении лимита."""
    
    text = """Наш разговор сегодня подходит к паузе... 
Но я здесь, и завтра мы продолжим 💛

Если хочешь общаться без ограничений — есть премиум-доступ."""
    
    keyboard = get_premium_keyboard()
    await update.message.reply_text(text, reply_markup=keyboard)


async def _check_referral_trigger(update: Update, user, result: dict) -> None:
    """Проверяет, нужно ли предложить реферальную программу."""
    
    # Не показываем при кризисе
    if result["is_crisis"]:
        return
    
    # Показываем при инсайтах или позитивных сигналах
    should_show = False
    
    if "insight" in result["tags"]:
        should_show = True
    
    if "positive" in result["tags"]:
        should_show = True
    
    if not should_show:
        return
    
    # Проверяем, не показывали ли недавно (через context или БД)
    # Пока простая логика — показываем редко
    import random
    if random.random() > 0.2:  # 20% шанс
        return
    
    # Получаем реферальный код
    code = await referral_service.get_or_create_code(user.id)
    
    if "insight" in result["tags"]:
        text = f"""💛 Рада, что удалось увидеть что-то новое.

Если у тебя есть подруга, которой тоже нужно безопасное место выговориться — можешь поделиться.

Ваш код: `{code}`
Вам обеим будет +7 дней без ограничений 🎁"""
    else:
        text = f"""💛 Если знаешь кого-то, кому тоже не с кем поговорить — можешь пригласить.

Ваш код: `{code}`"""
    
    await update.message.reply_text(text, parse_mode="Markdown")
