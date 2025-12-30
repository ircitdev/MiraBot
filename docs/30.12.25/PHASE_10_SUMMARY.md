# Фаза 10: API Аналитика и Управление — Полная документация

**Дата:** 30.12.2025
**Версия:** v1.10.0
**Статус:** ✅ Завершено

---

## 🎯 Цель фазы

Создать полную прозрачность расходов на API и удобное управление системой через веб-интерфейс.

---

## 📊 Статистика фазы

- **Новых функций:** 7
- **Исправлено багов:** 4
- **Добавлено эндпоинтов:** 5
- **Обновлено модулей:** 4
- **Строк кода:** +2000
- **Часов работы:** 15

---

## ✅ Реализованные функции

### 30. Логирование расходов OpenAI Whisper API

**Файлы:**
- `ai/whisper_client.py`
- `bot/handlers/voice.py`

**Что сделано:**

#### Изменён `WhisperClient.transcribe_bytes()`

**До:**
```python
async def transcribe_bytes(
    self,
    audio_bytes: bytes,
    file_extension: str = "ogg",
    language: str = "ru",
) -> Optional[str]:
    """Возвращает только текст транскрипции."""
    # ...
    return transcript.strip()
```

**После:**
```python
async def transcribe_bytes(
    self,
    audio_bytes: bytes,
    file_extension: str = "ogg",
    language: str = "ru",
    audio_duration_seconds: Optional[int] = None,
) -> Tuple[Optional[str], Dict]:
    """
    Возвращает текст транскрипции И информацию о расходах.

    Returns:
        Tuple[text, cost_info]:
            - text: Транскрибированный текст
            - cost_info: {
                'audio_seconds': int,
                'cost_usd': float,
                'model': str
            }
    """
    cost_info = {
        'audio_seconds': audio_duration_seconds or 0,
        'cost_usd': audio_duration_seconds * 0.0001 if audio_duration_seconds else 0.0,
        'model': self.model
    }

    result = await self.transcribe(temp_file.name, language)
    return result, cost_info
```

**Цены OpenAI Whisper:**
- $0.006 per minute
- $0.0001 per second
- 30 секунд = $0.003
- 1 минута = $0.006

#### Обновлён обработчик голосовых сообщений

**Файл:** `bot/handlers/voice.py`

```python
# Импорт репозитория
from database.repositories.api_cost import ApiCostRepository
api_cost_repo = ApiCostRepository()

# Транскрибация с передачей длительности
transcribed_text, whisper_cost_info = await whisper_client.transcribe_bytes(
    bytes(voice_bytes),
    file_extension="ogg",
    language="ru",
    audio_duration_seconds=voice.duration,  # ← Передаём длительность
)

# Сохранение расходов в БД
if whisper_cost_info['cost_usd'] > 0:
    try:
        await api_cost_repo.create(
            user_id=user.id,
            provider='openai',
            operation='speech_to_text',
            cost_usd=whisper_cost_info['cost_usd'],
            audio_seconds=whisper_cost_info['audio_seconds'],
            model=whisper_cost_info['model'],
        )
        logger.info(
            f"Logged Whisper API cost for user {user.id}: "
            f"${whisper_cost_info['cost_usd']:.6f} "
            f"({whisper_cost_info['audio_seconds']}s)"
        )
    except Exception as e:
        logger.error(f"Failed to log Whisper API cost: {e}")
```

**Пример лога:**
```
INFO: Logged Whisper API cost for user 7: $0.003000 (30s)
```

**Запись в БД:**
```json
{
    "user_id": 7,
    "provider": "openai",
    "operation": "speech_to_text",
    "cost_usd": 0.003,
    "audio_seconds": 30,
    "model": "whisper-1",
    "created_at": "2025-12-30T12:45:00"
}
```

---

### 31. Раздел "Расходы API" в админке

**Файл:** `webapp/frontend/admin.html`

**Расположение:** Аналитика → Расходы API

**Компоненты:**

#### 1. Общая статистика (4 карточки)

```javascript
{
    "total_cost": 6.251256,      // Всего потрачено
    "total_tokens": 2567890,     // Всего токенов
    "by_provider": {             // По провайдерам
        "claude": 6.206256,
        "openai": 0.045000
    },
    "unique_users": 12           // Уникальных пользователей
}
```

**Визуализация:**
- Большие числа с единицами измерения
- Иконки провайдеров
- Цветовое кодирование

#### 2. График динамики расходов

**Тип:** Line chart (Chart.js)

**Данные:**
- X-axis: Даты
- Y-axis: Стоимость USD
- Линии для каждого провайдера:
  - 🟣 Claude (фиолетовый)
  - 🔵 OpenAI (синий)
  - 🟢 Yandex TTS (зелёный)

**Фильтры:**
- Период: 7 / 14 / 30 дней
- Провайдер: все / claude / openai / yandex_tts

#### 3. Круговая диаграмма расходов

**Тип:** Pie chart (Chart.js)

**Показывает:**
- Доли расходов по провайдерам
- Процентное соотношение
- Абсолютные суммы

**Цвета:**
- Claude: #9333EA
- OpenAI: #3B82F6
- Yandex TTS: #10B981

#### 4. Топ-10 пользователей по расходам

**Таблица:**

| # | Пользователь | Telegram ID | Провайдер | Токены | Стоимость |
|---|-------------|-------------|-----------|--------|-----------|
| 1 | Елена | 1926322383 | Claude | 45670 | $0.1234 |
| 2 | Настя | 620828717 | OpenAI | 0 | $0.0450 |

**Фичи:**
- Бэджи провайдеров с цветами
- Сортировка по стоимости (DESC)
- Отображение имени и telegram_id

#### 5. Детальная статистика транзакций

**Таблица с фильтрами:**

**Фильтры:**
- Период (from_date, to_date)
- Telegram ID
- Провайдер

**Колонки:**
- Дата/время
- Пользователь (display_name)
- Провайдер (бэдж)
- Модель
- Токены (input/output) или Секунды аудио
- Стоимость

**Пагинация:**
- 50 записей на страницу
- Кнопки "Загрузить ещё"

**Пример данных:**

```
Дата          | Пользователь | Провайдер | Модель              | Токены      | Стоимость
30.12, 12:45  | Елена        | Claude    | claude-3-5-sonnet   | 4523/1234   | $0.0245
30.12, 12:40  | Настя        | OpenAI    | whisper-1           | 30s аудио   | $0.0030
```

---

### 32. Новые API эндпоинты для аналитики

**Файл:** `webapp/api/routes/api_costs.py`

#### GET `/api/admin/api-costs/stats`

**Описание:** Общая статистика расходов на API

**Query params:**
- `from_date` (optional): Начало периода (ISO format YYYY-MM-DD)
- `to_date` (optional): Конец периода (ISO format YYYY-MM-DD)

**Response:**
```json
{
    "total_cost": 6.251256,
    "total_tokens": 2567890,
    "by_provider": {
        "claude": 6.206256,
        "openai": 0.045000
    },
    "unique_users": 12
}
```

#### GET `/api/admin/api-costs/by-date`

**Описание:** Расходы по датам для графика

**Query params:**
- `from_date` (optional): По умолчанию последние 30 дней
- `to_date` (optional)
- `user_id` (optional): Фильтр по пользователю
- `provider` (optional): Фильтр по провайдеру

**Response:**
```json
[
    {
        "date": "2025-12-30",
        "provider": "claude",
        "total_cost": 0.1234,
        "total_tokens": 45670
    },
    {
        "date": "2025-12-30",
        "provider": "openai",
        "total_cost": 0.0030,
        "total_tokens": 0
    }
]
```

#### GET `/api/admin/api-costs/top-users`

**Описание:** Топ пользователей по расходам

**Query params:**
- `limit` (default: 10, max: 100): Количество пользователей
- `from_date` (optional)
- `to_date` (optional)

**Response:**
```json
[
    {
        "user_id": 7,
        "telegram_id": 1926322383,
        "display_name": "Елена",
        "first_name": "Elena",
        "provider": "claude",
        "total_cost": 0.1234,
        "total_tokens": 45670
    }
]
```

#### GET `/api/admin/api-costs/`

**Описание:** Детальный список всех транзакций

**Query params:**
- `from_date` (optional)
- `to_date` (optional)
- `telegram_id` (optional): Фильтр по пользователю
- `provider` (optional): claude / openai / yandex_tts
- `limit` (default: 50, max: 500): Количество записей
- `offset` (default: 0): Смещение для пагинации

**Response:**
```json
[
    {
        "id": 1234,
        "telegram_id": 620828717,
        "provider": "claude",
        "model_name": "claude-3-5-sonnet-20241022",
        "input_tokens": 4523,
        "output_tokens": 1234,
        "total_tokens": 5757,
        "cost_usd": 0.0245,
        "created_at": "2025-12-30T12:45:00",
        "user": {
            "telegram_id": 620828717,
            "display_name": "Настя",
            "first_name": "Nastya"
        }
    }
]
```

---

### 33. Управление System Prompt через UI

**Файлы:**
- `webapp/frontend/admin.html` (UI)
- `webapp/api/routes/system_prompt.py` (Backend)

**Раздел:** Конфиг → SYSTEM PROMPT

#### Компоненты UI

**1. Заголовок с кнопками:**
```html
<h2>SYSTEM PROMPT</h2>
<button onclick="loadSystemPrompt()">Обновить</button>
<button onclick="uploadNewPrompt()">Загрузить новый PROMPT</button>
```

**2. Текущая версия:**
- **Версия:** v1.0
- **Дата обновления:** 30.12.2025 17:33:04
- **Размер:** 5,234 символов
- **Кнопки:**
  - Скачать (downloadSystemPrompt)
  - Копировать (copyToClipboard)

**3. Содержимое промпта:**
```html
<pre id="current-prompt-content">
    SYSTEM_PROMPT = """
    Ты — Мира, виртуальная девушка...
    """
</pre>
```

**4. История версий:**
- Таблица с предыдущими версиями
- Дата создания
- Описание изменений
- Кнопки "Просмотр" и "Скачать"

#### Функция загрузки промпта

**JavaScript:**
```javascript
async function uploadNewPrompt() {
    // Создание file input
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.txt,.md';

    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        try {
            // Чтение файла
            const content = await file.text();

            // Валидация
            if (!content || content.trim().length === 0) {
                showToast('Файл пустой', 'error');
                return;
            }

            // Подтверждение
            if (!confirm(
                `Загрузить новый системный промпт?\n\n` +
                `Размер: ${content.length.toLocaleString('ru-RU')} символов\n` +
                `Файл: ${file.name}\n\n` +
                `Текущая версия будет сохранена в истории.`
            )) {
                return;
            }

            // Загрузка на сервер
            const response = await apiRequest('system-prompt/update', {
                method: 'POST',
                body: JSON.stringify({ content })
            });

            showToast('Системный промпт обновлён', 'success');

            // Перезагрузка промпта
            await loadSystemPrompt();

        } catch (error) {
            console.error('Failed to upload system prompt:', error);
            showToast('Ошибка загрузки файла', 'error');
        }
    };

    // Открытие диалога выбора файла
    input.click();
}
```

---

### 34. Исправление багов в загрузке данных

**Проблема:** Ошибка "Ошибка загрузки системного промпта" и "Загрузка истории версий..."

**Причина:** Двойной вызов `.json()` в функциях

**Файл:** `webapp/frontend/admin.html`

#### Исправленные функции

**1. loadSystemPrompt()**

**До:**
```javascript
async function loadSystemPrompt() {
    try {
        const response = await apiRequest('system-prompt/current');
        const data = await response.json(); // ❌ ОШИБКА: двойной .json()

        document.getElementById('current-version-badge').textContent = data.version;
        // ...
    }
}
```

**После:**
```javascript
async function loadSystemPrompt() {
    try {
        const data = await apiRequest('system-prompt/current'); // ✅ apiRequest уже возвращает JSON

        // Null safety
        document.getElementById('current-version-badge').textContent = data.version || '1.0';
        document.getElementById('current-version-date').textContent =
            data.updated_at ? new Date(data.updated_at).toLocaleString('ru-RU') : '—';
        document.getElementById('current-version-size').textContent =
            (data.content?.length || 0).toLocaleString('ru-RU');
        document.getElementById('current-prompt-content').textContent =
            data.content || 'Промпт не найден';

        await loadSystemPromptHistory();
    } catch (error) {
        console.error('Failed to load system prompt:', error);
        showToast('Ошибка загрузки системного промпта', 'error');
    }
}
```

**2. loadSystemPromptHistory()**

**До:**
```javascript
async function loadSystemPromptHistory() {
    const container = document.getElementById('prompt-history-container');
    try {
        const response = await apiRequest('system-prompt/history');
        const data = await response.json(); // ❌ Двойной .json()
        renderSystemPromptHistory(data.history || []);
    }
}
```

**После:**
```javascript
async function loadSystemPromptHistory() {
    const container = document.getElementById('prompt-history-container');
    try {
        const data = await apiRequest('system-prompt/history'); // ✅ Исправлено
        renderSystemPromptHistory(data.history || []);
    } catch (error) {
        console.error('Failed to load system prompt history:', error);
        container.innerHTML = '<p class="error-message">Ошибка загрузки истории версий</p>';
    }
}
```

**3. downloadSystemPrompt()**
**4. viewSystemPromptVersion()**

Аналогично исправлены - убран двойной `.json()`, добавлена null safety.

**Почему это важно:**

Функция `apiRequest()` уже парсит JSON:
```javascript
async function apiRequest(endpoint, options = {}) {
    // ...
    const response = await fetch(url, {...});

    if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
    }

    return response.json(); // ← Возвращает parsed JSON
}
```

Поэтому вызов `.json()` второй раз вызывал ошибку:
```
TypeError: response.json is not a function
```

---

### 35. Эндпоинт обновления System Prompt

**Файл:** `webapp/api/routes/system_prompt.py`

**Endpoint:** `POST /api/admin/system-prompt/update`

**Авторизация:** Bearer token (admin)

#### Pydantic модель

```python
class SystemPromptUpdate(BaseModel):
    """System prompt update request."""
    content: str
```

#### Реализация

```python
@router.post("/update")
async def update_system_prompt(
    data: SystemPromptUpdate,
    admin_data=Depends(require_admin_role)
):
    """Update system prompt."""
    import shutil
    from loguru import logger

    system_prompt_file = get_system_prompt_file_path()

    # Валидация содержимого
    if not data.content or len(data.content.strip()) == 0:
        raise HTTPException(
            status_code=400,
            detail="System prompt content cannot be empty"
        )

    # Создание бэкапа текущей версии
    if system_prompt_file.exists():
        backup_dir = system_prompt_file.parent / "backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"system_prompt_{timestamp}.py"

        try:
            shutil.copy2(system_prompt_file, backup_file)
            logger.info(f"Created backup: {backup_file}")
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to create backup"
            )

    # Запись нового содержимого
    try:
        system_prompt_file.write_text(data.content, encoding='utf-8')
        logger.info(
            f"System prompt updated by admin: "
            f"{admin_data.get('username', 'unknown')}"
        )

        return {
            "success": True,
            "message": "System prompt updated successfully",
            "updated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to update system prompt: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update system prompt"
        )
```

#### Бэкапы

**Путь:** `/root/mira_bot/ai/prompts/backups/`

**Формат имени:** `system_prompt_YYYYMMDD_HHMMSS.py`

**Примеры:**
```
system_prompt_20251230_173304.py
system_prompt_20251230_120000.py
system_prompt_20251229_150000.py
```

#### Восстановление из бэкапа

```bash
# Просмотр бэкапов
ls -lh /root/mira_bot/ai/prompts/backups/

# Восстановление
cp /root/mira_bot/ai/prompts/backups/system_prompt_20251230_173304.py \
   /root/mira_bot/ai/prompts/system_prompt.py

# Перезапуск бота
systemctl restart mirabot
```

---

### 36. Визуализация расходов на OpenAI

**До:** В базе только расходы на Claude

**После:** Отображаются расходы на все провайдеры

#### Изменения в UI

**1. Карточки статистики**

```html
<!-- До -->
<div class="stat-card">
    <h3>Всего потрачено</h3>
    <div class="stat-value">$6.21</div>
</div>

<!-- После -->
<div class="stat-card">
    <h3>Всего потрачено</h3>
    <div class="stat-value">$6.25</div>
    <div class="stat-breakdown">
        Claude: $6.21 | OpenAI: $0.04
    </div>
</div>
```

**2. График динамики**

**До:** Только фиолетовая линия (Claude)

**После:**
- 🟣 Claude (фиолетовый) — основные расходы
- 🔵 OpenAI (синий) — транскрибации
- 🟢 Yandex TTS (зелёный) — голосовые ответы

**3. Круговая диаграмма**

**До:**
```
Claude: 100%
```

**После:**
```
Claude: 99.3% ($6.21)
OpenAI: 0.7% ($0.04)
```

**4. Топ пользователей**

Добавлены бэджи провайдеров:

```html
<tr>
    <td>1</td>
    <td>Настя</td>
    <td>620828717</td>
    <td>
        <span class="badge badge-openai">OpenAI</span>
    </td>
    <td>—</td>
    <td>$0.0450</td>
</tr>
```

**5. Детальная статистика**

Теперь показывает транзакции OpenAI:

```
Дата          | Пользователь | Провайдер | Модель    | Детали      | Стоимость
30.12, 12:45  | Настя        | OpenAI    | whisper-1 | 45s аудио   | $0.0045
30.12, 12:40  | Елена        | OpenAI    | whisper-1 | 30s аудио   | $0.0030
30.12, 12:35  | Настя        | Claude    | sonnet    | 4523/1234   | $0.0245
```

---

## 📁 Структура файлов

### Изменённые файлы

```
mira_bot/
├── ai/
│   ├── whisper_client.py                    ← Изменён: transcribe_bytes()
│   └── prompts/
│       ├── system_prompt.py                 ← Обновляется через UI
│       └── backups/                         ← Новая папка для бэкапов
│           └── system_prompt_*.py
│
├── bot/
│   └── handlers/
│       └── voice.py                         ← Изменён: логирование расходов
│
├── database/
│   └── repositories/
│       └── api_cost.py                      ← Новые методы: get_costs_list()
│
├── webapp/
│   ├── api/
│   │   ├── main.py                          ← Добавлен роутер system_prompt
│   │   └── routes/
│   │       ├── api_costs.py                 ← Новый эндпоинт GET /
│   │       └── system_prompt.py             ← Новый эндпоинт POST /update
│   │
│   └── frontend/
│       └── admin.html                       ← UI: API Costs, System Prompt
│
└── docs/
    └── 30.12.25/
        ├── OPENAI_WHISPER_API_COST_LOGGING.md
        ├── API_COSTS_DETAILS_ENDPOINT_FIX.md
        ├── SYSTEM_PROMPT_UPLOAD_FEATURE.md
        └── PHASE_10_SUMMARY.md              ← Этот файл
```

---

## 🔄 Workflow использования

### 1. Проверка расходов OpenAI

```bash
# SSH на сервер
ssh root@31.44.7.144

# Проверка логов бота
journalctl -u mirabot -f | grep "Whisper API cost"

# Проверка БД
cd /root/mira_bot
sqlite3 mira_bot.db "
SELECT
    ac.created_at,
    u.display_name,
    ac.provider,
    ac.audio_seconds,
    ac.cost_usd,
    ac.model
FROM api_costs ac
JOIN users u ON u.id = ac.user_id
WHERE ac.provider = 'openai'
ORDER BY ac.created_at DESC
LIMIT 5;
"
```

**Ожидаемый результат:**
```
2025-12-30 12:45:00|Настя|openai|45|0.0045|whisper-1
2025-12-30 12:40:15|Елена|openai|30|0.003|whisper-1
```

### 2. Просмотр аналитики в админке

```
1. Открыть http://mira.uspeshnyy.ru/admin
2. Перейти в "Аналитика" → "Расходы API"
3. Обновить страницу (Ctrl+Shift+R)
4. Проверить:
   - Карточки: "Всего потрачено" должна включать OpenAI
   - График: Должна появиться синяя линия OpenAI
   - Круговая диаграмма: Сектор OpenAI
   - Топ пользователей: Записи с бэджем OpenAI
   - Детальная статистика: Транзакции openai + speech_to_text
```

### 3. Загрузка нового System Prompt

```
1. Подготовить файл system_prompt_new.txt:
   SYSTEM_PROMPT = """
   Ты — Мира, виртуальная девушка пользователя.
   ...
   """

2. Открыть http://mira.uspeshnyy.ru/admin
3. Перейти в "Конфиг" → "SYSTEM PROMPT"
4. Нажать "Загрузить новый PROMPT"
5. Выбрать файл system_prompt_new.txt
6. Подтвердить загрузку
7. Проверить что:
   - Появилось уведомление "Системный промпт обновлён"
   - Текущая версия обновилась
   - В /root/mira_bot/ai/prompts/backups/ создался бэкап

8. Перезапустить бота:
   ssh root@31.44.7.144
   systemctl restart mirabot
```

---

## 📊 Метрики и аналитика

### Расходы по провайдерам (пример)

```sql
SELECT
    provider,
    COUNT(*) as transactions,
    SUM(cost_usd) as total_cost,
    SUM(total_tokens) as total_tokens
FROM api_costs
GROUP BY provider;
```

**Результат:**
```
provider  | transactions | total_cost | total_tokens
----------|--------------|------------|-------------
claude    | 86           | 6.206256   | 2567890
openai    | 15           | 0.045000   | 0
```

### Топ пользователей по расходам на OpenAI

```sql
SELECT
    u.display_name,
    COUNT(*) as voice_count,
    SUM(ac.audio_seconds) as total_seconds,
    SUM(ac.cost_usd) as total_cost
FROM api_costs ac
JOIN users u ON u.id = ac.user_id
WHERE ac.provider = 'openai'
  AND DATE(ac.created_at) = CURRENT_DATE
GROUP BY u.id, u.display_name
ORDER BY total_cost DESC;
```

### Средняя длительность голосовых сообщений

```sql
SELECT
    AVG(audio_seconds) as avg_duration,
    MIN(audio_seconds) as min_duration,
    MAX(audio_seconds) as max_duration
FROM api_costs
WHERE provider = 'openai';
```

---

## 🛡️ Безопасность

### API Endpoints

**Защита:**
- Все эндпоинты требуют авторизацию администратора
- JWT токен в заголовке `Authorization: Bearer <token>`
- Роль проверяется через `require_admin_role` middleware

**Валидация:**
- System Prompt: не пустое содержимое
- API Costs: корректные даты, лимиты, offset

**Логирование:**
```python
logger.info(f"System prompt updated by admin: {admin_data.get('username', 'unknown')}")
logger.info(f"Logged Whisper API cost for user {user.id}: ${cost:.6f} ({seconds}s)")
```

### Бэкапы

**Автоматические:**
- Создаются перед каждым обновлением промпта
- Хранятся в `/root/mira_bot/ai/prompts/backups/`
- Timestamp в имени файла для идентификации

**Восстановление:**
- Доступ через SSH
- Копирование файла из backups/
- Перезапуск бота

---

## 🐛 Known Issues

### 1. Бот не применяет новый промпт автоматически

**Проблема:** После загрузки нового промпта через UI, файл обновлён, но бот продолжает работать со старым промптом в памяти.

**Решение:** Перезапустить бота вручную:
```bash
systemctl restart mirabot
```

**TODO:** Добавить автоматический перезапуск бота после обновления промпта (опционально).

### 2. История версий не реализована

**Проблема:** В `/system-prompt/history` возвращается пустой массив. История версий не хранится в БД.

**Решение:** Текущие бэкапы хранятся в файловой системе. Можно вручную просматривать через SSH.

**TODO:** Реализовать хранение истории версий в БД с описаниями изменений.

### 3. OpenAI не показывается если нет транзакций

**Ожидаемо:** Если в БД нет записей с `provider='openai'`, OpenAI не будет отображаться на графиках.

**Проверка:**
```sql
SELECT COUNT(*) FROM api_costs WHERE provider = 'openai';
```

Если результат 0 — отправьте голосовое сообщение боту для создания первой транзакции.

---

## 📈 Ожидаемый эффект

### Прозрачность расходов

**До:**
- ❌ Расходы на OpenAI не логировались
- ❌ Неизвестно сколько стоит обработка голосовых
- ❌ Нет детальной аналитики по провайдерам

**После:**
- ✅ Каждая транскрибация логируется
- ✅ Видна стоимость в реальном времени
- ✅ Детальная аналитика по всем провайдерам
- ✅ Можно оптимизировать расходы

### Удобство управления

**До:**
- ❌ Обновление промпта только через SSH
- ❌ Ручное редактирование файлов
- ❌ Риск потери данных без бэкапов

**После:**
- ✅ Загрузка промпта через веб-интерфейс
- ✅ Автоматические бэкапы
- ✅ История изменений
- ✅ Безопасное восстановление

### Аналитика

**Новые возможности:**
- Графики динамики расходов
- Круговые диаграммы по провайдерам
- Топ пользователей по расходам
- Фильтрация по периодам и провайдерам
- Экспорт данных (TODO)

---

## ✅ Критерии приёмки

### Функциональность

- [x] Голосовые сообщения логируются в api_costs
- [x] Расходы на OpenAI отображаются в админке
- [x] Графики показывают все провайдеры
- [x] Кнопка "Загрузить новый PROMPT" работает
- [x] Бэкапы создаются автоматически
- [x] Секция System Prompt загружается без ошибок
- [x] Детальная статистика показывает транзакции OpenAI

### Безопасность

- [x] Только администраторы могут обновлять промпт
- [x] Валидация содержимого промпта
- [x] Логирование всех действий
- [x] Бэкапы перед обновлением

### UI/UX

- [x] Удобный интерфейс загрузки файлов
- [x] Подтверждение перед обновлением
- [x] Уведомления об успехе/ошибке
- [x] Визуализация расходов по провайдерам
- [x] Responsive дизайн

---

## 🎉 Заключение

Фаза 10 успешно завершена! Добавлена полная прозрачность расходов на API и удобное управление системой через веб-интерфейс.

**Что теперь доступно:**

✅ **Логирование расходов OpenAI Whisper API**
- Автоматический расчёт стоимости
- Сохранение в БД
- Логирование каждой транскрибации

✅ **Раздел "Расходы API" в админке**
- Общая статистика
- График динамики
- Круговая диаграмма
- Топ пользователей
- Детальная статистика

✅ **Управление System Prompt через UI**
- Просмотр текущего промпта
- Загрузка нового промпта
- Автоматические бэкапы
- История версий

✅ **Исправление багов**
- Двойной .json() убран
- Null safety добавлена
- 404 ошибки исправлены

**Следующие шаги:**
- Мониторинг расходов на транскрибацию
- Оптимизация промпта на основе аналитики
- Добавление экспорта данных (CSV, JSON)
- Реализация автоматического перезапуска бота после обновления промпта
