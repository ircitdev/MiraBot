"""
Content handlers.
Обработчики для упражнений, аффирмаций, медитаций.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from content.exercises import (
    ExerciseCategory,
    get_exercises_by_category,
    get_exercise_by_id,
    get_exercise_for_state,
    get_random_exercise,
    format_exercise,
    format_exercise_short,
)
from content.affirmations import (
    get_daily_affirmation,
    get_affirmation_by_category,
    get_affirmation_for_mood,
    format_affirmation,
    AFFIRMATION_CATEGORIES,
)


async def exercises_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /exercises — показывает меню упражнений."""

    keyboard = [
        [
            InlineKeyboardButton("🌬️ Дыхательные", callback_data="ex:cat:breathing"),
            InlineKeyboardButton("🧘 Релаксация", callback_data="ex:cat:relaxation"),
        ],
        [
            InlineKeyboardButton("🖐️ Заземление", callback_data="ex:cat:grounding"),
            InlineKeyboardButton("⚡ Быстрые (1-2 мин)", callback_data="ex:cat:quick"),
        ],
        [
            InlineKeyboardButton("🎲 Случайное упражнение", callback_data="ex:random"),
        ],
    ]

    text = """🧘 **Библиотека упражнений**

Здесь собраны техники, которые помогут справиться с тревогой, напряжением и стрессом.

Выбери категорию или попроси меня подобрать что-то под твоё состояние — просто напиши, что чувствуешь."""

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def affirmation_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /affirmation — показывает аффирмацию дня."""

    user_id = update.effective_user.id
    affirmation = get_daily_affirmation(user_id)

    text = f"""💛 **Аффирмация дня**

{format_affirmation(affirmation)}

Повтори её несколько раз. Можешь написать в ответ или сохранить 📌"""

    keyboard = [
        [
            InlineKeyboardButton("🔄 Другая", callback_data="aff:random"),
            InlineKeyboardButton("📚 Категории", callback_data="aff:categories"),
        ],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def handle_content_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback-кнопок для контента."""

    query = update.callback_query
    await query.answer()

    data = query.data

    # === УПРАЖНЕНИЯ ===

    if data.startswith("ex:cat:"):
        # Показать упражнения категории
        category_key = data.replace("ex:cat:", "")
        category_map = {
            "breathing": ExerciseCategory.BREATHING,
            "relaxation": ExerciseCategory.RELAXATION,
            "grounding": ExerciseCategory.GROUNDING,
            "quick": ExerciseCategory.QUICK,
        }
        category = category_map.get(category_key)

        if category:
            exercises = get_exercises_by_category(category)
            keyboard = []
            for ex in exercises:
                keyboard.append([
                    InlineKeyboardButton(
                        format_exercise_short(ex),
                        callback_data=f"ex:show:{ex.id}",
                    )
                ])
            keyboard.append([
                InlineKeyboardButton("◀️ Назад", callback_data="ex:menu"),
            ])

            category_names = {
                ExerciseCategory.BREATHING: "🌬️ Дыхательные упражнения",
                ExerciseCategory.RELAXATION: "🧘 Упражнения на релаксацию",
                ExerciseCategory.GROUNDING: "🖐️ Техники заземления",
                ExerciseCategory.QUICK: "⚡ Быстрые упражнения",
            }

            await query.edit_message_text(
                f"**{category_names[category]}**\n\nВыбери упражнение:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

    elif data.startswith("ex:show:"):
        # Показать конкретное упражнение
        exercise_id = data.replace("ex:show:", "")
        exercise = get_exercise_by_id(exercise_id)

        if exercise:
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Другое упражнение", callback_data="ex:random"),
                ],
                [
                    InlineKeyboardButton("◀️ К категориям", callback_data="ex:menu"),
                ],
            ]

            await query.edit_message_text(
                format_exercise(exercise),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

    elif data == "ex:random":
        # Случайное упражнение
        exercise = get_random_exercise()

        keyboard = [
            [
                InlineKeyboardButton("🔄 Ещё одно", callback_data="ex:random"),
            ],
            [
                InlineKeyboardButton("◀️ К категориям", callback_data="ex:menu"),
            ],
        ]

        await query.edit_message_text(
            format_exercise(exercise),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "ex:menu":
        # Вернуться в меню упражнений
        keyboard = [
            [
                InlineKeyboardButton("🌬️ Дыхательные", callback_data="ex:cat:breathing"),
                InlineKeyboardButton("🧘 Релаксация", callback_data="ex:cat:relaxation"),
            ],
            [
                InlineKeyboardButton("🖐️ Заземление", callback_data="ex:cat:grounding"),
                InlineKeyboardButton("⚡ Быстрые", callback_data="ex:cat:quick"),
            ],
            [
                InlineKeyboardButton("🎲 Случайное", callback_data="ex:random"),
            ],
        ]

        await query.edit_message_text(
            "🧘 **Библиотека упражнений**\n\nВыбери категорию:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # === АФФИРМАЦИИ ===

    elif data == "aff:random":
        # Случайная аффирмация
        affirmation = get_affirmation_by_category(
            list(AFFIRMATION_CATEGORIES.keys())[0]
        )
        import random
        category = random.choice(list(AFFIRMATION_CATEGORIES.keys()))
        affirmation = get_affirmation_by_category(category)

        keyboard = [
            [
                InlineKeyboardButton("🔄 Ещё", callback_data="aff:random"),
                InlineKeyboardButton("📚 Категории", callback_data="aff:categories"),
            ],
        ]

        await query.edit_message_text(
            f"✨ {affirmation}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "aff:categories":
        # Показать категории аффирмаций
        keyboard = []
        emoji_map = {
            "self_love": "💕",
            "calm": "🌊",
            "strength": "💪",
            "boundaries": "🚧",
            "motherhood": "👩‍👧",
            "relationships": "💑",
            "growth": "🌱",
            "morning": "🌅",
            "evening": "🌙",
        }

        for key, name in AFFIRMATION_CATEGORIES.items():
            emoji = emoji_map.get(key, "✨")
            keyboard.append([
                InlineKeyboardButton(
                    f"{emoji} {name}",
                    callback_data=f"aff:cat:{key}",
                )
            ])

        await query.edit_message_text(
            "📚 **Категории аффирмаций**\n\nВыбери тему:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data.startswith("aff:cat:"):
        # Аффирмация из категории
        category = data.replace("aff:cat:", "")
        affirmation = get_affirmation_by_category(category)

        keyboard = [
            [
                InlineKeyboardButton("🔄 Ещё из этой", callback_data=f"aff:cat:{category}"),
            ],
            [
                InlineKeyboardButton("📚 Другие категории", callback_data="aff:categories"),
            ],
        ]

        category_name = AFFIRMATION_CATEGORIES.get(category, "")

        await query.edit_message_text(
            f"**{category_name}**\n\n✨ {affirmation}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )


async def suggest_exercise_for_state(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: str,
) -> None:
    """
    Предлагает упражнение под состояние пользователя.
    Вызывается из основного обработчика сообщений при обнаружении триггеров.
    """
    exercise = get_exercise_for_state(state)

    keyboard = [
        [
            InlineKeyboardButton("📖 Показать", callback_data=f"ex:show:{exercise.id}"),
            InlineKeyboardButton("🔄 Другое", callback_data="ex:random"),
        ],
    ]

    text = f"""💡 Вот что может помочь:

{format_exercise_short(exercise)}

Хочешь попробовать?"""

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
