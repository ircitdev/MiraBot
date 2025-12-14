"""
Inline keyboards.
Инлайн-клавиатуры для бота.
"""

from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_hints_keyboard(hints: List) -> InlineKeyboardMarkup:
    """
    Клавиатура с контекстными подсказками.

    Args:
        hints: Список объектов Hint с полями text и message

    Returns:
        InlineKeyboardMarkup с кнопками подсказок
    """
    if not hints:
        return None

    keyboard = []
    for i, hint in enumerate(hints):
        # callback_data формат: hint:{index}:{hash сообщения}
        # Используем индекс для идентификации подсказки
        callback_data = f"hint:{i}"
        keyboard.append([InlineKeyboardButton(hint.text, callback_data=callback_data)])

    return InlineKeyboardMarkup(keyboard)


def get_premium_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для предложения премиума."""
    keyboard = [
        [InlineKeyboardButton("✨ Узнать о Premium", callback_data="subscribe:show")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_crisis_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для кризисных ситуаций."""
    keyboard = [
        [InlineKeyboardButton("📞 Телефон доверия", callback_data="crisis:hotline")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_persona_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора персоны."""
    keyboard = [
        [
            InlineKeyboardButton("👩 Мира", callback_data="persona:mira"),
            InlineKeyboardButton("👨 Марк", callback_data="persona:mark"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_subscription_plans_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с планами подписки."""
    from config.settings import settings
    
    keyboard = [
        [InlineKeyboardButton(
            f"💎 1 месяц — {settings.PRICE_MONTHLY} ₽",
            callback_data="subscribe:monthly"
        )],
        [InlineKeyboardButton(
            f"💎 3 месяца — {settings.PRICE_QUARTERLY} ₽",
            callback_data="subscribe:quarterly"
        )],
        [InlineKeyboardButton(
            f"💎 1 год — {settings.PRICE_YEARLY} ₽",
            callback_data="subscribe:yearly"
        )],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_rituals_keyboard(enabled_rituals: list) -> InlineKeyboardMarkup:
    """Клавиатура настройки ритуалов."""
    
    def status(ritual: str) -> str:
        return "✅" if ritual in enabled_rituals else "❌"
    
    keyboard = [
        [InlineKeyboardButton(
            f"{status('morning')} Утренний check-in",
            callback_data="ritual:toggle:morning"
        )],
        [InlineKeyboardButton(
            f"{status('evening')} Вечерний check-in",
            callback_data="ritual:toggle:evening"
        )],
        [InlineKeyboardButton(
            f"{status('gratitude')} Благодарность дня",
            callback_data="ritual:toggle:gratitude"
        )],
        [InlineKeyboardButton(
            f"{status('letter')} Письмо себе",
            callback_data="ritual:toggle:letter"
        )],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirmation_keyboard(
    confirm_text: str = "✅ Да",
    cancel_text: str = "❌ Нет",
    confirm_data: str = "confirm",
    cancel_data: str = "cancel",
) -> InlineKeyboardMarkup:
    """Универсальная клавиатура подтверждения."""
    keyboard = [
        [
            InlineKeyboardButton(confirm_text, callback_data=confirm_data),
            InlineKeyboardButton(cancel_text, callback_data=cancel_data),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
