# Исправление бага в API costs - график расходов

**Дата:** 30.12.2025
**Проблема:** График расходов API не загружался в админ-панели (ошибка "Ошибка загрузки графика расходов API")

## Причина

В методе `get_costs_by_date()` репозитория `ApiCostRepository` была ошибка:

**Файл:** `database/repositories/api_cost.py:200`

```python
# Было (ОШИБКА):
'date': row.date.isoformat() if row.date else None,

# Стало (ИСПРАВЛЕНО):
'date': str(row.date) if row.date else None,
```

### Почему это была ошибка?

SQLAlchemy функция `func.date()` возвращает строку в формате `YYYY-MM-DD`, а не объект `date`. Попытка вызвать `.isoformat()` на строке приводила к ошибке:

```
AttributeError: 'str' object has no attribute 'isoformat'
```

## Исправление

Изменена строка 200 в файле `database/repositories/api_cost.py`:
- Убран вызов `.isoformat()`
- Добавлено явное приведение к строке через `str()`

## Проверка

После исправления все эндпоинты работают корректно:

### 1. GET /api/admin/api-costs/stats
```json
{
  "total_cost": 0.002468,
  "total_tokens": 600,
  "by_provider": {"claude": 0.002468},
  "unique_users": 1
}
```

### 2. GET /api/admin/api-costs/by-date
```json
[
  {
    "date": "2025-12-29",
    "provider": "claude",
    "total_cost": 0.002468,
    "total_tokens": 600
  }
]
```

### 3. GET /api/admin/api-costs/users/summary
```json
[
  {
    "user_id": 1,
    "telegram_id": 65876198,
    "display_name": "Мира",
    "total_cost": 0.002468
  }
]
```

## Результат

График расходов API теперь корректно загружается и отображает данные:
- ✅ Статистика сверху (всего потрачено, токены, пользователи)
- ✅ График по датам с разбивкой по провайдерам
- ✅ Кнопки переключения периода (7/30/90 дней)

## Файлы изменений

- `database/repositories/api_cost.py` (строка 200) - исправлен баг с `.isoformat()`

## Тестирование

Создан тестовый скрипт `test_api_endpoints.py` для проверки данных:
```bash
python test_api_endpoints.py
```

Все тесты проходят успешно.
