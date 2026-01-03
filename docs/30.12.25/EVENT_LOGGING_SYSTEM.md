# Система автоматического логирования событий пользователей

**Дата:** 03.01.2026
**Версия:** v1.11.0
**Commit:** d1a3087

---

## 🎯 Цель

Добавить автоматическое логирование важных событий пользователей в админ-панель для отслеживания активности, вовлеченности и прогресса пользователей.

---

## ✅ Что реализовано

### 1. Системный администратор для автологов

**Файл:** `database/migrations/versions/20260103_add_system_admin.py`

Создан специальный системный администратор с `telegram_id=0` для автоматического логирования событий.

**Миграция:**
```python
op.execute("""
    INSERT INTO admin_users (telegram_id, username, first_name, role, is_active, created_at)
    VALUES (0, 'system', 'System', 'admin', 1, datetime('now'))
    ON CONFLICT (telegram_id) DO NOTHING;
""")
```

**Результат в БД:**
```
id: 3
telegram_id: 0
username: system
first_name: System
role: admin
is_active: 1
```

---

### 2. SystemLogger - центральный логгер событий

**Файл:** `utils/system_logger.py`

Утилита для логирования всех системных событий через `AdminLogRepository`.

**Реализованные методы:**

#### `log_user_onboarding_completed()`
Логирует завершение онбординга нового пользователя.

**Параметры:**
- `user_id` - ID пользователя
- `telegram_id` - Telegram ID
- `username` - Username пользователя
- `first_name` - Имя пользователя
- `referrer_telegram_id` - Telegram ID реферера (опционально)
- `referrer_username` - Username реферера (опционально)

**Пример лога:**
```json
{
  "action": "user_onboarding_completed",
  "resource_type": "user",
  "resource_id": 12345,
  "details": {
    "username": "john_doe",
    "first_name": "John",
    "referrer_telegram_id": 67890,
    "referrer_username": "jane_doe"
  }
}
```

#### `log_first_voice_message()`
Логирует первое голосовое сообщение пользователя.

**Параметры:**
- `user_id`
- `telegram_id`
- `username`
- `duration` - длительность голосового сообщения (секунды)

**Пример лога:**
```json
{
  "action": "first_voice_message",
  "resource_type": "user",
  "resource_id": 12345,
  "details": {
    "username": "john_doe",
    "duration": 15
  }
}
```

#### `log_first_photo_message()`
Логирует первое сообщение с фото.

**Параметры:**
- `user_id`
- `telegram_id`
- `username`

**Пример лога:**
```json
{
  "action": "first_photo_message",
  "resource_type": "user",
  "resource_id": 12345,
  "details": {
    "username": "john_doe"
  }
}
```

#### `log_message_milestone()`
Логирует достижение вехи по количеству сообщений (50, 100, 300, 1000).

**Параметры:**
- `user_id`
- `telegram_id`
- `username`
- `milestone` - достигнутая веха (50, 100, 300, 1000)
- `total_messages` - общее количество сообщений

**Пример лога:**
```json
{
  "action": "message_milestone",
  "resource_type": "user",
  "resource_id": 12345,
  "details": {
    "username": "john_doe",
    "milestone": 100,
    "total_messages": 100
  }
}
```

#### `log_user_inactive()`
Логирует неактивного пользователя (50+ сообщений, 5+ дней без активности).

**Параметры:**
- `user_id`
- `telegram_id`
- `username`
- `total_messages`
- `days_inactive` - дней неактивности

**Пример лога:**
```json
{
  "action": "user_inactive",
  "resource_type": "user",
  "resource_id": 12345,
  "details": {
    "username": "john_doe",
    "total_messages": 78,
    "days_inactive": 7
  }
}
```

---

### 3. EventTracker - трекер событий

**Файл:** `utils/event_tracker.py`

Утилита для отслеживания первого вхождения события и вех по количеству сообщений.

**Реализованные методы:**

#### `track_first_voice_message(user, duration)`
Проверяет, является ли голосовое сообщение первым для пользователя.

**Логика:**
1. Получает все голосовые сообщения пользователя из истории
2. Если `count == 1` → это первое голосовое
3. Вызывает `system_logger.log_first_voice_message()`

**Возвращает:** `True` если это первое голосовое, иначе `False`

#### `track_first_photo_message(user)`
Проверяет, является ли фото первым для пользователя.

**Логика:**
1. Получает все фото-сообщения из истории (tag="photo")
2. Если `count == 1` → это первое фото
3. Вызывает `system_logger.log_first_photo_message()`

**Возвращает:** `True` если это первое фото, иначе `False`

#### `track_message_milestone(user)`
Проверяет достижение вех по количеству сообщений.

**Вехи:** 50, 100, 300, 1000 сообщений

**Логика:**
1. Получает все сообщения пользователя (role="user")
2. Считает общее количество
3. Если `total_messages == milestone` → логирует веху
4. Вызывает `system_logger.log_message_milestone()`

**Возвращает:** `milestone` (int) если достигнута веха, иначе `None`

---

### 4. Интеграция в обработчики

#### bot/handlers/voice.py

**Изменения:**
- Добавлен импорт `from utils.event_tracker import event_tracker`
- После сохранения голосового сообщения в историю:

```python
# 16. Проверяем это первое голосовое — отвечаем голосом!
voice_count = await conversation_repo.count_by_user_and_type(user.id, "voice")
if voice_count <= 1:
    # Логируем первое голосовое сообщение
    try:
        await event_tracker.track_first_voice_message(user, duration=voice.duration)
    except Exception as e:
        logger.warning(f"Failed to track first voice message: {e}")

# ... existing voice response code ...

# 17. Проверяем вехи по количеству сообщений
try:
    milestone = await event_tracker.track_message_milestone(user)
    if milestone:
        logger.info(f"User {user_tg.id} reached milestone: {milestone} messages")
except Exception as e:
    logger.warning(f"Failed to track message milestone: {e}")
```

#### bot/handlers/message.py

**Изменения:**
- Добавлен импорт `from utils.event_tracker import event_tracker`

**1. Трекинг вех в текстовых сообщениях (после line 375):**

```python
# 8.3. Трекаем вехи по количеству сообщений
try:
    milestone = await event_tracker.track_message_milestone(user)
    if milestone:
        logger.info(f"User {user_tg.id} reached milestone: {milestone} messages")
except Exception as e:
    logger.warning(f"Failed to track message milestone: {e}")
```

**2. Трекинг фото в handle_photo (после line 1102):**

```python
# 12. Трекаем первое фото и вехи по сообщениям
try:
    # Проверяем это первое фото
    await event_tracker.track_first_photo_message(user)
except Exception as e:
    logger.warning(f"Failed to track first photo message: {e}")

try:
    # Проверяем вехи по количеству сообщений
    milestone = await event_tracker.track_message_milestone(user)
    if milestone:
        logger.info(f"User {user_tg.id} reached milestone: {milestone} messages")
except Exception as e:
    logger.warning(f"Failed to track message milestone: {e}")
```

---

### 5. Скрипт проверки неактивных пользователей

**Файл:** `scripts/check_inactive_users.py`

Скрипт для периодической проверки пользователей с 50+ сообщениями и неактивностью 5+ дней.

**Логика:**
1. Получает всех пользователей
2. Фильтрует:
   - Не заблокированных
   - Завершивших онбординг
   - С 50+ сообщениями
3. Проверяет дату последнего сообщения
4. Если `days_since_last >= 5` → логирует как неактивного

**Использование:**
```bash
# Запуск вручную
python scripts/check_inactive_users.py

# Запуск через cron (каждый день в 12:00)
0 12 * * * cd /root/mira_bot && source venv/bin/activate && python scripts/check_inactive_users.py
```

---

## 📊 Список отслеживаемых событий

| Событие | Action | Триггер | Источник |
|---------|--------|---------|----------|
| ✅ Завершение онбординга | `user_onboarding_completed` | Пользователь ввёл имя | `message.py` |
| ✅ Первое голосовое | `first_voice_message` | Первое голосовое сообщение | `voice.py` |
| ✅ Первое фото | `first_photo_message` | Первое сообщение с фото | `message.py` |
| ✅ Веха: 50 сообщений | `message_milestone` | 50-е сообщение | `message.py`, `voice.py` |
| ✅ Веха: 100 сообщений | `message_milestone` | 100-е сообщение | `message.py`, `voice.py` |
| ✅ Веха: 300 сообщений | `message_milestone` | 300-е сообщение | `message.py`, `voice.py` |
| ✅ Веха: 1000 сообщений | `message_milestone` | 1000-е сообщение | `message.py`, `voice.py` |
| ✅ Неактивный пользователь | `user_inactive` | 50+ сообщений, 5+ дней неактивности | `check_inactive_users.py` (cron) |

---

## 🔍 Просмотр логов в админке

### Где смотреть:

**Админ-панель → Логи операций**

URL: `https://your-domain.com/admin#logs`

### Фильтры:

1. **По действию:**
   - `user_onboarding_completed`
   - `first_voice_message`
   - `first_photo_message`
   - `message_milestone`
   - `user_inactive`

2. **По пользователю:**
   - Фильтр по `resource_id` (user telegram_id)

3. **По дате:**
   - Период времени

### Пример отображения лога:

```
[03.01.2026 00:52:15] System
Action: first_voice_message
Resource: user #12345
Success: ✅
Details: {"username": "john_doe", "duration": 15}
```

---

## 🚀 Развёртывание

### Обновлённые файлы:

```bash
# Migration
database/migrations/versions/20260103_add_system_admin.py

# Utilities
utils/system_logger.py
utils/event_tracker.py

# Handlers
bot/handlers/message.py
bot/handlers/voice.py

# Scripts
scripts/check_inactive_users.py
```

### Команды развёртывания:

```bash
# 1. Загрузка файлов
scp database/migrations/versions/20260103_add_system_admin.py root@31.44.7.144:/root/mira_bot/database/migrations/versions/
scp utils/system_logger.py root@31.44.7.144:/root/mira_bot/utils/
scp utils/event_tracker.py root@31.44.7.144:/root/mira_bot/utils/
scp bot/handlers/message.py root@31.44.7.144:/root/mira_bot/bot/handlers/
scp bot/handlers/voice.py root@31.44.7.144:/root/mira_bot/bot/handlers/
scp scripts/check_inactive_users.py root@31.44.7.144:/root/mira_bot/scripts/

# 2. Запуск миграции
ssh root@31.44.7.144 "cd /root/mira_bot && source venv/bin/activate && alembic upgrade head"

# 3. Перезапуск сервисов
ssh root@31.44.7.144 "systemctl restart mirabot && systemctl restart mira-webapp"

# 4. Проверка статуса
ssh root@31.44.7.144 "systemctl status mirabot --no-pager"
ssh root@31.44.7.144 "systemctl status mira-webapp --no-pager"
```

**Результат:**
- ✅ Миграция применена: `20251229_add_api_costs -> 20260103_add_system_admin`
- ✅ System admin создан: `id=3, telegram_id=0`
- ✅ Сервисы перезапущены: Active (running)
- ✅ Статус: Deployed to production

---

## 🎯 Результат

### Теперь логируются автоматически:

1. ✅ **Новые пользователи** с информацией о рефералах
2. ✅ **Первое голосовое сообщение** с длительностью
3. ✅ **Первое фото** от пользователя
4. ✅ **Вехи по сообщениям**: 50, 100, 300, 1000
5. ✅ **Неактивные пользователи** (50+ сообщений, 5+ дней)

### Преимущества:

- Отслеживание прогресса пользователей
- Выявление вовлечённых пользователей
- Обнаружение churn (неактивных)
- Аналитика по первым касаниям (голосовые, фото)
- Статистика по рефералам

---

## 📝 Примеры использования

### 1. Просмотр всех новых пользователей за сегодня

**Фильтр:**
- Action: `user_onboarding_completed`
- Date: Сегодня

### 2. Кто отправил первое голосовое сегодня?

**Фильтр:**
- Action: `first_voice_message`
- Date: Сегодня

### 3. Пользователи, достигшие 100 сообщений

**Фильтр:**
- Action: `message_milestone`
- Details содержит: `"milestone": 100`

### 4. Неактивные пользователи (для реактивации)

**Фильтр:**
- Action: `user_inactive`
- Date: Последние 7 дней

---

## 🔗 Связанные файлы

- [20260103_add_system_admin.py](../../database/migrations/versions/20260103_add_system_admin.py) - миграция
- [system_logger.py](../../utils/system_logger.py) - логгер
- [event_tracker.py](../../utils/event_tracker.py) - трекер
- [check_inactive_users.py](../../scripts/check_inactive_users.py) - скрипт проверки
- [message.py](../../bot/handlers/message.py) - обработчик сообщений
- [voice.py](../../bot/handlers/voice.py) - обработчик голосовых

---

**Commit:** d1a3087
**GitHub:** https://github.com/ircitdev/MiraBot/commit/d1a3087
**Статус:** ✅ Deployed to production
**Дата развёртывания:** 03.01.2026 00:53 MSK

---

✨ **Теперь все важные события пользователей автоматически логируются в админке!**
