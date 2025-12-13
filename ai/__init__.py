"""
AI package.
Работа с Claude API и генерация ответов.
"""

from ai.claude_client import ClaudeClient
from ai.crisis_detector import CrisisDetector

__all__ = [
    "ClaudeClient",
    "CrisisDetector",
]
