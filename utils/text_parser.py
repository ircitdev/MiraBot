"""
Утилиты для парсинга текста пользователя.
"""

import re
from typing import Optional


def extract_name_from_text(text: str) -> Optional[str]:
    """
    Извлекает имя из текста пользователя.

    Обрабатывает случаи:
    - "Называй меня Ниночка" -> "Ниночка"
    - "Зови меня Аня" -> "Аня"
    - "Можешь звать Маша" -> "Маша"
    - "Я Катя" -> "Катя"
    - "Меня зовут Оля" -> "Оля"
    - "Ниночка" -> "Ниночка"
    - "Забыла?" -> None (вопрос, не имя)
    """
    text = text.strip()

    # Проверяем, что это не вопрос или команда
    if text.endswith("?") or text.startswith("/"):
        return None

    # Паттерны для извлечения имени из фраз
    patterns = [
        r"(?:называй|зови|обращайся)\s+(?:ко\s+)?(?:мне\s+)?(?:меня\s+)?(?:как\s+)?([а-яёА-ЯЁa-zA-Z]+)",
        r"(?:можешь\s+)?(?:называть|звать)\s+(?:меня\s+)?([а-яёА-ЯЁa-zA-Z]+)",
        r"(?:меня\s+)?зовут\s+([а-яёА-ЯЁa-zA-Z]+)",
        r"^я\s+([а-яёА-ЯЁa-zA-Z]+)$",
        r"^(?:это\s+)?([а-яёА-ЯЁa-zA-Z]+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip().capitalize()
            # Проверяем, что это похоже на имя (не слишком короткое/длинное)
            if 2 <= len(name) <= 20:
                return name

    # Если нет паттернов, берём первое слово (если оно похоже на имя)
    words = text.split()
    if words:
        first_word = words[0].strip().capitalize()
        # Исключаем служебные слова
        skip_words = {
            "привет", "здравствуй", "добрый", "доброе", "как", "что",
            "да", "нет", "ок", "окей", "хорошо", "ладно", "спасибо",
            "называй", "зови", "можешь", "пожалуйста", "меня",
        }
        if first_word.lower() not in skip_words and 2 <= len(first_word) <= 20:
            # Проверяем, что это не очевидно не имя
            if re.match(r"^[а-яёА-ЯЁa-zA-Z]+$", first_word):
                return first_word

    return None


def extract_partner_info(text: str) -> dict:
    """
    Извлекает информацию о партнёре из текста.

    Возвращает:
    {
        "name": "Саша" или None,
        "gender": "male" / "female" / None
    }
    """
    result = {"name": None, "gender": None}
    text_lower = text.lower()

    # Паттерны для имени партнёра
    partner_patterns = [
        r"(?:муж|мужа|супруг|супруга)\s+(?:зовут\s+)?([а-яёА-ЯЁa-zA-Z]+)",
        r"(?:партнёр|партнер|партнёра|партнера)\s+(?:зовут\s+)?([а-яёА-ЯЁa-zA-Z]+)",
        r"(?:его|её|ее)\s+зовут\s+([а-яёА-ЯЁa-zA-Z]+)",
    ]

    for pattern in partner_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["name"] = match.group(1).strip().capitalize()
            break

    # Определяем пол партнёра
    male_indicators = [
        "муж", "мужа", "мужем", "он ", " он", "его ", "парень",
        "мальчик", "супруг", "партнёр", "партнер"
    ]
    female_indicators = [
        "жена", "жены", "женой", "она ", " она", "её ", "ее ",
        "девушка", "девочка", "супруга", "партнёрша"
    ]

    male_count = sum(1 for indicator in male_indicators if indicator in text_lower)
    female_count = sum(1 for indicator in female_indicators if indicator in text_lower)

    # Проверяем явные указания пола
    if "мальчик" in text_lower and ("а не девочка" in text_lower or "не девочка" in text_lower):
        result["gender"] = "male"
    elif "девочка" in text_lower and ("а не мальчик" in text_lower or "не мальчик" in text_lower):
        result["gender"] = "female"
    elif male_count > female_count:
        result["gender"] = "male"
    elif female_count > male_count:
        result["gender"] = "female"

    return result
