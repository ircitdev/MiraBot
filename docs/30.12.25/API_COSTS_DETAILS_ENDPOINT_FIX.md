# Исправление эндпоинта детальной статистики API

**Дата:** 30.12.2025
**Проблема:** Ошибка загрузки детальной статистики (404 Not Found)

## 🔍 Причина

При загрузке раздела "Расходы API" появлялась ошибка:

```
Ошибка загрузки детальной статистики
```

**Логи сервера:**
```
INFO: "GET /api/admin/api-costs?from_date=2025-11-30&to_date=2025-12-30&limit=50&offset=0 HTTP/1.0" 404 Not Found
```

### Что происходило:

Функция `loadApiCostsDetails()` в [admin.html](webapp/frontend/admin.html) делала запрос к эндпоинту:
```
GET /api/admin/api-costs?from_date=...&to_date=...&limit=50&offset=0
```

Но такого эндпоинта не было! В [api_costs.py](webapp/api/routes/api_costs.py) были только:
- `/api-costs/users/summary` - сводка по пользователям
- `/api-costs/users/{telegram_id}` - расходы конкретного пользователя
- `/api-costs/stats` - общая статистика
- `/api-costs/by-date` - расходы по датам для графика
- `/api-costs/top-users` - топ пользователей

**Не было эндпоинта для получения списка всех транзакций с деталями.**

## ✅ Исправление

### 1. Добавлен эндпоинт `/api-costs/`

**Файл:** `webapp/api/routes/api_costs.py`

```python
@router.get("/")
async def get_api_costs_list(
    from_date: Optional[str] = Query(None, description="Начало периода (ISO format YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Конец периода (ISO format YYYY-MM-DD)"),
    telegram_id: Optional[int] = Query(None, description="Фильтр по telegram_id пользователя"),
    provider: Optional[str] = Query(None, description="Фильтр по провайдеру (claude, yandex_tts, etc.)"),
    limit: int = Query(50, ge=1, le=500, description="Количество записей"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    admin_data: dict = Depends(get_current_admin)
) -> List[dict]:
    """
    Получить список всех расходов на API с деталями.
    """
    repo = ApiCostRepository()

    # Парсинг дат
    from_datetime = None
    to_datetime = None
    if from_date:
        from_datetime = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
    if to_date:
        to_datetime = datetime.fromisoformat(to_date.replace('Z', '+00:00'))

    costs = await repo.get_costs_list(
        from_date=from_datetime,
        to_date=to_datetime,
        telegram_id=telegram_id,
        provider=provider,
        limit=limit,
        offset=offset
    )

    return costs
```

**Параметры запроса:**
- `from_date` - начало периода (опционально)
- `to_date` - конец периода (опционально)
- `telegram_id` - фильтр по пользователю (опционально)
- `provider` - фильтр по провайдеру (опционально)
- `limit` - количество записей (по умолчанию 50, макс 500)
- `offset` - смещение для пагинации (по умолчанию 0)

**Возвращает:**
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
        "created_at": "2025-12-30T05:39:12",
        "user": {
            "telegram_id": 620828717,
            "display_name": "Настя",
            "first_name": "Настя"
        }
    }
]
```

### 2. Добавлен метод `get_costs_list()` в репозиторий

**Файл:** `database/repositories/api_cost.py`

```python
async def get_costs_list(
    self,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    telegram_id: Optional[int] = None,
    provider: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict]:
    """
    Получить список всех расходов с деталями.
    """
    async with get_session_context() as session:
        query = select(
            ApiCost.id,
            ApiCost.user_id,
            ApiCost.provider,
            ApiCost.model.label('model_name'),
            ApiCost.input_tokens,
            ApiCost.output_tokens,
            ApiCost.total_tokens,
            ApiCost.cost_usd,
            ApiCost.created_at,
            User.telegram_id,
            User.display_name,
            User.first_name
        ).join(User, User.id == ApiCost.user_id)

        conditions = []
        if from_date:
            conditions.append(ApiCost.created_at >= from_date)
        if to_date:
            conditions.append(ApiCost.created_at <= to_date)
        if telegram_id:
            conditions.append(User.telegram_id == telegram_id)
        if provider:
            conditions.append(ApiCost.provider == provider)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(desc(ApiCost.created_at)).limit(limit).offset(offset)

        result = await session.execute(query)

        return [
            {
                'id': row.id,
                'telegram_id': row.telegram_id,
                'provider': row.provider,
                'model_name': row.model_name,
                'input_tokens': row.input_tokens,
                'output_tokens': row.output_tokens,
                'total_tokens': row.total_tokens or 0,
                'cost_usd': float(row.cost_usd),
                'created_at': row.created_at.isoformat() if row.created_at else None,
                'user': {
                    'telegram_id': row.telegram_id,
                    'display_name': row.display_name,
                    'first_name': row.first_name
                }
            }
            for row in result
        ]
```

**Что делает:**
- Загружает записи из таблицы `api_costs` с JOIN к `users`
- Фильтрует по датам, telegram_id, провайдеру
- Сортирует по дате создания (DESC)
- Применяет пагинацию (limit + offset)
- Возвращает список с полными данными о транзакциях

### 3. Исправлен метод `get_top_users_by_cost()`

**Проблема:** Не возвращал `first_name` и `provider`

**Было:**
```python
query = select(
    User.id,
    User.telegram_id,
    User.display_name,
    func.sum(ApiCost.cost_usd).label('total_cost'),
    func.sum(ApiCost.total_tokens).label('total_tokens')
).join(ApiCost, User.id == ApiCost.user_id)

query = query.group_by(
    User.id, User.telegram_id, User.display_name
)
```

**Стало:**
```python
query = select(
    User.id,
    User.telegram_id,
    User.display_name,
    User.first_name,                    # Добавлено
    ApiCost.provider,                   # Добавлено
    func.sum(ApiCost.cost_usd).label('total_cost'),
    func.sum(ApiCost.total_tokens).label('total_tokens')
).join(ApiCost, User.id == ApiCost.user_id)

query = query.group_by(
    User.id, User.telegram_id, User.display_name, User.first_name, ApiCost.provider
)
```

**Возвращает:**
```python
{
    'user_id': row.id,
    'telegram_id': row.telegram_id,
    'display_name': row.display_name,
    'first_name': row.first_name,      # Теперь есть
    'provider': row.provider,           # Теперь есть
    'total_cost': float(row.total_cost),
    'total_tokens': int(row.total_tokens) if row.total_tokens else 0
}
```

## 🤔 Почему OpenAI не показывается?

В базе данных нет записей об использовании OpenAI API:

```sql
SELECT provider, COUNT(*), SUM(cost_usd) FROM api_costs GROUP BY provider;
-- Результат:
-- claude|86|6.206256
```

**Вывод:** OpenAI API просто не использовался, поэтому данных нет.

Когда появятся расходы на OpenAI:
- Они автоматически появятся на графиках
- Будет показана круговая диаграмма с долей OpenAI
- В таблице топ-пользователей появятся записи с бэджем OpenAI

## 📋 Что было сделано

1. ✅ Добавлен эндпоинт `GET /api-costs/` для получения списка транзакций
2. ✅ Добавлен метод `get_costs_list()` в ApiCostRepository
3. ✅ Исправлен метод `get_top_users_by_cost()` - добавлены first_name и provider
4. ✅ Файлы загружены на сервер
5. ✅ Веб-сервер перезапущен

## 🔍 Проверка

### Через браузер:

1. Откройте админ-панель: http://mira.uspeshnyy.ru/admin
2. Перейдите в "Аналитика" → "Расходы API"
3. Нажмите Ctrl+Shift+R для обновления кэша
4. Должна загрузиться детальная статистика с таблицей транзакций

### Через curl:

```bash
curl -H "Authorization: Bearer {token}" \
     "http://mira.uspeshnyy.ru/api/admin/api-costs?from_date=2025-11-30&to_date=2025-12-30&limit=10"
```

**Ожидаемый результат:**
```json
[
    {
        "id": 86,
        "telegram_id": 1392513515,
        "provider": "claude",
        "model_name": "claude-3-5-sonnet-20241022",
        "input_tokens": 6873,
        "output_tokens": 2713,
        "total_tokens": 9586,
        "cost_usd": 0.03591,
        "created_at": "2025-12-30T08:09:12.123456",
        "user": {
            "telegram_id": 1392513515,
            "display_name": "Александр",
            "first_name": "Aleksandr"
        }
    }
]
```

## 📄 Файлы изменений

**1. webapp/api/routes/api_costs.py**
- Строки 243-288: Добавлен эндпоинт `GET /`

**2. database/repositories/api_cost.py**
- Строки 312-348: Исправлен `get_top_users_by_cost()` (добавлены first_name и provider)
- Строки 350-422: Добавлен `get_costs_list()`

## 🎉 Итог

✅ **Детальная статистика API теперь работает!**

**Что исправлено:**
- Добавлен эндпоинт `/api-costs/` для получения списка транзакций
- Таблица "Детальная статистика" теперь загружается корректно
- Топ-10 пользователей показывает правильные имена и провайдеры

**Почему OpenAI не виден:**
- В базе данных нет записей об использовании OpenAI API
- Как только появятся расходы на OpenAI, они автоматически появятся на всех графиках
