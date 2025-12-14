# MIRA BOT 💛

Психологический Telegram-бот для эмоциональной поддержки на базе Claude AI.

[![Tests](https://github.com/ircitdev/MiraBot/workflows/Tests/badge.svg)](https://github.com/ircitdev/MiraBot/actions)
[![codecov](https://codecov.io/gh/ircitdev/MiraBot/branch/main/graph/badge.svg)](https://codecov.io/gh/ircitdev/MiraBot)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Описание

MIRA BOT — это AI-ассистент для эмоциональной поддержки пользователей. Бот использует Claude Sonnet 4.5 для генерации эмпатичных ответов и помогает пользователям справляться с жизненными трудностями.

**Персонажи:**

- **Мира** — подруга-наставник (42 года, замужем 18 лет, двое детей)
- Эмпатичный тон, без осуждения, практичные советы

## Возможности

### 🤖 Основной функционал

- **AI-диалог** — эмпатичные ответы через Claude Sonnet 4.5
- **Голосовые сообщения** — транскрипция через Whisper API
- **Streaming ответов** — эффект "печатает..." в реальном времени
- **Mood tracking** — отслеживание эмоционального состояния
- **Контекстные подсказки** — кнопки быстрых ответов по ситуации
- **Кризис-детекция** — автоматическое распознавание кризиса

### 💳 Подписки

- **Free** — 10 сообщений в день
- **Premium** — безлимит, приоритетная поддержка, долгосрочная память

### 🔧 Дополнительно

- **Реферальная программа** — бонус +7 дней для обоих
- **Автоматические ритуалы** — утренние/вечерние check-in
- **Праздничные поздравления** — дни рождения, годовщины
- **Админ-панель** — управление пользователями, статистика, рассылки

## Технологический стек

### Backend

- **Python 3.10+** — основной язык
- **python-telegram-bot 21.0** — Telegram Bot API
- **Anthropic Claude API** — AI для генерации ответов
- **SQLAlchemy 2.0** — ORM + async поддержка
- **PostgreSQL / SQLite** — база данных
- **Redis** — кэширование и rate limiting
- **Alembic** — миграции БД

### Infrastructure

- **Docker** — контейнеризация
- **GitHub Actions** — CI/CD
- **systemd** — production deployment
- **pytest** — тестирование
- **mypy** — type checking

### AI & Services

- **Claude Sonnet 4.5** — основная модель
- **OpenAI Whisper** — транскрипция голоса
- **YooKassa** — платежи (опционально)

## Быстрый старт

### Docker (рекомендуется)

```bash
# Клонировать репозиторий
git clone https://github.com/ircitdev/MiraBot.git
cd mira_bot

# Настроить .env
cp .env.example .env
# Отредактируйте .env и заполните BOT_TOKEN, CLAUDE_API_KEY, ADMIN_TELEGRAM_IDS

# Запустить через Docker Compose
docker-compose up -d

# Проверить статус
docker-compose ps
curl http://localhost:8080/health
```

Подробнее: [DOCKER.md](DOCKER.md)

### Локальная разработка

```bash
# Клонировать и перейти в директорию
git clone https://github.com/ircitdev/MiraBot.git
cd mira_bot

# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Установить зависимости
pip install -r requirements.txt

# Настроить .env
cp .env.example .env
# Заполнить обязательные переменные

# Применить миграции
alembic upgrade head

# Запустить бота
python -m bot.main
```

Подробнее: [DEVELOPMENT.md](DEVELOPMENT.md)

## Архитектура

### Компоненты системы

```
┌─────────────────────────────────────────────────────────────────┐
│                        Telegram User                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                ┌───────────▼──────────────┐
                │   python-telegram-bot    │
                │   (Webhooks/Polling)     │
                └───────────┬──────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼─────┐      ┌──────▼──────┐    ┌──────▼──────┐
   │ Message  │      │   Voice     │    │   Photo     │
   │ Handler  │      │   Handler   │    │   Handler   │
   └────┬─────┘      └──────┬──────┘    └──────┬──────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                ┌───────────▼──────────────┐
                │   ClaudeClient           │
                │   (Anthropic API)        │
                └───────────┬──────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼─────┐      ┌──────▼──────┐    ┌──────▼──────┐
   │  Mood    │      │    Hint     │    │  Sticker    │
   │ Analyzer │      │  Generator  │    │   Sender    │
   └────┬─────┘      └──────┬──────┘    └──────┬──────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                ┌───────────▼──────────────┐
                │   Database (PostgreSQL)  │
                │   Redis (Cache/Limits)   │
                └──────────────────────────┘
```

### Message Flow

1. **Получение сообщения** → Telegram Bot API
2. **Валидация** → `sanitizer.validate_message()`
3. **Проверка лимитов** → Redis rate limiting
4. **Получение контекста** → `conversation_repo.get_history()`
5. **AI генерация** → Claude API (streaming)
6. **Анализ настроения** → `mood_analyzer.analyze()`
7. **Генерация подсказок** → `hint_generator.generate()`
8. **Отправка стикера** → `maybe_send_sticker()`
9. **Сохранение** → Database (messages + mood_entries)
10. **Отправка подсказок** → Inline кнопки

### Безопасность

#### Санитизация входных данных

- Максимальная длина сообщения: 4096 символов
- Блокировка SQL injection паттернов
- Фильтрация XSS попыток
- Валидация имён и текста через regex

#### Rate Limiting

- Redis-based ограничения
- Free: 10 сообщений/день
- Premium: безлимит
- Anti-flood защита

#### Защита данных

- Санитизация перед сохранением в БД
- Параметризованные SQL запросы (SQLAlchemy ORM)
- Безопасное хранение токенов в `.env`
- PID file locking (предотвращение multiple instances)

#### Обработка кризисных ситуаций

- Детекция суицидальных мыслей
- Автоматическое предложение телефона доверия
- Логирование кризисных сообщений для модерации

## Структура проекта

```
mira_bot/
├── ai/                      # AI модули
│   ├── claude_client.py     # Claude API клиент
│   ├── mood_analyzer.py     # Анализ настроения
│   ├── hint_generator.py    # Генерация подсказок
│   ├── style_analyzer.py    # Анализ стиля общения
│   └── prompts/             # Системные промпты
│       ├── system_prompt.py # Основной промпт Миры
│       └── mira_legend.py   # Легенда персонажа
├── bot/                     # Telegram bot
│   ├── handlers/            # Обработчики команд
│   │   ├── message.py       # Текстовые сообщения
│   │   ├── voice.py         # Голосовые сообщения
│   │   ├── photos.py        # Фотографии
│   │   ├── start.py         # /start, онбординг
│   │   └── admin.py         # Админ-панель
│   ├── keyboards/           # Inline клавиатуры
│   └── middlewares/         # Middlewares (rate limit)
├── database/                # База данных
│   ├── models.py            # SQLAlchemy модели
│   ├── repositories/        # Repository pattern
│   │   ├── user.py
│   │   ├── conversation.py
│   │   ├── mood.py
│   │   └── subscription.py
│   └── migrations/          # Alembic миграции
├── services/                # Бизнес-логика
│   ├── scheduler.py         # APScheduler (ритуалы)
│   ├── referral.py          # Реферальная система
│   ├── health.py            # Health check сервер
│   ├── redis_client.py      # Redis клиент
│   ├── sticker_sender.py    # Отправка стикеров
│   └── export.py            # Экспорт данных
├── utils/                   # Утилиты
│   ├── text_parser.py       # Парсинг текста
│   └── sanitizer.py         # Санитизация ввода
├── tests/                   # Тесты (46 unit тестов)
├── scripts/                 # Скрипты автоматизации
│   ├── backup_db.sh         # Бэкап БД
│   └── restore_db.sh        # Восстановление БД
├── config/                  # Конфигурация
│   ├── settings.py          # Pydantic Settings
│   └── constants.py         # Константы
└── docs/                    # Документация
```

## Команды бота

### Пользовательские

- `/start` — начать диалог, онбординг
- `/help` — справка по боту
- `/settings` — настройки (стиль общения, эмодзи)
- `/subscription` — управление подпиской
- `/referral` — реферальная программа
- `/rituals` — настройка ритуалов
- `/privacy` — политика конфиденциальности

### Админские

- `/admin` — админ-панель
  - Статистика пользователей
  - Broadcast рассылки
  - Блокировка пользователей
  - Экспорт данных
  - Просмотр истории диалогов

## База данных

### Основные таблицы

| Таблица | Описание |
|---------|----------|
| `users` | Профили пользователей |
| `subscriptions` | Подписки |
| `messages` | История диалогов |
| `memory_entries` | Долгосрочная память (Premium) |
| `mood_entries` | Записи настроения |
| `referrals` | Реферальные коды |
| `payments` | Платежи YooKassa |
| `scheduled_messages` | Запланированные сообщения |
| `admin_users` | Администраторы |
| `promo_codes` | Промокоды |

## Тестирование

```bash
# Запустить все тесты
pytest

# С покрытием кода
pytest --cov=. --cov-report=html

# Только определённый тест
pytest tests/test_text_parser.py -v

# Type checking
mypy .

# Форматирование
black .
isort .
flake8 .
```

Подробнее: [tests/README.md](tests/README.md)

## Deployment

### Production (systemd)

```bash
# На сервере
cd /root/mira_bot
git pull origin main
pip install -r requirements.txt
alembic upgrade head
systemctl restart mirabot

# Проверка
systemctl status mirabot
curl http://localhost:8080/health
```

### Docker Production

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Автоматический деплой

Push в `main` автоматически деплоится на production через GitHub Actions.

См. [.github/workflows/deploy.yml](.github/workflows/deploy.yml)

## Бэкапы

```bash
# Настроить автоматические ежедневные бэкапы (на сервере)
./scripts/setup_cron.sh "0 3 * * *" 7

# Ручной бэкап
./scripts/backup_db.sh

# Восстановление
./scripts/restore_db.sh /backup/mira_bot/mira_bot_20241214_120000.db.gz
```

## Мониторинг

### Health Check

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

### Логи

```bash
# Realtime логи
tail -f /var/log/mira_bot.log

# Docker логи
docker-compose logs -f bot

# Systemd логи
journalctl -u mirabot -f
```

## Конфигурация

Основные переменные окружения (`.env`):

```env
# Telegram
BOT_TOKEN=your_telegram_bot_token
ADMIN_TELEGRAM_IDS=123456789,987654321

# Claude API
CLAUDE_API_KEY=your_claude_api_key
CLAUDE_MODEL=claude-sonnet-4-20250514

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/mira_bot
# Или SQLite для локальной разработки:
# DATABASE_URL=sqlite:///./mira_bot.db

# Redis
REDIS_URL=redis://localhost:6379

# Settings
LOG_LEVEL=INFO
FREE_MESSAGES_PER_DAY=10
```

Полный список: [.env.example](.env.example)

## Changelog

См. [TODO.md](TODO.md) для детальной истории изменений.

### Последние обновления (14.12.2024)

- ✅ Добавлена инфраструктура тестирования (pytest, 46 тестов)
- ✅ Настроена типизация (mypy)
- ✅ Docker контейнеризация
- ✅ CI/CD через GitHub Actions
- ✅ Автоматические бэкапы БД
- ✅ Отключена музыкальная функция
- ✅ Убраны упоминания "виртуальный"

## Документация

- [DEVELOPMENT.md](DEVELOPMENT.md) — руководство для разработчиков
- [DOCKER.md](DOCKER.md) — Docker deployment
- [TODO.md](TODO.md) — план развития и changelog
- [tests/README.md](tests/README.md) — документация по тестированию
- [CHANGELOG_MUSIC.md](CHANGELOG_MUSIC.md) — история музыкальной функции

## Contribution

1. Fork репозиторий
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'feat: добавлена фича'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

Используем [Conventional Commits](https://www.conventionalcommits.org/).

## Roadmap

### В разработке

- [ ] Библиотека упражнений
- [ ] Аффирмации дня
- [ ] Web App для настроек
- [ ] Мультиязычность (EN)

### Планируется

- [ ] Интеграция YooKassa (реальные платежи)
- [ ] Trial период (3 дня Premium)
- [ ] Мониторинг (Prometheus + Grafana)
- [ ] Inline mode

## Лицензия

MIT License - см. [LICENSE](LICENSE)

## Контакты

- GitHub: [@ircitdev](https://github.com/ircitdev)
- Telegram Bot: [@MiraSupportBot](https://t.me/your_bot_username)

---

🤖 **Powered by Claude Sonnet 4.5**

Made with ❤️ using [Claude Code](https://claude.com/claude-code)
