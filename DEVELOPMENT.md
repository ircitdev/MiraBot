# MIRA BOT - Development Guide

Руководство по разработке и поддержке MIRA BOT.

## Требования

- Python 3.10+
- PostgreSQL или SQLite
- Redis (опционально, fallback на in-memory)

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/ircitdev/MiraBot.git
cd mira_bot
```

### 2. Создание виртуального окружения

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка окружения

Скопируйте `.env.example` в `.env` и заполните переменные:

```bash
cp .env.example .env
```

Основные переменные:
```env
# Telegram Bot
BOT_TOKEN=your_bot_token_here
ADMIN_TELEGRAM_IDS=123456789,987654321

# Claude API
CLAUDE_API_KEY=your_claude_api_key

# Database
DATABASE_URL=sqlite:///./mira_bot.db

# Redis (optional)
REDIS_URL=redis://localhost:6379
```

### 5. Инициализация базы данных

```bash
python -m alembic upgrade head
```

### 6. Запуск бота

```bash
python -m bot.main
```

## Разработка

### Структура проекта

```
mira_bot/
├── ai/                    # AI модули (Claude, mood, hints)
│   ├── claude_client.py
│   ├── mood_analyzer.py
│   └── hint_generator.py
├── bot/                   # Telegram bot handlers
│   ├── handlers/
│   ├── keyboards/
│   └── middlewares/
├── database/              # Database models and repositories
│   ├── models.py
│   ├── repositories/
│   └── migrations/
├── services/              # Business logic services
│   ├── referral.py
│   ├── scheduler.py
│   └── export.py
├── utils/                 # Utility functions
│   ├── text_parser.py
│   └── sanitizer.py
├── config/                # Configuration
│   └── settings.py
└── tests/                 # Tests
```

### Тестирование

#### Запуск всех тестов

```bash
pytest
```

#### Запуск с покрытием

```bash
pytest --cov=. --cov-report=html
```

#### Запуск определённого теста

```bash
pytest tests/test_text_parser.py -v
```

### Проверка типов

```bash
mypy .
```

### Форматирование кода

```bash
# Black
black .

# isort (сортировка импортов)
isort .

# Проверка flake8
flake8 .
```

### Миграции базы данных

#### Создание новой миграции

```bash
alembic revision --autogenerate -m "Description"
```

#### Применение миграций

```bash
alembic upgrade head
```

#### Откат миграции

```bash
alembic downgrade -1
```

#### История миграций

```bash
alembic history
```

## Git Workflow

### Основные ветки

- `main` — production-ready код
- `develop` — integration ветка для разработки
- `feature/*` — новые фичи
- `fix/*` — bug fixes

### Commit Convention

Используем [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Типы:
- `feat`: новая функция
- `fix`: исправление бага
- `docs`: документация
- `style`: форматирование кода
- `refactor`: рефакторинг
- `test`: добавление тестов
- `chore`: обновление зависимостей, конфигурации

Примеры:
```bash
git commit -m "feat(hints): добавлена генерация контекстных подсказок"
git commit -m "fix(mood): исправлен баг в определении anxiety_level"
git commit -m "docs(readme): обновлена документация API"
```

## Debugging

### Логи

Логи пишутся через `loguru`:

```python
from loguru import logger

logger.info("User message processed")
logger.error(f"API error: {e}")
logger.debug(f"Context: {context}")
```

Уровни логов настраиваются через `.env`:

```env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

### Отладка бота

1. Включите verbose логи: `LOG_LEVEL=DEBUG`
2. Запустите бота: `python -m bot.main`
3. Логи пишутся в консоль и `/var/log/mira_bot.log` (на сервере)

### Health Check

Проверка состояния бота:

```bash
curl http://localhost:8080/health
```

Ответ:
```json
{
  "status": "healthy",
  "checks": {
    "bot": {"status": "running", "healthy": true},
    "redis": {"status": "connected", "healthy": true},
    "database": {"status": "connected", "healthy": true}
  }
}
```

## Deployment

### Сервер

Бот работает на сервере `31.44.7.144` через systemd.

#### Деплой изменений

```bash
# 1. Закоммитить и запушить
git add .
git commit -m "feat: новая функция"
git push origin main

# 2. На сервере
ssh root@31.44.7.144
cd /root/mira_bot
git pull
pip install -r requirements.txt
alembic upgrade head
systemctl restart mirabot
```

#### Systemd управление

```bash
# Статус
systemctl status mirabot

# Старт
systemctl start mirabot

# Стоп
systemctl stop mirabot

# Рестарт
systemctl restart mirabot

# Логи
journalctl -u mirabot -f
```

#### Логи

```bash
# Последние 100 строк
tail -100 /var/log/mira_bot.log

# Realtime
tail -f /var/log/mira_bot.log

# Поиск ошибок
grep ERROR /var/log/mira_bot.log
```

### Резервное копирование

База данных:

```bash
# Бэкап
cp /root/mira_bot/mira_bot.db /backup/mira_bot_$(date +%Y%m%d).db

# Восстановление
cp /backup/mira_bot_20241214.db /root/mira_bot/mira_bot.db
```

## Troubleshooting

### Бот не отвечает

1. Проверьте статус: `systemctl status mirabot`
2. Проверьте логи: `tail /var/log/mira_bot.log`
3. Проверьте health: `curl http://localhost:8080/health`

### Конфликт Telegram API

Если видите `Conflict: terminated by other getUpdates`:

1. Остановите все экземпляры: `pkill -9 -f bot.main`
2. Удалите PID lock: `rm /root/mira_bot/mira_bot.pid`
3. Подождите 30 секунд
4. Запустите: `systemctl start mirabot`

### Ошибки базы данных

1. Проверьте миграции: `alembic current`
2. Примените миграции: `alembic upgrade head`
3. Если не помогло — откат и повтор:
   ```bash
   alembic downgrade -1
   alembic upgrade head
   ```

### Claude API errors

Если видите ошибки API:

1. Проверьте API key в `.env`
2. Проверьте лимиты на https://console.anthropic.com
3. Retry logic должна автоматически повторить запрос

## Полезные ссылки

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [python-telegram-bot docs](https://docs.python-telegram-bot.org/)
- [Claude API docs](https://docs.anthropic.com/)
- [SQLAlchemy docs](https://docs.sqlalchemy.org/)
- [Alembic docs](https://alembic.sqlalchemy.org/)
- [pytest docs](https://docs.pytest.org/)
