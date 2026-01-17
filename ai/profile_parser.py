"""
AI-based Profile Data Parser.
Извлечение структурированных данных профиля из свободного текста пользователя.
"""

import json
from typing import Dict, Any, Optional
from loguru import logger

from ai.claude_client import claude_client


PROFILE_EXTRACTION_PROMPT = """
Ты - AI-ассистент для извлечения структурированных данных из текста.

Пользователь ответил на вопрос: "Расскажи немного о себе: сколько тебе лет, из какого города и чем занимаешься?"

Твоя задача: извлечь следующие данные из ответа пользователя и вернуть их в формате JSON:

{
  "age": int или null,          // Возраст (число)
  "city": str или null,         // Город проживания
  "job": str или null,          // Профессия или род занятий
  "hobby": str или null         // Хобби или увлечения
}

ПРАВИЛА ИЗВЛЕЧЕНИЯ:

1. **Возраст (age):**
   - Извлекай только ЯВНО указанный возраст (число)
   - Примеры: "Мне 34" → 34, "34 года" → 34
   - Если возраст НЕ указан → null

2. **Город (city):**
   - Извлекай название города или страны
   - Примеры: "из Москвы" → "Москва", "живу в Питере" → "Санкт-Петербург"
   - Нормализуй: "Питер" → "Санкт-Петербург", "Спб" → "Санкт-Петербург"
   - Если город НЕ указан → null

3. **Работа (job):**
   - Извлекай профессию, должность или род занятий
   - Примеры: "работаю маркетологом" → "маркетолог", "я учитель" → "учитель"
   - "домохозяйка", "мама в декрете", "не работаю" - тоже валидные значения
   - Если работа НЕ указана → null

4. **Хобби (hobby):**
   - Извлекай увлечения, интересы, хобби
   - Примеры: "люблю йогу" → "йога", "читаю книги" → "чтение"
   - Можно несколько через запятую: "йога, чтение, путешествия"
   - Если хобби НЕ указано → null

ВАЖНО:
- Заполняй ТОЛЬКО то, что пользователь ЯВНО упомянул
- НЕ придумывай и НЕ предполагай данные
- Если какие-то поля отсутствуют → null
- Верни ТОЛЬКО валидный JSON, без дополнительного текста

ПРИМЕРЫ:

Ввод: "Мне 34, живу в Москве, работаю маркетологом, люблю йогу"
Вывод: {"age": 34, "city": "Москва", "job": "маркетолог", "hobby": "йога"}

Ввод: "34 года, из Питера, маркетолог"
Вывод: {"age": 34, "city": "Санкт-Петербург", "job": "маркетолог", "hobby": null}

Ввод: "Живу в Москве, работаю в IT, в свободное время рисую"
Вывод: {"age": null, "city": "Москва", "job": "IT-специалист", "hobby": "рисование"}

Ввод: "Мне 28, мама двоих детей, сижу дома"
Вывод: {"age": 28, "city": null, "job": "домохозяйка", "hobby": null}

Ввод: "Работаю дизайнером в Екатеринбурге"
Вывод: {"age": null, "city": "Екатеринбург", "job": "дизайнер", "hobby": null}

ТЕПЕРЬ ИЗВЛЕКИ ДАННЫЕ ИЗ ЭТОГО ОТВЕТА:

"{user_input}"

Верни ТОЛЬКО JSON, без дополнительного текста.
"""


async def parse_social_portrait(user_input: str) -> Dict[str, Any]:
    """
    Извлекает структурированные данные профиля из свободного текста.

    Args:
        user_input: Свободный ответ пользователя на вопрос о себе

    Returns:
        Словарь с извлечёнными данными:
        {
            "age": int | None,
            "city": str | None,
            "job": str | None,
            "hobby": str | None,
        }
    """
    try:
        # Формируем промпт для Claude
        prompt = PROFILE_EXTRACTION_PROMPT.format(user_input=user_input)

        # Вызываем Claude API
        response = await claude_client.send_message(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are a precise data extraction assistant. Return only valid JSON.",
            max_tokens=500,
        )

        # Парсим JSON из ответа
        # Claude может обернуть JSON в ```json ... ```, убираем это
        content = response.strip()

        # Убираем markdown code blocks если есть
        if content.startswith("```json"):
            content = content[7:]  # Убираем ```json
        if content.startswith("```"):
            content = content[3:]  # Убираем ```
        if content.endswith("```"):
            content = content[:-3]  # Убираем ```

        content = content.strip()

        # Парсим JSON
        parsed_data = json.loads(content)

        # Валидация структуры
        result = {
            "age": parsed_data.get("age"),
            "city": parsed_data.get("city"),
            "job": parsed_data.get("job"),
            "hobby": parsed_data.get("hobby"),
        }

        logger.info(f"Profile parsed successfully: {result}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Claude response: {e}")
        logger.error(f"Claude response: {response}")
        # Возвращаем пустой результат
        return {"age": None, "city": None, "job": None, "hobby": None}

    except Exception as e:
        logger.error(f"Error during profile parsing: {e}")
        return {"age": None, "city": None, "job": None, "hobby": None}


async def parse_family_details(user_input: str) -> Dict[str, Any]:
    """
    Извлекает данные о семье из свободного текста.

    Args:
        user_input: Свободный ответ пользователя о партнёре и детях

    Returns:
        Словарь с извлечёнными данными:
        {
            "partner_name": str | None,
            "partner_job": str | None,
            "children": List[Dict] | None,  // [{"age": int, "gender": str, "hobby": str}]
            "pets": str | None,
        }
    """
    family_extraction_prompt = f"""
Извлеки данные о семье из ответа пользователя.

Верни JSON в формате:
{{
  "partner_name": str или null,       // Имя партнёра/мужа
  "partner_job": str или null,        // Работа партнёра
  "children": [                       // Массив детей
    {{"age": int, "gender": str, "name": str или null, "hobby": str или null}}
  ] или null,
  "pets": str или null                // Питомцы
}}

ПРАВИЛА:
- gender: "мальчик", "девочка" или null
- Если детей несколько - верни массив
- Если детей нет или не упомянуты - верни null

ПРИМЕРЫ:

Ввод: "Муж Андрей, работает программистом. Сын 5 лет, обожает лего"
Вывод: {{"partner_name": "Андрей", "partner_job": "программист", "children": [{{"age": 5, "gender": "мальчик", "name": null, "hobby": "лего"}}], "pets": null}}

Ввод: "У меня двое детей - Маша 7 лет и Петя 3 года"
Вывод: {{"partner_name": null, "partner_job": null, "children": [{{"age": 7, "gender": "девочка", "name": "Маша", "hobby": null}}, {{"age": 3, "gender": "мальчик", "name": "Петя", "hobby": null}}], "pets": null}}

ОТВЕТ ПОЛЬЗОВАТЕЛЯ:
"{user_input}"

Верни ТОЛЬКО JSON.
"""

    try:
        response = await claude_client.send_message(
            messages=[{"role": "user", "content": family_extraction_prompt}],
            system_prompt="You are a precise data extraction assistant. Return only valid JSON.",
            max_tokens=500,
        )

        # Убираем markdown code blocks
        content = response.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        parsed_data = json.loads(content)

        result = {
            "partner_name": parsed_data.get("partner_name"),
            "partner_job": parsed_data.get("partner_job"),
            "children": parsed_data.get("children"),
            "pets": parsed_data.get("pets"),
        }

        logger.info(f"Family details parsed successfully: {result}")
        return result

    except Exception as e:
        logger.error(f"Error during family parsing: {e}")
        return {"partner_name": None, "partner_job": None, "children": None, "pets": None}
