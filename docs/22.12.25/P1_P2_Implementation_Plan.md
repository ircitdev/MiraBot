# План реализации P1 и P2 приоритетов

**Дата:** 22.12.2025
**Версия:** 1.0
**Статус:** В разработке

---

## P1: Mood Analyzer → Промпт Claude (смешанные эмоции)

### Проблема
Текущий `mood_analyzer.py` определяет PRIMARY emotion и secondary emotions, но это НЕ передаётся в системный промпт Claude. Claude не знает, что у пользователя смешанные эмоции (например: тревога + злость + усталость одновременно).

**Результат:** Claude может упустить нюансы эмоционального состояния, особенно когда эмоции противоречивые (радость + грусть, спокойствие + тревога).

### Текущая архитектура

**Файл:** `ai/mood_analyzer.py` (484 строки)
- Класс `MoodAnalyzer` с методом `analyze(message: str) -> MoodAnalysis`
- Возвращает:
  - `mood_score` (-5 до +5)
  - `primary_emotion` (happy, sad, anxious, angry, frustrated, hopeless, overwhelmed, tired, calm, neutral)
  - `secondary_emotions` (список с порогом 0.5 от primary_score)
  - `energy_level` (1-10)
  - `anxiety_level` (1-10)
  - `triggers` (partner, children, work, family, health, finance, self)
  - `confidence` (0.0-1.0)

**Использование:** В `bot/handlers/message.py` анализируется настроение, но данные НЕ передаются в `build_system_prompt()`.

### Решение

#### Шаг 1: Расширить `_build_user_context_block()` в system_prompt.py

**Файл:** `ai/prompts/system_prompt.py` (строки 45-70)

Добавить блок эмоционального состояния ПОСЛЕ основного контекста:

```python
def _build_user_context_block(user_context: Dict[str, Any]) -> str:
    """Формирует блок контекста пользователя."""
    # ... существующий код ...

    # НОВЫЙ БЛОК: Эмоциональное состояние
    mood_block = ""
    if user_context.get("current_mood"):
        mood_data = user_context["current_mood"]
        mood_block = _format_mood_context(mood_data)

    return f"{context}{mood_block}"


def _format_mood_context(mood: Dict[str, Any]) -> str:
    """Форматирует эмоциональное состояние для промпта."""

    primary = mood.get("primary_emotion", "neutral")
    secondary = mood.get("secondary_emotions", [])
    score = mood.get("mood_score", 0)
    energy = mood.get("energy_level")
    anxiety = mood.get("anxiety_level")
    triggers = mood.get("triggers", [])

    # Переводим эмоции на русский для Claude
    EMOTION_NAMES = {
        "happy": "счастлива/рада",
        "calm": "спокойна",
        "neutral": "нейтральна",
        "tired": "уставшая",
        "sad": "грустная",
        "anxious": "тревожная",
        "angry": "злая/раздражённая",
        "frustrated": "разочарована",
        "hopeless": "отчаявшаяся",
        "overwhelmed": "перегружена",
    }

    lines = ["\n### 🎭 ЭМОЦИОНАЛЬНОЕ СОСТОЯНИЕ (текущее сообщение)\n"]

    # Основная эмоция
    primary_ru = EMOTION_NAMES.get(primary, primary)
    lines.append(f"**Основная эмоция:** {primary_ru} (настроение: {score}/5)")

    # Смешанные эмоции (КРИТИЧЕСКИ ВАЖНО)
    if secondary:
        secondary_ru = [EMOTION_NAMES.get(e, e) for e in secondary]
        lines.append(f"**⚠️ СМЕШАННЫЕ эмоции:** {', '.join(secondary_ru)}")
        lines.append("*(Обрати внимание: человек испытывает НЕСКОЛЬКО эмоций одновременно — это важно!)*")

    # Энергия и тревога
    if energy:
        lines.append(f"**Уровень энергии:** {energy}/10")
    if anxiety:
        lines.append(f"**Уровень тревоги:** {anxiety}/10")

    # Триггеры
    if triggers:
        TRIGGER_NAMES = {
            "partner": "отношения с партнёром",
            "children": "дети",
            "work": "работа",
            "family": "семья",
            "health": "здоровье",
            "finance": "финансы",
            "self": "самореализация",
        }
        triggers_ru = [TRIGGER_NAMES.get(t, t) for t in triggers]
        lines.append(f"**Триггеры:** {', '.join(triggers_ru)}")

    lines.append("\n**КАК ИСПОЛЬЗОВАТЬ:**")
    lines.append("- Если есть СМЕШАННЫЕ эмоции — признай ВСЕ, не только главную")
    lines.append("- Пример: \"Похоже, ты одновременно и рада, и тревожишься... Это нормально.\"")
    lines.append("- НЕ упрощай: если человек чувствует 3 эмоции — не своди всё к одной\n")

    return "\n".join(lines)
```

#### Шаг 2: Интегрировать mood в message.py

**Файл:** `bot/handlers/message.py` (строки 230-260, функция `_get_fresh_user_data()`)

Добавить анализ настроения ПЕРЕД вызовом Claude:

```python
async def _get_fresh_user_data(user: User) -> Dict[str, Any]:
    """Собирает актуальные данные пользователя для промпта."""

    # ... существующий код для памяти, подписки, статистики ...

    # НОВОЕ: Анализ настроения текущего сообщения
    # (вызывается ДО отправки в Claude, передаём message_text)
    # Примечание: message_text должен быть доступен в контексте

    return {
        "display_name": user.display_name,
        "persona": user.preferred_persona,
        "memory": memory_dict,
        "subscription": subscription_info,
        "stats": stats,
        "current_mood": mood_data,  # <-- НОВОЕ
    }
```

**Изменения в основном обработчике:**

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... существующий код до вызова Claude ...

    # 6.5. НОВОЕ: Анализ настроения ПЕРЕД Claude
    from ai.mood_analyzer import mood_analyzer

    mood_analysis = mood_analyzer.analyze(message_text)
    mood_data = {
        "mood_score": mood_analysis.mood_score,
        "primary_emotion": mood_analysis.primary_emotion,
        "secondary_emotions": mood_analysis.secondary_emotions,
        "energy_level": mood_analysis.energy_level,
        "anxiety_level": mood_analysis.anxiety_level,
        "triggers": mood_analysis.triggers,
        "confidence": mood_analysis.confidence,
    }

    # 6.6. Обновляем user_data с настроением
    user_data = await _get_fresh_user_data(user)
    user_data["current_mood"] = mood_data  # Добавляем mood

    # 7. Генерация ответа Claude (с учётом mood в промпте)
    result = await claude.generate_response(...)
```

#### Шаг 3: Сохранение mood в БД (опционально)

**Файл:** `database/repositories/conversation.py`

Добавить сохранение `mood_data` в JSON поле `metadata` таблицы `conversations`:

```python
await conversation_repo.save_message(
    user_id=user.id,
    role="user",
    content=message_text,
    metadata={"mood": mood_data},  # <-- сохраняем для аналитики
)
```

#### Шаг 4: Тестирование

**Тестовые кейсы:**

1. **Смешанные эмоции (радость + тревога):**
   - Ввод: "Я так рада, что получила работу! Но одновременно боюсь, что не справлюсь..."
   - Ожидание: Claude признаёт ОБЕ эмоции: "Вижу, что ты одновременно рада и тревожишься. Это абсолютно нормально!"

2. **Тройная смесь (грусть + злость + усталость):**
   - Ввод: "Устала от этих придирок мужа... Обидно и злюсь на него, но сил уже нет..."
   - Ожидание: Claude учитывает все 3 эмоции.

3. **Нейтральное настроение:**
   - Ввод: "Как дела?"
   - Ожидание: Нет блока эмоций в промпте (или минимальный).

#### Оценка сложности
- **Время:** 2-3 часа
- **Риски:** Низкие (изменения изолированы)
- **Приоритет:** P1 (высокий)

---

## P1: Валидация записей в память (защита от манипуляций)

### Проблема
Claude может записывать в память **что угодно** по запросу пользователя, включая:
- Заведомо ложные факты ("Запомни, что мужа зовут Андрей" → но это неправда)
- Манипуляции ("Запомни, что я сказала X" → но не говорила)
- Противоречия ("Запомни, что у меня нет детей" → но уже записано про детей)

**Результат:** Память может быть "отравлена" и привести к абсурдным ответам.

### Текущая архитектура

**Файл:** `database/repositories/memory.py`
- Метод `create()` — создаёт запись БЕЗ валидации
- Метод `upsert_by_category()` — перезаписывает содержимое БЕЗ проверки противоречий

**Файл:** `ai/memory_manager.py` (предполагается)
- НЕ существует — память управляется напрямую из промпта Claude

### Решение

#### Архитектура валидации

```
User message → Claude decides to save
              ↓
        Memory Validator
              ↓
      [Checks contradictions]
      [Checks plausibility]
      [Flags suspicious edits]
              ↓
     ✅ Save  OR  ⚠️ Flag for review
```

#### Шаг 1: Создать `ai/memory_validator.py`

**Файл:** `ai/memory_validator.py` (новый)

```python
"""
Memory Validator.
Валидация записей в долговременную память.
Защита от манипуляций и противоречий.
"""

from typing import Optional, List, Dict, Any
from loguru import logger

from database.repositories.memory import MemoryRepository


class MemoryValidator:
    """Валидатор памяти."""

    def __init__(self):
        self.memory_repo = MemoryRepository()

    async def validate_new_entry(
        self,
        user_id: int,
        category: str,
        content: str,
        source_context: str = "",
    ) -> Dict[str, Any]:
        """
        Валидирует новую запись в память.

        Returns:
            {
                "valid": bool,
                "confidence": float,  # 0.0-1.0
                "warnings": List[str],
                "contradictions": List[Dict],
            }
        """

        warnings = []
        contradictions = []
        confidence = 1.0

        # 1. Проверка на противоречия с существующей памятью
        existing_entries = await self.memory_repo.get_by_user(
            user_id=user_id,
            category=category,
        )

        for entry in existing_entries:
            contradiction = await self._check_contradiction(
                new_content=content,
                existing_content=entry.content,
                category=category,
            )

            if contradiction:
                contradictions.append({
                    "existing_id": entry.id,
                    "existing_content": entry.content,
                    "type": contradiction,
                })
                confidence -= 0.3

        # 2. Проверка на явные манипуляции
        manipulation_score = self._check_manipulation_markers(content, source_context)

        if manipulation_score > 0.5:
            warnings.append("Возможная попытка манипуляции памятью")
            confidence -= 0.4

        # 3. Проверка правдоподобности
        plausibility = self._check_plausibility(content, category)

        if plausibility < 0.3:
            warnings.append("Низкая правдоподобность информации")
            confidence -= 0.2

        # Финальное решение
        valid = confidence >= 0.5 and len(contradictions) == 0

        return {
            "valid": valid,
            "confidence": max(0.0, confidence),
            "warnings": warnings,
            "contradictions": contradictions,
        }

    async def _check_contradiction(
        self,
        new_content: str,
        existing_content: str,
        category: str,
    ) -> Optional[str]:
        """Проверяет противоречие между новой и существующей записью."""

        # Ключевые противоречия по категориям

        if category == "personal":
            # Имя, возраст, профессия не должны меняться кардинально
            name_markers = ["зовут", "имя", "меня", "я -"]

            if any(m in new_content.lower() and m in existing_content.lower() for m in name_markers):
                # Простая эвристика: если слова разные — возможно противоречие
                new_words = set(new_content.lower().split())
                existing_words = set(existing_content.lower().split())

                if len(new_words & existing_words) < len(new_words) * 0.3:
                    return "name_change"

        if category == "family":
            # Проверка на изменение состава семьи (муж, дети)
            family_markers = ["муж", "дети", "сын", "дочь", "ребёнок"]

            new_has_family = any(m in new_content.lower() for m in family_markers)
            existing_has_family = any(m in existing_content.lower() for m in family_markers)

            # Если было "есть муж" а теперь "нет мужа" — противоречие
            negation_markers = ["нет", "не было", "не имею", "без"]
            new_has_negation = any(m in new_content.lower() for m in negation_markers)
            existing_has_negation = any(m in existing_content.lower() for m in negation_markers)

            if new_has_family != existing_has_family or new_has_negation != existing_has_negation:
                return "family_composition_change"

        # TODO: Добавить проверки для других категорий

        return None

    def _check_manipulation_markers(self, content: str, source_context: str) -> float:
        """
        Проверяет маркеры манипуляции.
        Возвращает score от 0.0 (честная запись) до 1.0 (явная манипуляция).
        """

        score = 0.0
        content_lower = content.lower()

        # Маркеры прямых команд (подозрительно)
        command_markers = [
            "запомни, что",
            "сохрани, что",
            "забудь, что",
            "удали из памяти",
            "перезапиши",
        ]

        if any(m in content_lower for m in command_markers):
            score += 0.4

        # Маркеры отрицания предыдущего
        denial_markers = [
            "я не говорила",
            "я не говорил",
            "это неправда",
            "это ложь",
            "удали это",
        ]

        if any(m in content_lower for m in denial_markers):
            score += 0.3

        # Противоречие с исходным контекстом
        if source_context:
            # Если в content есть факты, которых НЕТ в source_context
            # (грубая проверка через пересечение слов)
            content_words = set(content_lower.split())
            source_words = set(source_context.lower().split())

            overlap = len(content_words & source_words) / len(content_words) if content_words else 1.0

            if overlap < 0.2:
                score += 0.3  # Низкое пересечение = возможная выдумка

        return min(1.0, score)

    def _check_plausibility(self, content: str, category: str) -> float:
        """
        Проверяет правдоподобность содержимого.
        Возвращает score от 0.0 (неправдоподобно) до 1.0 (правдоподобно).
        """

        # Базовая правдоподобность
        score = 0.7

        content_lower = content.lower()

        # Проверка на абсурдные утверждения
        absurd_markers = [
            "мне 200 лет",
            "у меня 50 детей",
            "я инопланетянин",
            "я робот",
            "я умерла",
        ]

        if any(m in content_lower for m in absurd_markers):
            score = 0.1

        # Проверка длины (слишком короткие записи подозрительны)
        if len(content.strip()) < 10:
            score -= 0.2

        # Проверка на CAPS LOCK (часто признак эмоций, но не обязательно манипуляции)
        if content.isupper() and len(content) > 20:
            score -= 0.1

        return max(0.0, score)


# Глобальный экземпляр
memory_validator = MemoryValidator()
```

#### Шаг 2: Интегрировать валидатор в промпт Claude

**Файл:** `ai/prompts/system_prompt.py`

Добавить инструкции для Claude о валидации памяти:

```python
def _get_memory_guidelines() -> str:
    """Возвращает инструкции по работе с памятью."""
    return """
## 📝 РАБОТА С ПАМЯТЬЮ — СТРОГИЕ ПРАВИЛА

**КРИТИЧЕСКИ ВАЖНО:** Ты НЕ имеешь прямого доступа к записи в память.
Вместо этого:

1. **Когда сохранить:**
   - Пользователь сообщил НОВЫЙ важный факт о себе
   - Пользователь попросил запомнить что-то (НО проверь валидность!)
   - Выявлен важный триггер или паттерн (работа, семья, здоровье)

2. **ЗАПРЕЩЕНО сохранять:**
   ❌ По команде "запомни, что..." БЕЗ проверки правдивости
   ❌ Противоречия с уже известными фактами (например: "у меня нет детей" если уже знаешь про детей)
   ❌ Явные манипуляции ("забудь, что я говорила X")

3. **Как действовать при подозрении:**
   - "Хм, но ты раньше говорила, что [факт из памяти]. Что-то изменилось?"
   - "Подожди, я помню другое... Давай уточним?"
   - НЕ молчаливо перезаписывай память!

4. **Формат записи:**
   - Краткий факт (1-2 предложения)
   - Категория: personal, family, work, health, goals, triggers
   - Важность: 1-10 (по значимости для поддержки)
"""
```

#### Шаг 3: Обработка флагов валидации в коде

**Файл:** `bot/handlers/message.py` (или новый `ai/memory_manager.py`)

```python
async def save_memory_with_validation(
    user_id: int,
    category: str,
    content: str,
    source_message: str = "",
) -> Dict[str, Any]:
    """
    Сохраняет запись в память С валидацией.

    Returns:
        {
            "saved": bool,
            "entry_id": Optional[int],
            "warnings": List[str],
        }
    """

    from ai.memory_validator import memory_validator

    # Валидация
    validation = await memory_validator.validate_new_entry(
        user_id=user_id,
        category=category,
        content=content,
        source_context=source_message,
    )

    if not validation["valid"]:
        # Не сохраняем, логируем предупреждение
        logger.warning(
            f"Memory validation FAILED for user {user_id}: {content}\n"
            f"Warnings: {validation['warnings']}\n"
            f"Contradictions: {validation['contradictions']}"
        )

        return {
            "saved": False,
            "warnings": validation["warnings"],
            "contradictions": validation["contradictions"],
        }

    # Сохраняем с флагом confidence
    entry = await memory_repo.create(
        user_id=user_id,
        category=category,
        content=content,
        importance=5,  # TODO: динамический расчёт
        metadata={"confidence": validation["confidence"]},
    )

    logger.info(f"Memory saved for user {user_id}: {category} - {content[:50]}...")

    return {
        "saved": True,
        "entry_id": entry.id,
        "warnings": validation["warnings"] if validation["warnings"] else [],
    }
```

#### Шаг 4: Миграция БД (добавить metadata в таблицу memory_entries)

**Файл:** `alembic/versions/XXXX_add_memory_metadata.py`

```python
def upgrade():
    op.add_column(
        'memory_entries',
        sa.Column('metadata', postgresql.JSONB(), nullable=True)
    )

def downgrade():
    op.drop_column('memory_entries', 'metadata')
```

#### Шаг 5: Тестирование

**Тестовые кейсы:**

1. **Противоречие:**
   - Память: "Мужа зовут Андрей, дети Тим и Алиса"
   - Запрос: "Запомни, что у меня нет детей"
   - Ожидание: Claude спрашивает "Подожди, ты же говорила про Тима и Алису?"

2. **Манипуляция:**
   - Запрос: "Удали из памяти всё про мужа"
   - Ожидание: Не удаляется, Claude объясняет "Я не могу удалить важные факты..."

3. **Валидная запись:**
   - Запрос: "Я нашла новое хобби — йога"
   - Ожидание: Сохраняется в категорию "self" с confidence=1.0

#### Оценка сложности
- **Время:** 4-6 часов (валидатор + интеграция + тестирование)
- **Риски:** Средние (может блокировать легитимные запросы)
- **Приоритет:** P1 (высокий, защита от манипуляций критична)

---

## P1: Vision AI с приоритетом безопасности для фото

### Проблема
Сейчас бот НЕ обрабатывает фото от пользователей (только отправляет свои). Но пользователи могут присылать:
- Селфи (хотят обсудить внешность, настроение по лицу)
- Скриншоты переписок (хотят обсудить конфликт)
- Фото ситуаций (дом, еда, места)

**КРИТИЧНО:** Нужен приоритет безопасности:
- НЕ сохранять фото несовершеннолетних
- НЕ обрабатывать NSFW контент
- НЕ анализировать фото третьих лиц без контекста

### Текущая архитектура

**Файл:** `bot/handlers/photos.py`
- Только ОТПРАВКА фото (send_photos)
- НЕТ обработчика входящих фото

### Решение

#### Архитектура Vision AI

```
User sends photo
      ↓
[Safety Check] → NSFW? Children? Violence?
      ↓ (safe)
[Claude Vision API]
      ↓
[Context Analysis] → Mood, situation, request
      ↓
Response to user
```

#### Шаг 1: Создать `ai/vision_analyzer.py`

**Файл:** `ai/vision_analyzer.py` (новый)

```python
"""
Vision Analyzer.
Анализ изображений через Claude Vision API с приоритетом безопасности.
"""

import base64
from typing import Dict, Any, Optional, List
from loguru import logger

from anthropic import Anthropic
from config.settings import settings


class VisionAnalyzer:
    """Анализатор изображений."""

    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def analyze_photo(
        self,
        photo_bytes: bytes,
        user_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Анализирует фото через Claude Vision API.

        Args:
            photo_bytes: Байты изображения
            user_message: Сообщение пользователя (если есть)
            context: Контекст (данные пользователя)

        Returns:
            {
                "safe": bool,
                "safety_reason": Optional[str],
                "analysis": Optional[str],
                "detected_content": List[str],  # ["text", "people", "objects", "mood"]
                "mood_from_image": Optional[str],
            }
        """

        # 1. Проверка безопасности (ПЕРВЫЙ приоритет)
        safety_check = await self._check_safety(photo_bytes)

        if not safety_check["safe"]:
            logger.warning(f"Photo rejected: {safety_check['reason']}")
            return {
                "safe": False,
                "safety_reason": safety_check["reason"],
                "analysis": None,
                "detected_content": [],
                "mood_from_image": None,
            }

        # 2. Анализ контента через Claude Vision
        analysis_result = await self._analyze_content(
            photo_bytes=photo_bytes,
            user_message=user_message,
            context=context,
        )

        return {
            "safe": True,
            "safety_reason": None,
            "analysis": analysis_result["analysis"],
            "detected_content": analysis_result["detected_content"],
            "mood_from_image": analysis_result.get("mood"),
        }

    async def _check_safety(self, photo_bytes: bytes) -> Dict[str, Any]:
        """
        Проверка безопасности изображения.

        Returns:
            {"safe": bool, "reason": Optional[str]}
        """

        # Кодируем в base64
        image_base64 = base64.standard_b64encode(photo_bytes).decode("utf-8")

        # Промпт для проверки безопасности
        safety_prompt = """Проанализируй это изображение на предмет безопасности.

КРИТЕРИИ ОТКЛОНЕНИЯ (верни "UNSAFE" если обнаружено):
1. Несовершеннолетние лица (дети, подростки до 18 лет)
2. NSFW контент (обнажённые тела, сексуальный контент)
3. Насилие, кровь, травмы
4. Документы с персональными данными (паспорта, ID)
5. Медицинские снимки (рентген, УЗИ и т.п.)

КРИТЕРИИ РАЗРЕШЕНИЯ:
- Взрослые люди в обычной одежде
- Селфи в нейтральной обстановке
- Скриншоты переписок (текст)
- Фото мест, предметов, еды
- Пейзажи, интерьеры

Ответь СТРОГО в формате:
SAFE - если изображение безопасно
UNSAFE: [причина] - если нужно отклонить

Причины должны быть: "children", "nsfw", "violence", "personal_data", "medical"
"""

        try:
            response = self.client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=100,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",  # TODO: определять тип
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": safety_prompt,
                            }
                        ],
                    }
                ],
            )

            result_text = response.content[0].text.strip()

            if result_text.startswith("UNSAFE"):
                # Извлекаем причину
                reason = result_text.split(":", 1)[1].strip() if ":" in result_text else "unknown"
                return {"safe": False, "reason": reason}

            return {"safe": True, "reason": None}

        except Exception as e:
            logger.error(f"Safety check failed: {e}")
            # В случае ошибки — отклоняем (безопаснее)
            return {"safe": False, "reason": "check_error"}

    async def _analyze_content(
        self,
        photo_bytes: bytes,
        user_message: Optional[str],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Анализ содержимого изображения.

        Returns:
            {
                "analysis": str,  # Текст анализа для пользователя
                "detected_content": List[str],  # Типы контента
                "mood": Optional[str],  # Настроение с фото (если лицо)
            }
        """

        image_base64 = base64.standard_b64encode(photo_bytes).decode("utf-8")

        # Промпт для анализа
        analysis_prompt = f"""Ты — Мира, друг-наставник для женщин. Проанализируй это изображение.

КОНТЕКСТ от пользователя: {user_message if user_message else "Без текста"}

ЗАДАЧА:
1. Определи что на изображении: люди, текст, предметы, место
2. Если это СЕЛФИ — опиши настроение человека по лицу (радость, грусть, усталость, тревога)
3. Если это СКРИНШОТ переписки — кратко суммируй суть (НЕ пересказывай всё!)
4. Если это СИТУАЦИЯ — опиши что видишь

ОТВЕТ в формате JSON:
{{
    "type": "selfie" | "screenshot" | "scene" | "object",
    "description": "краткое описание",
    "mood": "happy|sad|anxious|neutral|tired" (только для селфи),
    "text_summary": "краткая суть" (только для скриншотов)
}}

Будь эмпатична, но лаконична. Не более 2-3 предложений.
"""

        try:
            response = self.client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": analysis_prompt,
                            }
                        ],
                    }
                ],
            )

            result_text = response.content[0].text.strip()

            # Парсим JSON (или текст, если не JSON)
            import json
            try:
                data = json.loads(result_text)

                return {
                    "analysis": data.get("description", ""),
                    "detected_content": [data.get("type", "unknown")],
                    "mood": data.get("mood"),
                }
            except json.JSONDecodeError:
                # Если не JSON — возвращаем как есть
                return {
                    "analysis": result_text,
                    "detected_content": ["unknown"],
                    "mood": None,
                }

        except Exception as e:
            logger.error(f"Content analysis failed: {e}")
            return {
                "analysis": "Не удалось проанализировать изображение",
                "detected_content": [],
                "mood": None,
            }


# Глобальный экземпляр
vision_analyzer = VisionAnalyzer()
```

#### Шаг 2: Добавить обработчик фото в `bot/handlers/photos.py`

```python
async def handle_incoming_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обработчик входящих фотографий от пользователя."""

    user_tg = update.effective_user
    photo = update.message.photo[-1]  # Берём лучшее качество
    caption = update.message.caption or ""

    try:
        # 1. Получаем пользователя
        user, _ = await user_repo.get_or_create(
            telegram_id=user_tg.id,
            username=user_tg.username,
            first_name=user_tg.first_name,
        )

        # 2. Проверка лимитов (фото = токены!)
        subscription = await subscription_repo.get_active(user.id)
        is_premium = subscription and subscription.plan == "premium"

        if not is_premium:
            if subscription and subscription.messages_today >= settings.FREE_MESSAGES_PER_DAY:
                await update.message.reply_text(
                    "Анализ фото доступен только в премиум-версии 💛"
                )
                return

        # 3. Скачиваем фото
        status_msg = await update.message.reply_text("📸 Смотрю на фото...")

        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()

        # 4. Анализ через Vision AI
        from ai.vision_analyzer import vision_analyzer

        result = await vision_analyzer.analyze_photo(
            photo_bytes=bytes(photo_bytes),
            user_message=caption,
            context={"user_id": user.id},
        )

        # 5. Если небезопасно — отклоняем
        if not result["safe"]:
            await status_msg.edit_text(
                _get_safety_rejection_message(result["safety_reason"])
            )
            return

        # 6. Отправляем анализ
        await status_msg.edit_text(result["analysis"])

        # 7. Сохраняем в GCS (опционально)
        # TODO: file_storage_service.save_photo(...)

        # 8. Сохраняем в историю с тегом "photo"
        await conversation_repo.save_message(
            user_id=user.id,
            role="user",
            content=f"[Фото] {caption}",
            tags=["photo"],
            metadata={
                "photo_analysis": result,
                "file_id": photo.file_id,
            },
        )

        logger.info(f"Photo analyzed for user {user_tg.id}: {result['detected_content']}")

    except Exception as e:
        logger.error(f"Error handling photo from {user_tg.id}: {e}")
        await update.message.reply_text(
            "Не удалось обработать фото... Попробуй ещё раз 💛"
        )


def _get_safety_rejection_message(reason: str) -> str:
    """Возвращает сообщение об отклонении фото."""

    messages = {
        "children": "Прости, я не могу анализировать фото с несовершеннолетними 💛",
        "nsfw": "Это фото не подходит для анализа. Давай обсудим что-то другое?",
        "violence": "Я не могу анализировать это фото. Если тебе нужна помощь — позвони 112.",
        "personal_data": "На фото видны персональные данные. Лучше не делиться ими.",
        "medical": "Медицинские снимки лучше обсудить с врачом 💛",
        "check_error": "Не удалось проверить фото. Попробуй другое?",
    }

    return messages.get(reason, "Не могу обработать это фото 💛")
```

#### Шаг 3: Регистрация обработчика в `bot/main.py`

```python
from bot.handlers.photos import handle_incoming_photo

# В функции main():
application.add_handler(MessageHandler(filters.PHOTO, handle_incoming_photo))
```

#### Шаг 4: Тестирование

**Тестовые кейсы:**

1. **Селфи взрослого:**
   - Ожидание: "Вижу, что ты выглядишь уставшей... Тяжёлый день?"

2. **Скриншот переписки:**
   - Ожидание: "Вижу, что он написал X... Похоже, это тебя задело?"

3. **Фото ребёнка:**
   - Ожидание: "Прости, я не могу анализировать фото с несовершеннолетними 💛"

4. **NSFW контент:**
   - Ожидание: Отклонение без деталей

#### Оценка сложности
- **Время:** 5-7 часов (Vision API + safety check + тестирование)
- **Риски:** Средние (False positives в safety check)
- **Приоритет:** P1 (высокий, но требует Claude Vision API)

---

## P2: Анализ тона голоса (эмоции в интонации)

### Проблема
Сейчас голосовые сообщения обрабатываются через Whisper (транскрибация), но интонация и тон голоса **ТЕРЯЮТСЯ**. Claude видит только текст, но НЕ знает:
- Голос дрожал от слёз?
- Говорила агрессивно/раздражённо?
- Тон был саркастичным?
- Говорила быстро/медленно (признак тревоги/усталости)?

### Текущая архитектура

**Файл:** `bot/handlers/voice.py`
- Скачивание голосового → Whisper → текст → Claude
- НЕТ анализа аудио-характеристик

**Файл:** `ai/whisper_client.py`
- Только транскрибация (возвращает текст)

### Решение

#### Архитектура Voice Emotion Analysis

```
Voice message (OGG/MP3)
      ↓
[Whisper Transcription] → text
      ↓
[Audio Feature Extraction] → pitch, tempo, energy, pauses
      ↓
[Emotion Classifier] → happy, sad, anxious, angry, neutral
      ↓
Context for Claude (text + emotion)
```

**Технологии:**
- **librosa** (Python) — извлечение аудио-признаков (pitch, tempo, energy, MFCCs)
- **pyAudioAnalysis** — классификация эмоций (опционально, альтернатива)
- **OpenAI Whisper** — уже используется для транскрибации

#### Шаг 1: Создать `ai/voice_emotion_analyzer.py`

**Файл:** `ai/voice_emotion_analyzer.py` (новый)

```python
"""
Voice Emotion Analyzer.
Анализ эмоций в голосовых сообщениях через тон, интонацию, темп.
"""

import io
import numpy as np
from typing import Dict, Any, Optional
from loguru import logger

try:
    import librosa
    import soundfile as sf
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logger.warning("librosa not installed, voice emotion analysis disabled")


class VoiceEmotionAnalyzer:
    """Анализатор эмоций в голосовых сообщениях."""

    def __init__(self):
        if not LIBROSA_AVAILABLE:
            logger.error("Voice emotion analysis requires librosa library")

    async def analyze_emotion(self, audio_bytes: bytes) -> Dict[str, Any]:
        """
        Анализирует эмоции в голосовом сообщении.

        Args:
            audio_bytes: Байты аудио (OGG/MP3)

        Returns:
            {
                "emotion": str,  # happy, sad, anxious, angry, neutral, tired
                "confidence": float,  # 0.0-1.0
                "features": {
                    "pitch_mean": float,  # Средняя высота тона
                    "pitch_std": float,   # Вариация тона
                    "tempo": float,       # Скорость речи (BPM)
                    "energy": float,      # Энергия голоса
                    "pause_ratio": float, # Доля пауз
                },
                "interpretation": str,  # Описание для промпта
            }
        """

        if not LIBROSA_AVAILABLE:
            return self._fallback_analysis()

        try:
            # 1. Загрузка аудио
            audio, sr = librosa.load(io.BytesIO(audio_bytes), sr=None)

            # 2. Извлечение признаков
            features = self._extract_features(audio, sr)

            # 3. Классификация эмоций
            emotion_result = self._classify_emotion(features)

            return emotion_result

        except Exception as e:
            logger.error(f"Voice emotion analysis failed: {e}")
            return self._fallback_analysis()

    def _extract_features(self, audio: np.ndarray, sr: int) -> Dict[str, float]:
        """Извлекает аудио-признаки."""

        # 1. Pitch (высота тона)
        pitches, magnitudes = librosa.piptrack(y=audio, sr=sr)

        # Берём только значимые (с магнитудой выше порога)
        pitch_values = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                pitch_values.append(pitch)

        pitch_mean = np.mean(pitch_values) if pitch_values else 0
        pitch_std = np.std(pitch_values) if pitch_values else 0

        # 2. Tempo (скорость речи)
        tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)

        # 3. Energy (энергия)
        rms = librosa.feature.rms(y=audio)[0]
        energy_mean = np.mean(rms)

        # 4. Zero-crossing rate (пересечения нуля — показатель чёткости речи)
        zcr = librosa.feature.zero_crossing_rate(audio)[0]
        zcr_mean = np.mean(zcr)

        # 5. Паузы (тишина)
        # Считаем долю времени с низкой энергией
        silence_threshold = np.percentile(rms, 20)  # 20-й перцентиль
        pause_ratio = np.sum(rms < silence_threshold) / len(rms)

        return {
            "pitch_mean": float(pitch_mean),
            "pitch_std": float(pitch_std),
            "tempo": float(tempo),
            "energy": float(energy_mean),
            "zcr": float(zcr_mean),
            "pause_ratio": float(pause_ratio),
        }

    def _classify_emotion(self, features: Dict[str, float]) -> Dict[str, Any]:
        """
        Классифицирует эмоцию на основе признаков.

        Эвристики (на основе исследований):
        - Высокий pitch + высокий tempo = тревога/паника
        - Низкий pitch + низкая энергия = грусть/усталость
        - Высокая энергия + высокий tempo = радость/возбуждение
        - Высокий pitch_std + высокая энергия = злость
        - Много пауз + низкая энергия = усталость
        """

        pitch_mean = features["pitch_mean"]
        pitch_std = features["pitch_std"]
        tempo = features["tempo"]
        energy = features["energy"]
        pause_ratio = features["pause_ratio"]

        # Нормализуем признаки (примерные пороги)
        # TODO: обучить ML модель на реальных данных

        # Тревога: высокий pitch (>180 Hz) + быстрый темп (>120 BPM)
        if pitch_mean > 180 and tempo > 120:
            return {
                "emotion": "anxious",
                "confidence": 0.7,
                "features": features,
                "interpretation": "голос звучит тревожно (высокий тон, быстрая речь)",
            }

        # Грусть/усталость: низкая энергия + медленный темп + много пауз
        if energy < 0.02 and tempo < 90 and pause_ratio > 0.3:
            return {
                "emotion": "sad",
                "confidence": 0.75,
                "features": features,
                "interpretation": "голос звучит устало или грустно (низкая энергия, медленная речь, паузы)",
            }

        # Злость: высокая вариация тона + высокая энергия
        if pitch_std > 30 and energy > 0.05:
            return {
                "emotion": "angry",
                "confidence": 0.65,
                "features": features,
                "interpretation": "голос звучит напряжённо или раздражённо (резкие перепады тона)",
            }

        # Радость: высокая энергия + средний/высокий темп
        if energy > 0.05 and tempo > 110:
            return {
                "emotion": "happy",
                "confidence": 0.6,
                "features": features,
                "interpretation": "голос звучит бодро и энергично",
            }

        # Усталость: много пауз + низкая энергия
        if pause_ratio > 0.4 and energy < 0.03:
            return {
                "emotion": "tired",
                "confidence": 0.7,
                "features": features,
                "interpretation": "голос звучит очень устало (много пауз, низкая энергия)",
            }

        # По умолчанию — нейтральный
        return {
            "emotion": "neutral",
            "confidence": 0.5,
            "features": features,
            "interpretation": "голос в нейтральном тоне",
        }

    def _fallback_analysis(self) -> Dict[str, Any]:
        """Fallback если библиотека недоступна."""
        return {
            "emotion": "neutral",
            "confidence": 0.0,
            "features": {},
            "interpretation": "анализ тона голоса недоступен",
        }


# Глобальный экземпляр
voice_emotion_analyzer = VoiceEmotionAnalyzer()
```

#### Шаг 2: Интегрировать в `bot/handlers/voice.py`

```python
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... существующий код до транскрибации ...

    # 8. Транскрибируем
    await status_message.edit_text("✍️ Расшифровываю...")

    transcribed_text = await whisper_client.transcribe_bytes(...)

    # 8.5. НОВОЕ: Анализ эмоций в голосе
    from ai.voice_emotion_analyzer import voice_emotion_analyzer

    voice_emotion = await voice_emotion_analyzer.analyze_emotion(bytes(voice_bytes))

    logger.info(
        f"Voice emotion detected: {voice_emotion['emotion']} "
        f"(confidence: {voice_emotion['confidence']:.2f})"
    )

    # 9. Показываем распознанный текст
    await status_message.edit_text(f"💬 Ты сказал(а): «{transcribed_text}»")

    # ... дальше подготовка user_data ...

    # 12.5. Добавляем эмоцию голоса в контекст
    user_data["voice_emotion"] = voice_emotion

    # 13. Получаем ответ от Claude (с учётом эмоции в промпте)
    result = await claude.generate_response(...)
```

#### Шаг 3: Обновить системный промпт

**Файл:** `ai/prompts/system_prompt.py`

Добавить блок эмоций голоса:

```python
def _build_user_context_block(user_context: Dict[str, Any]) -> str:
    # ... существующий код ...

    # Блок эмоций голоса
    voice_emotion_block = ""
    if user_context.get("voice_emotion"):
        voice_data = user_context["voice_emotion"]

        if voice_data["confidence"] > 0.5:  # Только если уверенность выше порога
            emotion = voice_data["emotion"]
            interpretation = voice_data["interpretation"]

            voice_emotion_block = f"""
### 🎤 ЭМОЦИЯ В ГОЛОСЕ (голосовое сообщение)

**Анализ тона:** {interpretation}

**КАК ИСПОЛЬЗОВАТЬ:**
- Учти не только СЛОВА, но и КАК они сказаны
- Если голос дрожит/звучит устало — признай это: "Слышу, как тебе тяжело..."
- Если голос напряжённый — спроси: "Чувствую напряжение в твоём голосе... Что-то произошло?"
- НЕ игнорируй несоответствие: если СЛОВА бодрые, но ГОЛОС грустный — обрати внимание!
"""

    return f"{context}{mood_block}{voice_emotion_block}"
```

#### Шаг 4: Установка зависимостей

**Файл:** `requirements.txt`

```txt
librosa==0.10.1
soundfile==0.12.1
numpy>=1.24.0
```

**Установка:**
```bash
pip install librosa soundfile
```

#### Шаг 5: Тестирование

**Тестовые кейсы:**

1. **Голос с тревогой (высокий тон, быстро):**
   - Ожидание: Claude: "Слышу, что ты говоришь очень быстро... Переживаешь?"

2. **Усталый голос (паузы, низкая энергия):**
   - Ожидание: "По голосу слышу, как ты устала... Тяжёлый день?"

3. **Несоответствие (слова "всё хорошо" но голос грустный):**
   - Ожидание: "Ты говоришь 'всё хорошо', но по голосу чувствую грусть... Поговорим?"

#### Оценка сложности
- **Время:** 6-8 часов (librosa + эвристики + тестирование)
- **Риски:** Высокие (эвристики могут давать false positives, нужна калибровка)
- **Приоритет:** P2 (средний, но ОЧЕНЬ ценная фича для эмпатии)

---

## P2: Партнёрская программа (статусы Друг/Активист)

### Проблема
Сейчас есть реферальная система (пригласить подругу → +7 дней обеим), но НЕТ:
- Видимых статусов ("Друг", "Активист", "Амбассадор")
- Геймификации (бейджи, достижения)
- Специальных привилегий для активных рефереров

**Цель:** Мотивировать пользователей приводить подруг через публичное признание и бонусы.

### Текущая архитектура

**Файл:** `services/referral.py`
- Создание кода, активация, бонусы
- Milestone на 3 реферала → статус "guardian" (но НЕ используется)

**Файл:** `database/models.py` → `User.special_status`
- Поле существует, но нигде НЕ отображается

### Решение

#### Статусная система

| Статус | Условие | Бонусы |
|--------|---------|--------|
| **Друг** | 1 реферал | +7 дней premium |
| **Активист** | 3 реферала | +14 дней premium + бейдж 🌟 |
| **Амбассадор** | 10 рефералов | +30 дней premium + бейдж 💎 + ранний доступ к новым фичам |

#### Шаг 1: Расширить `services/referral.py`

**Файл:** `services/referral.py`

```python
# Добавить константы статусов
REFERRAL_STATUSES = {
    "friend": {
        "threshold": 1,
        "badge": "💛",
        "title": "Друг",
        "bonus_days": 7,
    },
    "activist": {
        "threshold": 3,
        "badge": "🌟",
        "title": "Активист",
        "bonus_days": 14,
    },
    "ambassador": {
        "threshold": 10,
        "badge": "💎",
        "title": "Амбассадор",
        "bonus_days": 30,
    },
}


async def apply_referral(self, new_user_id: int, code: str) -> dict:
    # ... существующий код ...

    # Проверяем milestone (обновлённая логика)
    referral_count = await self.referral_repo.count_by_referrer(referral.referrer_id)

    # Определяем новый статус
    new_status = self._get_status_for_count(referral_count)

    if new_status:
        # Обновляем статус
        await self.user_repo.update(referral.referrer_id, special_status=new_status)

        # Даём бонусные дни за статус
        status_info = REFERRAL_STATUSES[new_status]
        await self._give_bonus(referral.referrer_id, status_info["bonus_days"])

        # Отправляем уведомление
        await self._notify_status_upgrade(
            user_id=referral.referrer_id,
            status=new_status,
            count=referral_count,
        )

        logger.info(f"User {referral.referrer_id} reached status '{new_status}' ({referral_count} referrals)")

    # ... остальной код ...


def _get_status_for_count(self, count: int) -> Optional[str]:
    """Определяет статус по количеству рефералов."""
    if count >= REFERRAL_STATUSES["ambassador"]["threshold"]:
        return "ambassador"
    elif count >= REFERRAL_STATUSES["activist"]["threshold"]:
        return "activist"
    elif count >= REFERRAL_STATUSES["friend"]["threshold"]:
        return "friend"
    return None


async def _notify_status_upgrade(self, user_id: int, status: str, count: int) -> None:
    """Отправляет уведомление о новом статусе."""
    try:
        from telegram import Bot
        from config.settings import settings

        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

        status_info = REFERRAL_STATUSES[status]

        message = f"""🎉 Поздравляю!

Ты стала **{status_info['title']}** {status_info['badge']}

Ты пригласила {count} {"подругу" if count == 1 else "подруги" if count < 5 else "подруг"}!

**Твой бонус:** +{status_info['bonus_days']} дней премиум-доступа 💛

Спасибо, что делишься Мирой с другими! Вместе мы сильнее."""

        user = await self.user_repo.get(user_id)
        if user and user.telegram_id:
            await bot.send_message(chat_id=user.telegram_id, text=message)
            logger.info(f"Sent status upgrade notification to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send status notification: {e}")
```

#### Шаг 2: Отображение статуса в WebApp

**Файл:** `webapp/frontend/index.html`

Добавить блок статуса в секцию статистики:

```html
<!-- Секция "Партнёрская программа" -->
<section class="stats-section">
  <h3>💛 Партнёрская программа</h3>

  <div class="status-badge">
    <span class="badge" id="user-status-badge">💛</span>
    <span class="status-title" id="user-status-title">Друг</span>
  </div>

  <div class="referral-progress">
    <p><strong>Приглашено подруг:</strong> <span id="referral-count">0</span></p>
    <p><strong>Следующий уровень:</strong> <span id="next-milestone">3 реферала → Активист 🌟</span></p>
  </div>

  <div class="referral-link">
    <p>Твоя реферальная ссылка:</p>
    <input type="text" id="referral-link-input" readonly />
    <button id="copy-referral-btn">Скопировать</button>
  </div>
</section>
```

**Файл:** `webapp/frontend/app.js`

```javascript
// Загрузка данных партнёрской программы
async function loadReferralData() {
  const response = await fetch('/api/referral/stats', {
    headers: { 'Authorization': `tma ${window.Telegram.WebApp.initData}` }
  });

  const data = await response.json();

  // Отображаем статус
  const statusBadge = document.getElementById('user-status-badge');
  const statusTitle = document.getElementById('user-status-title');

  const statusMap = {
    'friend': { badge: '💛', title: 'Друг' },
    'activist': { badge: '🌟', title: 'Активист' },
    'ambassador': { badge: '💎', title: 'Амбассадор' },
  };

  const status = statusMap[data.status] || statusMap['friend'];
  statusBadge.textContent = status.badge;
  statusTitle.textContent = status.title;

  // Количество рефералов
  document.getElementById('referral-count').textContent = data.invited_count;

  // Следующий milestone
  if (data.next_milestone) {
    const nextStatus = data.next_milestone_status;
    const nextBadge = statusMap[nextStatus].badge;
    document.getElementById('next-milestone').textContent =
      `${data.next_milestone} реферала → ${statusMap[nextStatus].title} ${nextBadge}`;
  } else {
    document.getElementById('next-milestone').textContent = 'Максимальный уровень! 💎';
  }

  // Реферальная ссылка
  document.getElementById('referral-link-input').value = data.referral_link;
}

// Копирование ссылки
document.getElementById('copy-referral-btn').addEventListener('click', () => {
  const input = document.getElementById('referral-link-input');
  input.select();
  document.execCommand('copy');

  // Показываем уведомление
  window.Telegram.WebApp.showAlert('Ссылка скопирована! 💛');
});

// Вызываем при загрузке
loadReferralData();
```

#### Шаг 3: API endpoint для статистики

**Файл:** `webapp/api/routes/referral.py`

```python
@router.get("/stats")
async def get_referral_stats(user_id: int = Depends(get_current_user_id)):
    """Получить статистику партнёрской программы."""

    from services.referral import ReferralService

    service = ReferralService()
    stats = await service.get_stats(user_id)

    # Определяем текущий статус
    user = await user_repo.get(user_id)
    current_status = user.special_status or "friend"

    # Генерируем реферальную ссылку
    bot_username = settings.TELEGRAM_BOT_USERNAME
    referral_link = f"https://t.me/{bot_username}?start={stats['code']}"

    # Определяем следующий milestone
    next_milestone_info = _get_next_milestone(stats['invited_count'])

    return {
        "status": current_status,
        "invited_count": stats['invited_count'],
        "bonus_earned_days": stats['bonus_earned_days'],
        "referral_link": referral_link,
        "next_milestone": next_milestone_info["count"] if next_milestone_info else None,
        "next_milestone_status": next_milestone_info["status"] if next_milestone_info else None,
    }


def _get_next_milestone(current_count: int) -> Optional[Dict]:
    """Определяет следующий milestone."""
    from services.referral import REFERRAL_STATUSES

    if current_count < REFERRAL_STATUSES["activist"]["threshold"]:
        return {
            "count": REFERRAL_STATUSES["activist"]["threshold"],
            "status": "activist",
        }
    elif current_count < REFERRAL_STATUSES["ambassador"]["threshold"]:
        return {
            "count": REFERRAL_STATUSES["ambassador"]["threshold"],
            "status": "ambassador",
        }
    return None
```

#### Шаг 4: Отображение статуса в боте (команда /profile)

**Файл:** `bot/handlers/commands.py`

```python
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_tg = update.effective_user

    user, _ = await user_repo.get_or_create(...)

    # ... существующий код профиля ...

    # Блок партнёрской программы
    from services.referral import ReferralService, REFERRAL_STATUSES

    service = ReferralService()
    stats = await service.get_stats(user.id)

    status = user.special_status or "friend"
    status_info = REFERRAL_STATUSES.get(status, REFERRAL_STATUSES["friend"])

    profile_text += f"""

💛 **Партнёрская программа**
Статус: {status_info['badge']} {status_info['title']}
Приглашено подруг: {stats['invited_count']}
"""

    await update.message.reply_text(profile_text, parse_mode="Markdown")
```

#### Шаг 5: Тестирование

**Тестовые кейсы:**

1. **1 реферал:**
   - Ожидание: Статус "Друг 💛" + уведомление

2. **3 реферала:**
   - Ожидание: Статус "Активист 🌟" + уведомление + бонус +14 дней

3. **10 рефералов:**
   - Ожидание: Статус "Амбассадор 💎" + уведомление + бонус +30 дней

4. **WebApp отображение:**
   - Проверить корректность бейджа, счётчика, next milestone

#### Оценка сложности
- **Время:** 4-5 часов (API + frontend + уведомления)
- **Риски:** Низкие (изменения изолированы)
- **Приоритет:** P2 (средний, геймификация важна для retention)

---

## Общий план внедрения

### Порядок реализации (рекомендуемый)

1. **P1: Mood Analyzer → Промпт** (2-3 часа) — быстрый win, улучшает эмпатию Claude
2. **P2: Партнёрская программа** (4-5 часов) — геймификация, мотивация пользователей
3. **P1: Валидация памяти** (4-6 часов) — защита от манипуляций, критично для trust
4. **P1: Vision AI** (5-7 часов) — требует Claude Vision API, но очень ценная фича
5. **P2: Анализ тона голоса** (6-8 часов) — сложнее всего, но максимальная эмпатия

### Итого время: ~22-29 часов

### Зависимости

**Библиотеки:**
```bash
pip install librosa soundfile  # Для P2: анализ голоса
```

**API:**
- Claude Vision API (для P1: Vision AI)

**База данных:**
- Миграция для `memory_entries.metadata` (JSONB)

---

## Мониторинг и метрики

После внедрения отслеживать:

1. **Mood Analyzer:**
   - Процент сообщений со смешанными эмоциями (ожидается ~20-30%)
   - User feedback на распознавание эмоций (опросы)

2. **Валидация памяти:**
   - Количество отклонённых записей в неделю
   - False positive rate (легитимные записи отклонены)

3. **Vision AI:**
   - Количество фото в день
   - Safety rejection rate (ожидается <5%)

4. **Анализ голоса:**
   - Accuracy эмоций (сравнение с текстом)
   - User feedback ("голос распознан правильно?")

5. **Партнёрская программа:**
   - Conversion rate (сколько рефералов активируются)
   - Retention rate активных рефереров

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Mood analyzer даёт false positives | Средняя | Добавить confidence threshold, не показывать если <0.5 |
| Memory validator блокирует честные записи | Средняя | Добавить ручной override ("Всё равно сохранить?") |
| Vision AI отклоняет безопасные фото | Низкая | Логировать все отклонения, калибровать промпт |
| Voice emotion даёт неверные эмоции | Высокая | Использовать только как дополнительный контекст, не как истину |
| Статусы не мотивируют | Низкая | A/B тест: с бейджами vs без, замерить retention |

---

## Заключение

Этот план покрывает **все P1 и P2 приоритеты** с детальными шагами реализации, тестированием и оценкой рисков.

**Следующие шаги:**
1. Утвердить порядок реализации
2. Начать с P1: Mood Analyzer (быстрый win)
3. Итеративно внедрять остальные фичи
4. Собирать метрики и feedback от пользователей

**Готов начинать?** 🚀
