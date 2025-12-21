"""
Programs Module.
Структурированные программы и курсы для пользователей.
"""

from .catalog import PROGRAMS_CATALOG, get_program, get_all_programs
from .self_care_7_days import SELF_CARE_7_DAYS

__all__ = [
    "PROGRAMS_CATALOG",
    "get_program",
    "get_all_programs",
    "SELF_CARE_7_DAYS",
]
