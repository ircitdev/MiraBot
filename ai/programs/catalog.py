"""
Programs Catalog.
Каталог доступных программ.
"""

from typing import Dict, List, Optional, Any
from .self_care_7_days import SELF_CARE_7_DAYS, get_day_task, get_morning_message, get_evening_question, get_completion_message


# Каталог всех программ
PROGRAMS_CATALOG: Dict[str, Dict[str, Any]] = {
    "7_days_self_care": SELF_CARE_7_DAYS,
}


def get_program(program_id: str) -> Optional[Dict[str, Any]]:
    """Получает информацию о программе по ID."""
    return PROGRAMS_CATALOG.get(program_id)


def get_all_programs() -> List[Dict[str, Any]]:
    """Получает список всех программ."""
    return list(PROGRAMS_CATALOG.values())


def get_program_task(program_id: str, day: int) -> Optional[Any]:
    """
    Получает задание на конкретный день программы.

    Args:
        program_id: ID программы
        day: Номер дня

    Returns:
        Объект DayTask или None
    """
    if program_id == "7_days_self_care":
        return get_day_task(day)
    return None


def get_program_morning_message(program_id: str, day: int) -> Optional[str]:
    """
    Получает утреннее сообщение для дня программы.

    Args:
        program_id: ID программы
        day: Номер дня

    Returns:
        Текст утреннего сообщения или None
    """
    if program_id == "7_days_self_care":
        return get_morning_message(day)
    return None


def get_program_evening_question(program_id: str, day: int) -> Optional[str]:
    """
    Получает вечерний вопрос для дня программы.

    Args:
        program_id: ID программы
        day: Номер дня

    Returns:
        Текст вечернего вопроса или None
    """
    if program_id == "7_days_self_care":
        return get_evening_question(day)
    return None


def get_program_completion_message(program_id: str) -> Optional[str]:
    """
    Получает сообщение о завершении программы.

    Args:
        program_id: ID программы

    Returns:
        Текст поздравления или None
    """
    if program_id == "7_days_self_care":
        return get_completion_message()
    return None


def format_program_info(program: Dict[str, Any]) -> str:
    """
    Форматирует информацию о программе для отображения.

    Args:
        program: Словарь с информацией о программе

    Returns:
        Отформатированный текст
    """
    emoji = program.get("emoji", "📚")
    name = program.get("name", "Программа")
    description = program.get("description", "")
    total_days = program.get("total_days", 0)
    for_whom = program.get("for_whom", "")
    what_gives = program.get("what_gives", [])

    parts = [
        f"{emoji} **{name}**",
        f"_{description}_",
        "",
        f"📅 Длительность: {total_days} дней",
        "",
    ]

    if for_whom:
        parts.append(f"👤 {for_whom}")
        parts.append("")

    if what_gives:
        parts.append("✨ Что даёт программа:")
        for item in what_gives:
            parts.append(f"• {item}")

    return "\n".join(parts)


def format_programs_list() -> str:
    """
    Форматирует список всех программ.

    Returns:
        Отформатированный текст со списком программ
    """
    parts = ["📚 **Доступные программы:**\n"]

    for program in PROGRAMS_CATALOG.values():
        emoji = program.get("emoji", "📚")
        name = program.get("name", "Программа")
        days = program.get("total_days", 0)
        desc = program.get("description", "")[:80] + "..." if len(program.get("description", "")) > 80 else program.get("description", "")

        parts.append(f"\n{emoji} **{name}** ({days} дней)")
        parts.append(f"_{desc}_")

    parts.append("\n\nВыбери программу, чтобы узнать больше!")

    return "\n".join(parts)
