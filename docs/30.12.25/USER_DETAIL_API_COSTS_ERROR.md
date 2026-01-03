# Ошибка загрузки API расходов на странице пользователя

**Дата:** 30.12.2025
**Проблема:** На странице деталей пользователя показывается "API Расходы: Ошибка загрузки"

## Описание проблемы

При открытии модального окна с детальной информацией о пользователе (например, "Лиза", telegram_id: 1392513515), в разделе "API Расходы" отображается сообщение об ошибке вместо данных о расходах.

## Причины ошибки

Ошибка возникает в файле [admin.html:8024-8026](../webapp/frontend/admin.html#L8024-L8026) при выполнении запроса к эндпоинту:

```javascript
const apiCosts = await apiRequest(`api-costs/users/${user.telegram_id}`);
```

Полный URL запроса: `GET /api/admin/api-costs/users/{telegram_id}`

### Возможные причины:

1. **Эндпоинт не доступен** - сервер не возвращает корректный ответ
2. **Проблема с авторизацией** - запрос блокируется из-за отсутствия токена
3. **Ошибка в базе данных** - отсутствуют необходимые миграции
4. **Сервер не перезапущен** - изменения в коде не применены

## Проверка на сервере

### 1. Проверить, что веб-сервер запущен

```bash
ssh root@31.44.7.144
systemctl status mira-webapp
```

Если не запущен:
```bash
systemctl restart mira-webapp
```

### 2. Проверить логи сервера

```bash
journalctl -u mira-webapp -n 100 --no-pager
```

Искать ошибки связанные с `/api/admin/api-costs/users/`

### 3. Тестировать эндпоинт напрямую

Создать файл на сервере `/tmp/test_endpoint.py`:

```python
import asyncio
from database.repositories.api_cost import ApiCostRepository
from database.repositories.user import UserRepository


async def test():
    telegram_id = 1392513515  # Лиза

    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        print(f"User {telegram_id} not found")
        return

    print(f"User found: {user.display_name} (id={user.id})")

    repo = ApiCostRepository()
    total_cost = await repo.get_total_cost_by_user(user.id)
    by_provider = await repo.get_costs_by_provider(user.id)

    print(f"Total cost: ${total_cost:.4f}")
    print(f"By provider: {by_provider}")

    result = {
        "total_cost": total_cost,
        "by_provider": by_provider
    }
    print(f"\nEndpoint response: {result}")


asyncio.run(test())
```

Запустить:
```bash
cd /var/www/mira_bot
python3 /tmp/test_endpoint.py
```

### 4. Проверить HTTP запрос через curl

Получить админский токен из настроек `.env` или через веб-интерфейс, затем:

```bash
TOKEN="ваш_токен_здесь"
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/admin/api-costs/users/1392513515
```

Ожидаемый ответ:
```json
{
  "total_cost": 0.0,
  "by_provider": {}
}
```

Если пользователь не имеет расходов, это нормально.

## Решение

### Сценарий 1: Эндпоинт работает, но браузер получает ошибку

**Причина:** Проблема с заголовками CORS или кешем браузера

**Решение:**
1. Перезапустить веб-сервер:
   ```bash
   systemctl restart mira-webapp
   ```

2. Очистить кеш браузера (Ctrl + Shift + R)

3. Открыть DevTools (F12) → вкладка Network
4. Обновить страницу и найти запрос к `api-costs/users/...`
5. Посмотреть код ответа и тело ответа

### Сценарий 2: Эндпоинт возвращает 500 ошибку

**Причина:** Ошибка в коде эндпоинта или базе данных

**Решение:**
1. Проверить логи сервера (см. выше)
2. Убедиться, что все миграции применены:
   ```bash
   cd /var/www/mira_bot
   alembic current
   # Должно быть: 20251229_add_api_costs (head)

   # Если нет, применить:
   alembic upgrade head
   ```

### Сценарий 3: Эндпоинт возвращает 401/403 ошибку

**Причина:** Проблема с авторизацией

**Решение:**
1. Проверить, что токен админа передаётся в заголовке
2. В DevTools → вкладка Network → выбрать запрос → Headers
3. Должен быть заголовок: `Authorization: Bearer <token>`

## Код эндпоинта

Эндпоинт находится в файле [webapp/api/routes/api_costs.py:75-106](../webapp/api/routes/api_costs.py#L75-L106):

```python
@router.get("/users/{telegram_id}")
async def get_user_api_costs(
    telegram_id: int,
    admin_data: dict = Depends(get_current_admin)
) -> dict:
    """Получить детальную информацию о расходах пользователя на API."""
    from database.repositories.user import UserRepository
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        return {"total_cost": 0.0, "by_provider": {}}

    repo = ApiCostRepository()
    total_cost = await repo.get_total_cost_by_user(user.id)
    by_provider = await repo.get_costs_by_provider(user.id)

    return {
        "total_cost": total_cost,
        "by_provider": by_provider
    }
```

## Код в админ-панели

Запрос выполняется в файле [admin.html:8005-8026](../webapp/frontend/admin.html#L8005-L8026):

```javascript
try {
    const apiCosts = await apiRequest(`api-costs/users/${user.telegram_id}`);
    if (apiCosts && apiCosts.total_cost > 0) {
        apiCostHtml = `<span style="color: var(--md-sys-color-primary); font-weight: 500;">$${apiCosts.total_cost.toFixed(2)}</span>`;
        // ...
    } else {
        apiCostHtml = '<span style="color: var(--md-sys-color-outline);">$0.00</span>';
        apiTokensHtml = '<span style="color: var(--md-sys-color-outline);">0</span>';
    }
} catch (error) {
    console.error('Failed to load API costs:', error);
    apiCostHtml = '<span style="color: var(--md-sys-color-error);">Ошибка загрузки</span>';
}
```

## Временное решение

Если проблема не решается срочно, можно временно скрыть ошибку, заменив "Ошибка загрузки" на "$0.00":

```javascript
} catch (error) {
    console.error('Failed to load API costs:', error);
    apiCostHtml = '<span style="color: var(--md-sys-color-outline);">$0.00</span>';
    apiTokensHtml = '<span style="color: var(--md-sys-color-outline);">—</span>';
}
```

Но это **НЕ РЕКОМЕНДУЕТСЯ** - лучше исправить причину ошибки.

## Следующие шаги

1. Подключиться к серверу: `ssh root@31.44.7.144`
2. Проверить статус сервиса: `systemctl status mira-webapp`
3. Посмотреть логи: `journalctl -u mira-webapp -n 100`
4. Протестировать эндпоинт вручную (см. выше)
5. Если эндпоинт работает - проверить браузер (DevTools → Network)
6. Перезапустить сервер и очистить кеш браузера

## Ожидаемый результат

После исправления, при открытии страницы пользователя должно отображаться:

- **Если у пользователя нет расходов:**
  ```
  API Токенов: 0
  API Расходы: $0.00
  ```

- **Если есть расходы:**
  ```
  API Токенов: 12,345
  API Расходы: $1.23
                claude: $1.20, yandex_tts: $0.03
  ```
