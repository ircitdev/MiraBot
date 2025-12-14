# MIRA BOT - Docker Deployment

Руководство по запуску MIRA BOT через Docker Compose.

## Быстрый старт

### 1. Подготовка

```bash
# Клонируем репозиторий
git clone https://github.com/ircitdev/MiraBot.git
cd mira_bot

# Копируем пример конфигурации
cp .env.example .env
```

### 2. Настройка .env

Отредактируйте `.env` файл и заполните обязательные переменные:

```env
BOT_TOKEN=your_telegram_bot_token
ADMIN_TELEGRAM_IDS=123456789
CLAUDE_API_KEY=your_claude_api_key
```

### 3. Запуск

```bash
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f bot

# Проверка статуса
docker-compose ps
curl http://localhost:8080/health
```

## Архитектура

Docker Compose поднимает 3 сервиса:

1. **PostgreSQL** (порт 5432)
   - База данных
   - Volume: `postgres_data`
   - Backups: `./backups`

2. **Redis** (порт 6379)
   - Кэш и rate limiting
   - Volume: `redis_data`

3. **MIRA Bot** (порт 8080)
   - Telegram бот
   - Health check: http://localhost:8080/health

## Управление

### Запуск и остановка

```bash
# Запустить
docker-compose up -d

# Остановить
docker-compose down

# Перезапустить
docker-compose restart bot

# Остановить и удалить volumes
docker-compose down -v
```

### Логи

```bash
# Все сервисы
docker-compose logs -f

# Только бот
docker-compose logs -f bot

# Последние 100 строк
docker-compose logs --tail=100 bot
```

### Выполнение команд

```bash
# Войти в контейнер
docker-compose exec bot bash

# Выполнить миграции
docker-compose exec bot alembic upgrade head

# Запустить тесты
docker-compose exec bot pytest

# Проверить типы
docker-compose exec bot mypy .
```

## Обновление

```bash
# Получить последний код
git pull origin main

# Пересобрать и перезапустить
docker-compose up -d --build

# Применить миграции
docker-compose exec bot alembic upgrade head
```

## Бэкапы

### Автоматические бэкапы

Настройка автоматических бэкапов (на хосте):

```bash
# Настроить cron для ежедневных бэкапов в 3:00
./scripts/setup_cron.sh "0 3 * * *" 7
```

### Ручной бэкап

```bash
# Создать бэкап
./scripts/backup_db.sh

# Восстановить из бэкапа
./scripts/restore_db.sh /backup/mira_bot/mira_bot_20241214_120000.db.gz
```

### Бэкап PostgreSQL

```bash
# Экспорт БД
docker-compose exec db pg_dump -U mirabot mira_bot > backup.sql

# Импорт БД
docker-compose exec -T db psql -U mirabot mira_bot < backup.sql
```

## Мониторинг

### Health Checks

```bash
# Проверка всех сервисов
docker-compose ps

# Health check бота
curl http://localhost:8080/health

# Детальная информация
curl http://localhost:8080/health | jq
```

### Метрики

```bash
# Использование ресурсов
docker stats

# Только MIRA Bot
docker stats mira_bot
```

## Production

### Рекомендации для production

1. **Смените пароли БД:**
   ```env
   DB_PASSWORD=strong_random_password_here
   JWT_SECRET=another_strong_random_secret
   ```

2. **Настройте HTTPS** (через nginx reverse proxy)

3. **Настройте мониторинг** (Prometheus + Grafana)

4. **Регулярные бэкапы:**
   ```bash
   # Ежедневные бэкапы с хранением 30 дней
   ./scripts/setup_cron.sh "0 3 * * *" 30
   ```

5. **Логирование:**
   ```env
   LOG_LEVEL=INFO  # WARNING для production
   ```

### Системные требования

Минимум:
- CPU: 1 core
- RAM: 1GB
- Disk: 10GB

Рекомендуется:
- CPU: 2 cores
- RAM: 2GB
- Disk: 20GB SSD

## Troubleshooting

### Бот не запускается

```bash
# Проверить логи
docker-compose logs bot

# Проверить health
curl http://localhost:8080/health

# Перезапустить
docker-compose restart bot
```

### База данных недоступна

```bash
# Проверить статус PostgreSQL
docker-compose ps db
docker-compose logs db

# Перезапустить
docker-compose restart db
```

### Redis недоступен

```bash
# Проверить Redis
docker-compose exec redis redis-cli ping

# Перезапустить
docker-compose restart redis
```

### Сбросить всё

```bash
# Остановить и удалить всё (включая данные!)
docker-compose down -v

# Пересоздать
docker-compose up -d
```

## Переменные окружения

См. `.env.example` для полного списка переменных.

Обязательные:
- `BOT_TOKEN` — Telegram bot token
- `CLAUDE_API_KEY` — Claude API key
- `ADMIN_TELEGRAM_IDS` — ID админов (через запятую)

Опциональные:
- `LOG_LEVEL` — уровень логов (DEBUG/INFO/WARNING/ERROR)
- `FREE_MESSAGES_PER_DAY` — лимит бесплатных сообщений
- `REDIS_URL` — URL Redis сервера
- `DATABASE_URL` — URL PostgreSQL

## Дополнительно

### Разработка

Для локальной разработки лучше использовать SQLite:

```env
DATABASE_URL=sqlite:///./mira_bot.db
```

И запускать бота напрямую:

```bash
python -m bot.main
```

### CI/CD

GitHub Actions автоматически:
- Запускает тесты при push
- Деплоит на production при push в main

См. `.github/workflows/` для деталей.
