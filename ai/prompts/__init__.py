"""
Prompts package.
Системные промпты и шаблоны для Claude.
"""

from ai.prompts.system_prompt import build_system_prompt
from ai.prompts.rituals import get_ritual_prompt, MORNING_CHECKIN_PROMPTS, EVENING_CHECKIN_PROMPTS

__all__ = [
    "build_system_prompt",
    "get_ritual_prompt",
    "MORNING_CHECKIN_PROMPTS",
    "EVENING_CHECKIN_PROMPTS",
]
