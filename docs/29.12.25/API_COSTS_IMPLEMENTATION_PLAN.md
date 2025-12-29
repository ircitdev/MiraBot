# План реализации: Трекинг API расходов и улучшение таблицы пользователей

**Дата:** 29.12.2025
**Статус:** 📋 План

---

## 📊 Общая картина

### Цели:
1. ✅ Добавить логирование критических операций (ВЫПОЛНЕНО)
2. 🔄 Добавить трекинг API расходов (Claude, Yandex, OpenAI)
3. 🔄 Улучшить таблицу пользователей (адаптивность + колонка API)
4. 🔄 Создать график расходов API в аналитике
5. 🔄 Логирование медиа-событий и милестоунов

---

## 🗂️ Этап 1: Модель для хранения API расходов

### 1.1. Создать модель `ApiCost`

**Файл:** `database/models.py`

```python
class ApiCost(Base):
    """
    Трекинг расходов на API (Claude, Yandex, OpenAI).
    """
    __tablename__ = "api_costs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)  # Для быстрого поиска

    # Тип API
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # 'claude', 'yandex', 'openai'
    model: Mapped[str] = mapped_column(String(50), nullable=False)  # 'claude-sonnet-4', 'gpt-4', etc

    # Использование
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)

    # Стоимость
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)

    # Тип операции
    operation_type: Mapped[str] = mapped_column(String(50))  # 'chat', 'report', 'tts', 'stt'

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)

    # Связи
    user: Mapped["User"] = relationship("User")

    # Индексы
    __table_args__ = (
        Index("idx_api_cost_user", "user_id"),
        Index("idx_api_cost_telegram", "telegram_id"),
        Index("idx_api_cost_date", "created_at"),
        Index("idx_api_cost_provider", "provider"),
    )
```

### 1.2. Создать миграцию

**Файл:** `database/migrations/versions/20251229_add_api_costs.py`

---

## 🔧 Этап 2: Репозиторий для API расходов

**Файл:** `database/repositories/api_cost.py`

```python
class ApiCostRepository:
    """Репозиторий для работы с API расходами."""

    async def create(
        self,
        user_id: int,
        telegram_id: int,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        operation_type: str = "chat"
    ) -> ApiCost:
        """Записать использование API."""

    async def get_user_total_cost(self, user_id: int) -> float:
        """Получить общую стоимость по пользователю."""

    async def get_costs_by_date(
        self,
        from_date: datetime,
        to_date: datetime,
        provider: Optional[str] = None
    ) -> List[ApiCost]:
        """Получить расходы за период."""

    async def get_total_by_provider(self) -> dict:
        """Получить общую сумму по каждому провайдеру."""
```

---

## 💰 Этап 3: Интеграция трекинга в существующий код

### 3.1. Claude API (основной)

**Файл:** `ai/claude_client.py`

После каждого вызова `client.messages.create()`:

```python
# Записываем расход
cost_repo = ApiCostRepository()
await cost_repo.create(
    user_id=user.id,
    telegram_id=user.telegram_id,
    provider="claude",
    model="claude-sonnet-4-20250514",
    input_tokens=response.usage.input_tokens,
    output_tokens=response.usage.output_tokens,
    cost_usd=calculate_claude_cost(response.usage),
    operation_type="chat"
)
```

**Функция расчёта стоимости Claude:**

```python
def calculate_claude_cost(usage) -> float:
    """
    Расчёт стоимости для Claude Sonnet 4.
    Input: $3 per million tokens
    Output: $15 per million tokens
    """
    input_cost = (usage.input_tokens / 1_000_000) * 3.0
    output_cost = (usage.output_tokens / 1_000_000) * 15.0
    return round(input_cost + output_cost, 6)
```

### 3.2. Yandex TTS/STT

**Файлы:**
- `services/tts_yandex.py`
- `services/stt_service.py`

После каждого вызова:

```python
# Yandex SpeechKit стоит ~$0.0015 за минуту
# Для TTS: ~15 символов/сек, ~900 символов/мин
cost_per_char = 0.0015 / 900

await cost_repo.create(
    user_id=user.id,
    telegram_id=user.telegram_id,
    provider="yandex",
    model="tts-premium",
    input_tokens=len(text),  # Символы для TTS
    output_tokens=0,
    cost_usd=len(text) * cost_per_char,
    operation_type="tts"
)
```

### 3.3. OpenAI (если используется)

**Файлы:** Поиск по кодовой базе `import openai`

```python
# GPT-4o: $2.50 input, $10 output per million
```

---

## 🌐 Этап 4: Backend API

**Файл:** `webapp/api/routes/stats.py`

Добавить новые эндпоинты:

```python
@router.get("/api/costs/by-user")
async def get_costs_by_user(
    admin_data: dict = Depends(get_current_admin)
) -> List[UserCostSummary]:
    """
    Получить расходы API по каждому пользователю.

    Returns:
        [
            {
                "telegram_id": 123456,
                "name": "Анна",
                "total_cost_usd": 1.23,
                "total_tokens": 50000,
                "claude_cost": 1.00,
                "yandex_cost": 0.20,
                "openai_cost": 0.03
            }
        ]
    """

@router.get("/api/costs/timeline")
async def get_costs_timeline(
    from_date: str,
    to_date: str,
    group_by: str = "day",  # day, week, month
    admin_data: dict = Depends(get_current_admin)
) -> List[CostTimelinePoint]:
    """
    Получить расходы по датам для графика.

    Returns:
        [
            {
                "date": "2025-12-25",
                "claude_cost": 2.50,
                "yandex_cost": 0.30,
                "openai_cost": 0.10,
                "total_cost": 2.90,
                "total_tokens": 120000
            }
        ]
    """
```

---

## 🎨 Этап 5: Frontend - Таблица пользователей

**Файл:** `webapp/frontend/admin.html`

### 5.1. Добавить адаптивность

```css
.table-container {
    background: var(--md-sys-color-surface);
    border-radius: 12px;
    overflow-x: auto;  /* Горизонтальная прокрутка */
    overflow-y: visible;
    box-shadow: var(--md-sys-elevation-1);

    /* Улучшенная прокрутка для touch устройств */
    -webkit-overflow-scrolling: touch;
}

/* Фиксированная ширина таблицы на мобильных */
@media (max-width: 768px) {
    .table-container table {
        min-width: 900px;  /* Минимальная ширина для прокрутки */
    }

    .table-container th,
    .table-container td {
        white-space: nowrap;  /* Текст не переносится */
        padding: 8px;  /* Уменьшенные отступы */
    }
}
```

### 5.2. Добавить колонку API

```html
<th class="sortable" data-sort="api_cost" onclick="sortTable('api_cost')">
    API $
    <span class="material-icons sort-icon">unfold_more</span>
</th>
```

### 5.3. Обновить renderUsers()

```javascript
async function renderUsers(users) {
    // Загружаем стоимость API для каждого пользователя
    const costs = await apiRequest('/costs/by-user');
    const costMap = {};
    costs.forEach(c => costMap[c.telegram_id] = c.total_cost_usd);

    const tbody = document.getElementById('users-table-body');
    tbody.innerHTML = users.map(user => {
        const apiCost = costMap[user.telegram_id] || 0;

        return `
            <tr>
                <td><input type="checkbox" class="user-checkbox" value="${user.telegram_id}"></td>
                <td>${user.telegram_id}</td>
                <td>${user.display_name || user.first_name || '-'}</td>
                <td>@${user.username || '-'}</td>
                <td>${renderSubscriptionBadge(user.subscription_plan)}</td>
                <td>${user.total_messages || 0}</td>
                <td>${apiCost > 0 ? `$${apiCost.toFixed(3)}` : '-'}</td>
                <td>${formatDate(user.last_active_at)}</td>
                <td>${renderActions(user)}</td>
            </tr>
        `;
    }).join('');
}
```

---

## 📈 Этап 6: График расходов API

**Файл:** `webapp/frontend/admin.html` (вкладка Аналитика)

### 6.1. HTML структура

```html
<!-- В разделе Аналитика -->
<div class="analytics-section">
    <h3>Расходы на API</h3>

    <div class="date-range-picker">
        <input type="date" id="api-costs-from" />
        <input type="date" id="api-costs-to" />
        <button onclick="loadApiCostsChart()">Применить</button>
    </div>

    <canvas id="api-costs-chart" width="400" height="200"></canvas>

    <div class="cost-summary">
        <div class="cost-card">
            <span class="material-icons">psychology</span>
            <div>
                <div class="cost-label">Claude</div>
                <div class="cost-value" id="claude-total">$0.00</div>
            </div>
        </div>
        <div class="cost-card">
            <span class="material-icons">record_voice_over</span>
            <div>
                <div class="cost-label">Yandex</div>
                <div class="cost-value" id="yandex-total">$0.00</div>
            </div>
        </div>
        <div class="cost-card">
            <span class="material-icons">smart_toy</span>
            <div>
                <div class="cost-label">OpenAI</div>
                <div class="cost-value" id="openai-total">$0.00</div>
            </div>
        </div>
    </div>
</div>
```

### 6.2. JavaScript для графика (использовать Chart.js)

```javascript
async function loadApiCostsChart() {
    const fromDate = document.getElementById('api-costs-from').value;
    const toDate = document.getElementById('api-costs-to').value;

    const data = await apiRequest(`/costs/timeline?from_date=${fromDate}&to_date=${toDate}`);

    const chart = new Chart(document.getElementById('api-costs-chart'), {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets: [
                {
                    label: 'Claude',
                    data: data.map(d => d.claude_cost),
                    borderColor: '#4285f4',
                    backgroundColor: 'rgba(66, 133, 244, 0.1)'
                },
                {
                    label: 'Yandex',
                    data: data.map(d => d.yandex_cost),
                    borderColor: '#ea4335',
                    backgroundColor: 'rgba(234, 67, 53, 0.1)'
                },
                {
                    label: 'OpenAI',
                    data: data.map(d => d.openai_cost),
                    borderColor: '#10a37f',
                    backgroundColor: 'rgba(16, 163, 127, 0.1)'
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                title: { display: true, text: 'API Costs Over Time' }
            },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Cost (USD)' } }
            }
        }
    });
}
```

---

## 🎯 Этап 7: Логирование медиа-событий

### 7.1. Первое фото пользователя

**Файл:** `bot/handlers/message.py` (функция `handle_photo`)

После успешной отправки ответа:

```python
# Проверяем, было ли это первое фото
first_photo_logs = await admin_log_repo.get_by_action_and_resource(
    action="user_first_photo_sent",
    resource_id=user.telegram_id
)

if not first_photo_logs:
    await admin_log_repo.create(
        admin_user_id=None,
        action="user_first_photo_sent",
        resource_type="user",
        resource_id=user.telegram_id,
        details={"display_name": user.display_name},
        success=True
    )
```

### 7.2. Первое голосовое

**Файл:** `bot/handlers/voice.py`

Аналогично:

```python
# action="user_first_voice_sent"
```

### 7.3. Милестоуны сообщений

**Файл:** `bot/handlers/message.py` (после сохранения сообщения)

```python
# Получаем общее количество сообщений пользователя
total_messages = await conversation_repo.count_by_user(user.id)

# Проверяем милестоуны
milestones = [50, 100, 300, 1000]
for milestone in milestones:
    if total_messages == milestone:
        # Проверяем, не логировали ли уже
        existing = await admin_log_repo.get_by_action_and_resource(
            action=f"user_messages_milestone_{milestone}",
            resource_id=user.telegram_id
        )

        if not existing:
            await admin_log_repo.create(
                admin_user_id=None,
                action=f"user_messages_milestone_{milestone}",
                resource_type="user",
                resource_id=user.telegram_id,
                details={
                    "display_name": user.display_name,
                    "total_messages": total_messages
                },
                success=True
            )
            break  # Только один милестоун за раз
```

---

## 📦 Список файлов для изменения

### Backend:
1. `database/models.py` - модель ApiCost
2. `database/migrations/versions/20251229_add_api_costs.py` - миграция
3. `database/repositories/api_cost.py` - новый репозиторий
4. `ai/claude_client.py` - трекинг Claude
5. `services/tts_yandex.py` - трекинг Yandex TTS
6. `services/stt_service.py` - трекинг Yandex STT
7. `webapp/api/routes/stats.py` - новые эндпоинты
8. `webapp/api/routes/admin.py` - обновить список пользователей
9. `bot/handlers/message.py` - логирование событий
10. `bot/handlers/voice.py` - логирование голосовых

### Frontend:
11. `webapp/frontend/admin.html` - таблица, график, стили

---

## ⏱️ Оценка времени

- **Этап 1-2:** Модель и репозиторий - 1 час
- **Этап 3:** Интеграция трекинга - 2 часа (много мест)
- **Этап 4:** Backend API - 1 час
- **Этап 5:** Таблица пользователей - 1 час
- **Этап 6:** График расходов - 2 часа
- **Этап 7:** Логирование событий - 1.5 часа
- **Тестирование:** 1.5 часа

**Итого:** ~10 часов работы

---

## 🚀 Приоритеты для быстрого старта

Если нужно сделать быстро (2-3 часа):

1. ✅ Адаптивность таблицы (CSS) - 15 минут
2. ✅ Модель ApiCost - 30 минут
3. ✅ Трекинг в Claude (основной API) - 30 минут
4. ✅ Backend эндпоинт для расходов - 30 минут
5. ✅ Колонка API в таблице - 30 минут
6. ✅ Базовый график - 45 минут

Это даст основную функциональность без полного покрытия.

---

**Готов начать реализацию?** Скажите с какого этапа начать, и я приступлю к кодированию.
