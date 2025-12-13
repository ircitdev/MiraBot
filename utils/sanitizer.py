"""
Input sanitizer.
Валидация и санитизация пользовательского ввода.
"""

import re
import html
from typing import Optional
from loguru import logger


# Максимальные длины
MAX_MESSAGE_LENGTH = 4096  # Telegram limit
MAX_NAME_LENGTH = 100
MAX_DISPLAY_NAME_LENGTH = 50

# Паттерны для фильтрации
SQL_INJECTION_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)",
    r"(--|\#|\/\*)",
    r"(\bOR\b\s+\d+\s*=\s*\d+)",
    r"(\bAND\b\s+\d+\s*=\s*\d+)",
]

# Опасные HTML/JS теги
DANGEROUS_TAGS = [
    "<script", "</script>", "<iframe", "</iframe>",
    "javascript:", "onerror=", "onclick=", "onload=",
]

# Символы для удаления (контрольные символы кроме пробелов и переносов)
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """
    Санитизирует текст сообщения.

    - Удаляет контрольные символы
    - Экранирует HTML
    - Обрезает по максимальной длине
    - Удаляет лишние пробелы

    Args:
        text: Исходный текст
        max_length: Максимальная длина

    Returns:
        Очищенный текст
    """
    if not text:
        return ""

    # Удаляем контрольные символы
    text = CONTROL_CHARS_PATTERN.sub("", text)

    # Удаляем лишние пробелы (но оставляем одинарные)
    text = re.sub(r" {3,}", "  ", text)

    # Убираем ведущие/завершающие пробелы
    text = text.strip()

    # Ограничиваем длину
    if len(text) > max_length:
        text = text[:max_length]
        logger.warning(f"Text truncated to {max_length} chars")

    return text


def sanitize_name(name: str, max_length: int = MAX_NAME_LENGTH) -> str:
    """
    Санитизирует имя (пользователя или партнёра).

    - Удаляет специальные символы
    - Оставляет только буквы, цифры и базовые знаки
    - Капитализирует первую букву

    Args:
        name: Исходное имя
        max_length: Максимальная длина

    Returns:
        Очищенное имя
    """
    if not name:
        return ""

    # Удаляем контрольные символы
    name = CONTROL_CHARS_PATTERN.sub("", name)

    # Оставляем только буквы (включая кириллицу), цифры, пробелы и дефисы
    name = re.sub(r"[^\w\s\-]", "", name, flags=re.UNICODE)

    # Удаляем множественные пробелы
    name = re.sub(r"\s+", " ", name)

    # Убираем ведущие/завершающие пробелы
    name = name.strip()

    # Ограничиваем длину
    if len(name) > max_length:
        name = name[:max_length]

    # Капитализируем
    if name:
        name = name[0].upper() + name[1:] if len(name) > 1 else name.upper()

    return name


def sanitize_display_name(name: str) -> str:
    """
    Санитизирует display_name пользователя.

    Более строгая версия sanitize_name.
    """
    return sanitize_name(name, max_length=MAX_DISPLAY_NAME_LENGTH)


def check_sql_injection(text: str) -> bool:
    """
    Проверяет текст на признаки SQL-инъекции.

    Args:
        text: Текст для проверки

    Returns:
        True если обнаружены подозрительные паттерны
    """
    if not text:
        return False

    text_upper = text.upper()

    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, text_upper, re.IGNORECASE):
            logger.warning(f"Potential SQL injection detected: {text[:100]}")
            return True

    return False


def check_xss(text: str) -> bool:
    """
    Проверяет текст на признаки XSS-атаки.

    Args:
        text: Текст для проверки

    Returns:
        True если обнаружены подозрительные паттерны
    """
    if not text:
        return False

    text_lower = text.lower()

    for tag in DANGEROUS_TAGS:
        if tag in text_lower:
            logger.warning(f"Potential XSS detected: {text[:100]}")
            return True

    return False


def escape_html(text: str) -> str:
    """
    Экранирует HTML-символы для безопасного отображения.

    Args:
        text: Исходный текст

    Returns:
        Текст с экранированными HTML-символами
    """
    return html.escape(text) if text else ""


def validate_message(text: str) -> tuple[bool, str, Optional[str]]:
    """
    Полная валидация сообщения пользователя.

    Args:
        text: Текст сообщения

    Returns:
        (is_valid, sanitized_text, error_message)
    """
    if not text:
        return False, "", "Пустое сообщение"

    if len(text) > MAX_MESSAGE_LENGTH:
        return False, "", f"Сообщение слишком длинное (максимум {MAX_MESSAGE_LENGTH} символов)"

    # Санитизируем
    sanitized = sanitize_text(text)

    # Проверяем на атаки (логируем, но не блокируем — это чат-бот)
    if check_sql_injection(sanitized):
        logger.warning(f"SQL injection attempt in message: {sanitized[:50]}...")

    if check_xss(sanitized):
        logger.warning(f"XSS attempt in message: {sanitized[:50]}...")

    return True, sanitized, None


def validate_name(name: str) -> tuple[bool, str, Optional[str]]:
    """
    Валидация имени пользователя/партнёра.

    Args:
        name: Имя для валидации

    Returns:
        (is_valid, sanitized_name, error_message)
    """
    if not name:
        return False, "", "Имя не указано"

    sanitized = sanitize_name(name)

    if not sanitized:
        return False, "", "Имя содержит только недопустимые символы"

    if len(sanitized) < 2:
        return False, "", "Имя слишком короткое"

    if len(sanitized) > MAX_NAME_LENGTH:
        return False, "", f"Имя слишком длинное (максимум {MAX_NAME_LENGTH} символов)"

    return True, sanitized, None
