"""
Programs handlers.
Обработчики команд для структурированных программ.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger

from database.repositories.user import UserRepository
from database.repositories.program import ProgramRepository
from ai.programs.catalog import (
    get_program,
    get_all_programs,
    format_program_info,
    format_programs_list,
    get_program_morning_message,
    get_program_completion_message,
)


user_repo = UserRepository()
program_repo = ProgramRepository()


async def programs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /programs - показывает доступные программы."""

    user = await user_repo.get_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text("Сначала напиши /start 💛")
        return

    # Получаем активные программы пользователя
    active_programs = await program_repo.get_active_programs(user.id)

    if active_programs:
        # Показываем активные программы
        parts = ["📚 **Твои активные программы:**\n"]

        keyboard = []

        for prog in active_programs:
            progress = f"{prog.current_day}/{prog.total_days}"
            parts.append(f"\n🌸 **{prog.program_name}**")
            parts.append(f"Прогресс: День {progress}")

            # Кнопки для каждой программы
            keyboard.append([
                InlineKeyboardButton(
                    f"📝 Текущее задание — {prog.program_name}",
                    callback_data=f"program:task:{prog.id}"
                )
            ])
            keyboard.append([
                InlineKeyboardButton("⏸ Пауза", callback_data=f"program:pause:{prog.id}"),
                InlineKeyboardButton("❌ Прекратить", callback_data=f"program:abandon:{prog.id}"),
            ])

        parts.append("\n\n—\n")
        parts.append("Хочешь начать ещё одну программу?")

        keyboard.append([
            InlineKeyboardButton("📚 Все программы", callback_data="program:catalog")
        ])

        await update.message.reply_text(
            "\n".join(parts),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    else:
        # Показываем каталог программ
        text = format_programs_list()

        keyboard = []
        for program in get_all_programs():
            keyboard.append([
                InlineKeyboardButton(
                    f"{program['emoji']} {program['name']}",
                    callback_data=f"program:info:{program['id']}"
                )
            ])

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )


async def program_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback-кнопок для программ."""

    query = update.callback_query
    await query.answer()

    data = query.data.split(":")
    action = data[1]

    user = await user_repo.get_by_telegram_id(update.effective_user.id)
    if not user:
        await query.edit_message_text("Сначала напиши /start 💛")
        return

    if action == "catalog":
        # Показать каталог программ
        text = format_programs_list()

        keyboard = []
        for program in get_all_programs():
            keyboard.append([
                InlineKeyboardButton(
                    f"{program['emoji']} {program['name']}",
                    callback_data=f"program:info:{program['id']}"
                )
            ])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif action == "info":
        # Показать информацию о программе
        program_id = data[2]
        program = get_program(program_id)

        if not program:
            await query.edit_message_text("Программа не найдена 😕")
            return

        text = format_program_info(program)

        # Проверяем есть ли уже активная
        existing = await program_repo.get_active_by_program(user.id, program_id)

        keyboard = []
        if existing:
            keyboard.append([
                InlineKeyboardButton("📝 Текущее задание", callback_data=f"program:task:{existing.id}")
            ])
            keyboard.append([
                InlineKeyboardButton("⏸ Пауза", callback_data=f"program:pause:{existing.id}"),
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("🚀 Начать программу", callback_data=f"program:start:{program_id}")
            ])

        keyboard.append([
            InlineKeyboardButton("« Назад", callback_data="program:catalog")
        ])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif action == "start":
        # Начать программу
        program_id = data[2]
        program = get_program(program_id)

        if not program:
            await query.edit_message_text("Программа не найдена 😕")
            return

        # Создаём участие в программе
        program_entry = await program_repo.create(
            user_id=user.id,
            program_id=program_id,
            program_name=program["name"],
            total_days=program["total_days"],
            reminder_time="09:00",  # По умолчанию
        )

        # Отправляем первое задание
        morning_message = get_program_morning_message(program_id, 1)

        text = f"""🎉 **Ты начала программу "{program['name']}"!**

Каждый день в 09:00 я буду присылать тебе новое задание.

—

{morning_message}"""

        keyboard = [
            [InlineKeyboardButton("✅ Сделала!", callback_data=f"program:done:{program_entry.id}")],
            [InlineKeyboardButton("⏰ Изменить время напоминаний", callback_data=f"program:set_time:{program_entry.id}")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

        logger.info(f"User {user.id} started program {program_id}")

    elif action == "task":
        # Показать текущее задание
        program_entry_id = int(data[2])
        program_entry = await program_repo.get(program_entry_id)

        if not program_entry or program_entry.user_id != user.id:
            await query.edit_message_text("Программа не найдена 😕")
            return

        morning_message = get_program_morning_message(
            program_entry.program_id,
            program_entry.current_day
        )

        text = f"""📝 **{program_entry.program_name}**
День {program_entry.current_day} из {program_entry.total_days}

—

{morning_message or 'Задание для этого дня не найдено'}"""

        keyboard = [
            [InlineKeyboardButton("✅ Сделала!", callback_data=f"program:done:{program_entry_id}")],
            [InlineKeyboardButton("⏸ Пауза", callback_data=f"program:pause:{program_entry_id}")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif action == "done":
        # Отметить день как выполненный
        program_entry_id = int(data[2])
        program_entry = await program_repo.complete_day(program_entry_id)

        if not program_entry:
            await query.edit_message_text("Программа не найдена 😕")
            return

        if program_entry.status == "completed":
            # Программа завершена!
            completion_message = get_program_completion_message(program_entry.program_id)

            await query.edit_message_text(
                completion_message or "🎉 Поздравляю! Ты завершила программу!",
                parse_mode="Markdown",
            )
        else:
            # Переходим к следующему дню
            progress_bar = "▓" * program_entry.current_day + "░" * (program_entry.total_days - program_entry.current_day)

            text = f"""✅ **Молодец!** День {program_entry.current_day - 1} выполнен!

Прогресс: [{progress_bar}] {program_entry.current_day - 1}/{program_entry.total_days}

Завтра в 09:00 пришлю задание на день {program_entry.current_day}.

Отдыхай и заботься о себе 💛"""

            keyboard = [
                [InlineKeyboardButton("📝 Посмотреть следующее задание", callback_data=f"program:task:{program_entry_id}")],
            ]

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

    elif action == "pause":
        # Поставить на паузу
        program_entry_id = int(data[2])
        program_entry = await program_repo.pause_program(program_entry_id)

        if not program_entry:
            await query.edit_message_text("Программа не найдена 😕")
            return

        text = f"""⏸ **Программа "{program_entry.program_name}" на паузе**

Ты на дне {program_entry.current_day} из {program_entry.total_days}.

Когда будешь готова продолжить — нажми кнопку ниже.
Я буду ждать 💛"""

        keyboard = [
            [InlineKeyboardButton("▶️ Продолжить", callback_data=f"program:resume:{program_entry_id}")],
            [InlineKeyboardButton("❌ Прекратить совсем", callback_data=f"program:abandon:{program_entry_id}")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif action == "resume":
        # Возобновить программу
        program_entry_id = int(data[2])
        program_entry = await program_repo.resume_program(program_entry_id)

        if not program_entry:
            await query.edit_message_text("Программа не найдена 😕")
            return

        morning_message = get_program_morning_message(
            program_entry.program_id,
            program_entry.current_day
        )

        text = f"""▶️ **Продолжаем!**

Ты на дне {program_entry.current_day} из {program_entry.total_days}.

—

{morning_message or 'Задание для этого дня'}"""

        keyboard = [
            [InlineKeyboardButton("✅ Сделала!", callback_data=f"program:done:{program_entry_id}")],
            [InlineKeyboardButton("⏸ Пауза", callback_data=f"program:pause:{program_entry_id}")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif action == "abandon":
        # Подтверждение прекращения
        program_entry_id = int(data[2])

        text = """❓ **Точно хочешь прекратить программу?**

Твой прогресс будет сохранён, и ты сможешь начать заново в любой момент."""

        keyboard = [
            [InlineKeyboardButton("Да, прекратить", callback_data=f"program:confirm_abandon:{program_entry_id}")],
            [InlineKeyboardButton("Нет, продолжу", callback_data=f"program:task:{program_entry_id}")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif action == "confirm_abandon":
        # Подтверждённое прекращение
        program_entry_id = int(data[2])
        program_entry = await program_repo.abandon_program(program_entry_id)

        if not program_entry:
            await query.edit_message_text("Программа не найдена 😕")
            return

        text = f"""Программа "{program_entry.program_name}" прекращена.

Ты прошла {len(program_entry.completed_days or [])} дней из {program_entry.total_days}.

Если захочешь попробовать снова — /programs 💛"""

        await query.edit_message_text(text, parse_mode="Markdown")

    elif action == "set_time":
        # Настройка времени напоминаний
        program_entry_id = int(data[2])

        text = """⏰ **Выбери время для ежедневных напоминаний:**"""

        keyboard = [
            [
                InlineKeyboardButton("07:00", callback_data=f"program:time:{program_entry_id}:07:00"),
                InlineKeyboardButton("08:00", callback_data=f"program:time:{program_entry_id}:08:00"),
                InlineKeyboardButton("09:00", callback_data=f"program:time:{program_entry_id}:09:00"),
            ],
            [
                InlineKeyboardButton("10:00", callback_data=f"program:time:{program_entry_id}:10:00"),
                InlineKeyboardButton("11:00", callback_data=f"program:time:{program_entry_id}:11:00"),
                InlineKeyboardButton("12:00", callback_data=f"program:time:{program_entry_id}:12:00"),
            ],
            [
                InlineKeyboardButton("18:00", callback_data=f"program:time:{program_entry_id}:18:00"),
                InlineKeyboardButton("19:00", callback_data=f"program:time:{program_entry_id}:19:00"),
                InlineKeyboardButton("20:00", callback_data=f"program:time:{program_entry_id}:20:00"),
            ],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif action == "time":
        # Установка времени
        program_entry_id = int(data[2])
        time_str = data[3]

        await program_repo.update_reminder_time(program_entry_id, time_str)

        text = f"""✅ Время напоминаний установлено: **{time_str}**

Буду присылать задания каждый день в это время!"""

        keyboard = [
            [InlineKeyboardButton("📝 К заданию", callback_data=f"program:task:{program_entry_id}")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
