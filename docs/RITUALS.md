# Ритуалы и поздравления

## Обзор

Система ритуалов позволяет Mira Bot отправлять персонализированные сообщения пользователям:
- **Утренние check-in** — приветствие с учётом контекста
- **Вечерние check-in** — проверка как прошёл день
- **Праздничные поздравления** — дни рождения, годовщины

## Архитектура

### Компоненты

```
services/scheduler.py          # APScheduler — основной планировщик
├── process_scheduled_messages  # Каждую минуту — отправка запланированных
├── check_celebrations          # Ежедневно в 9:00 — дни рождения, годовщины
├── send_expiration_reminders   # Ежедневно в 10:00 — напоминания о подписке
└── cleanup_old_messages        # Ежедневно в 3:00 — очистка старых записей

ai/prompts/checkin.py          # Промпты для персонализации check-in
ai/prompts/celebrations.py     # Промпты для поздравлений
database/models.py             # ScheduledMessage, User (birthday, anniversary)
```

### Поток данных

```
Пользователь включает ритуал
         ↓
callbacks.py: _handle_ritual()
         ↓
schedule_user_rituals(user_id)
         ↓
ScheduledMessage создаётся в БД
         ↓
[Каждую минуту]
process_scheduled_messages()
         ↓
_generate_ritual_content() → Claude API
         ↓
Персонализированное сообщение → Telegram
```

## Персонализация

### Контекст для check-in

При генерации утренних/вечерних сообщений используется:

1. **Недавние темы** — из MemoryEntry (последние 3)
2. **Настроение** — из MoodEntry (последняя запись)
3. **Последнее сообщение** — текст от пользователя

```python
# Пример промпта
context_parts = []

if recent_topics:
    context_parts.append(f"Недавние темы: {', '.join(recent_topics)}")

if recent_mood:
    context_parts.append(f"Последнее настроение: {emotion_ru}")

if last_message:
    context_parts.append(f"Последнее сообщение: '{content[:150]}'")
```

### Примеры персонализированных сообщений

**Утро (с контекстом):**
> Доброе утро, солнце ☀️ Вчера был непростой разговор о муже... Как ты сегодня?

**Вечер (без контекста):**
> Привет 💛 Как прошёл день?

**День рождения:**
> С днём рождения, Аня! 🎂 Это Мира. Помню, ты рассказывала о планах на этот год. Желаю, чтобы всё получилось 💛

## Праздники

### Поля в User

```python
birthday: Date      # День рождения (YYYY-MM-DD)
anniversary: Date   # Годовщина свадьбы (YYYY-MM-DD)
```

### Миграция БД

```bash
python add_celebration_fields.py
```

Скрипт поддерживает SQLite и PostgreSQL:
- SQLite: использует `PRAGMA table_info(users)`
- PostgreSQL: использует `information_schema.columns`

### Логика проверки

Каждое утро в 9:00 запускается `check_celebrations()`:

```python
today = datetime.now()
month = today.month
day = today.day

# Находим пользователей с праздником сегодня
birthday_users = await user_repo.get_by_celebration_date("birthday", month, day)
anniversary_users = await user_repo.get_by_celebration_date("anniversary", month, day)
```

Условия отправки:
- `is_blocked == False`
- `proactive_messages == True`

## API

### Включение/выключение ритуалов

**Callback:** `ritual:toggle:<type>`

```python
# types: morning, evening, gratitude, letter
await callback_query.answer("Ритуал morning включён")
```

### Планирование

```python
from services.scheduler import schedule_user_rituals, cancel_user_ritual

# Запланировать все включённые ритуалы
await schedule_user_rituals(user_id)

# Отменить конкретный тип
await cancel_user_ritual(user_id, "morning_checkin")
```

### Ручная отправка (для тестов)

```python
from services.scheduler import check_celebrations

# Проверить праздники сейчас
await check_celebrations()
```

## Конфигурация

### settings.py

```python
RITUAL_MORNING_DEFAULT = "08:00"   # Время утреннего check-in
RITUAL_EVENING_DEFAULT = "21:00"  # Время вечернего check-in
```

### Пользовательские настройки

```python
User.preferred_time_morning  # Переопределение утреннего времени
User.preferred_time_evening  # Переопределение вечернего времени
User.proactive_messages      # Глобальный флаг (True/False)
User.rituals_enabled         # Список включённых ритуалов ["morning", "evening"]
```

## Таблица ScheduledMessage

```sql
CREATE TABLE scheduled_messages (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    type VARCHAR(50) NOT NULL,       -- morning_checkin, evening_checkin, etc.
    content TEXT,                     -- NULL = генерировать через Claude
    scheduled_for DATETIME NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, sent, cancelled
    sent_at DATETIME,
    created_at DATETIME DEFAULT NOW()
);
```

## Fallback

При ошибке генерации через Claude используются шаблонные сообщения:

```python
# ai/prompts/rituals.py
MORNING_CHECKIN_PROMPTS = [
    "Доброе утро 🌅 Как ты сегодня?",
    "Привет, солнце ☀️ Как спалось?",
    ...
]

EVENING_CHECKIN_PROMPTS = [
    "Добрый вечер 🌙 Как прошёл день?",
    "Привет 💛 День заканчивается... Как ты?",
    ...
]
```

## Мониторинг

### Логи

```bash
# На сервере
tail -f /var/log/mira_bot.log | grep -E "(Sent scheduled|check_celebrations|birthday|anniversary)"
```

### Статистика

```sql
-- Сколько сообщений отправлено за день
SELECT COUNT(*) FROM scheduled_messages
WHERE status = 'sent' AND sent_at > NOW() - INTERVAL '1 day';

-- Пользователи с днём рождения в этом месяце
SELECT display_name, birthday FROM users
WHERE EXTRACT(MONTH FROM birthday) = EXTRACT(MONTH FROM NOW());
```

## Troubleshooting

### Ритуалы не отправляются

1. Проверить `user.proactive_messages == True`
2. Проверить `user.rituals_enabled` содержит нужный тип
3. Проверить записи в `scheduled_messages` со статусом `pending`
4. Проверить логи scheduler

### Праздники не поздравляются

1. Проверить что `birthday` или `anniversary` заполнены
2. Формат даты должен быть `DATE` (не `DATETIME`)
3. Проверить `proactive_messages == True`

### Дублирование сообщений

Возможно запущено несколько инстансов бота:

```bash
pgrep -c -f "python -m bot.main"  # Должно быть 1
pkill -9 python  # Убить все
python -m bot.main  # Запустить один
```
