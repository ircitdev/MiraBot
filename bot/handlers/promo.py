"""
Promo Code Handler.
Обработка команды /promo для активации промокодов.
"""

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
from loguru import logger

from database.repositories.promo import promo_repo
from database.repositories.user import UserRepository

# Состояния для ConversationHandler
WAITING_FOR_CODE = 1


async def promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /promo.
    Может принимать код сразу: /promo SUMMER2024
    Или запрашивать код отдельно: /promo
    """
    user_repo = UserRepository()
    tg_user = update.effective_user

    # Получаем пользователя из БД
    user = await user_repo.get_by_telegram_id(tg_user.id)
    if not user:
        await update.message.reply_text(
            "❌ Сначала начните общение с ботом, отправив любое сообщение."
        )
        return ConversationHandler.END

    # Проверяем, передан ли код в команде
    if context.args:
        code = " ".join(context.args).strip()
        return await _apply_promo_code(update, context, user.id, code)

    # Запрашиваем код
    await update.message.reply_text(
        "🎁 *Активация промокода*\n\n"
        "Введите ваш промокод:",
        parse_mode="Markdown"
    )

    # Сохраняем user_id в контексте
    context.user_data["promo_user_id"] = user.id

    return WAITING_FOR_CODE


async def receive_promo_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает промокод от пользователя."""
    code = update.message.text.strip()
    user_id = context.user_data.get("promo_user_id")

    if not user_id:
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте снова: /promo")
        return ConversationHandler.END

    return await _apply_promo_code(update, context, user_id, code)


async def _apply_promo_code(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    code: str,
) -> int:
    """Применяет промокод."""
    # Проверяем промокод
    result = await promo_repo.apply(code, user_id)

    if not result["success"]:
        await update.message.reply_text(
            f"❌ {result['error']}\n\n"
            "Проверьте правильность кода и попробуйте снова."
        )
        return ConversationHandler.END

    # Формируем сообщение об успехе
    promo_result = result["result"]
    promo_type = promo_result["type"]
    value = promo_result["value"]

    if promo_type == "free_days":
        message = (
            f"✅ *Промокод активирован!*\n\n"
            f"🎁 Вам добавлено *{value} дней* Premium подписки!\n\n"
            f"Наслаждайтесь всеми преимуществами Premium."
        )
    elif promo_type == "free_trial":
        message = (
            f"✅ *Промокод активирован!*\n\n"
            f"🎁 Вам активирован *Trial период* на *{value} дней*!\n\n"
            f"Попробуйте все возможности Premium бесплатно."
        )
    elif promo_type == "discount_percent":
        message = (
            f"✅ *Промокод активирован!*\n\n"
            f"💰 Скидка *{value}%* будет применена при следующей оплате!\n\n"
            f"Используйте /subscribe для оформления подписки со скидкой."
        )
    elif promo_type == "discount_amount":
        message = (
            f"✅ *Промокод активирован!*\n\n"
            f"💰 Скидка *{value}₽* будет применена при следующей оплате!\n\n"
            f"Используйте /subscribe для оформления подписки со скидкой."
        )
    else:
        message = "✅ *Промокод активирован!*"

    await update.message.reply_text(message, parse_mode="Markdown")

    logger.info(f"User {user_id} applied promo code: {code} ({promo_type}={value})")

    return ConversationHandler.END


async def cancel_promo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена ввода промокода."""
    await update.message.reply_text(
        "Ввод промокода отменён.\n"
        "Чтобы активировать промокод позже, используйте /promo"
    )
    return ConversationHandler.END


def get_promo_handler() -> ConversationHandler:
    """Возвращает ConversationHandler для промокодов."""
    return ConversationHandler(
        entry_points=[CommandHandler("promo", promo_command)],
        states={
            WAITING_FOR_CODE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_promo_code
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_promo),
            MessageHandler(filters.COMMAND, cancel_promo),
        ],
        conversation_timeout=120,  # 2 минуты на ввод кода
    )
