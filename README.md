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

### 🤖 AI-диалог

Streaming ответы через Claude Sonnet 4.5 с контекстом до 200K токенов. Сообщения обновляются в реальном времени по мере генерации.

**Технологии:** Streaming API, 200K context window

### 😊 Mood Tracking

Автоматический анализ настроения пользователя по 12 эмоциям с расчётом уверенности и динамики изменений.

**Эмоции:** happy, sad, anxious, angry, calm, excited, lonely, stressed, overwhelmed, grateful, hopeful, frustrated

### 💡 Контекстные подсказки

Умные quick reply кнопки, адаптирующиеся к контексту диалога с приоритизацией по релевантности.

**Фичи:** Context-aware, Priority-based, До 6 подсказок одновременно

### 🚨 Кризис-детекция

Автоматическое выявление суицидальных мыслей, панических атак и кризисных состояний с немедленным предложением помощи.

**Маркеры:** Суицидальные мысли, паника, кризисное состояние

### 👤 Персонализация

Запоминание имени пользователя, партнёра, детей, предпочтений в общении и стиля диалога.

**Данные:** Имя, персона (Мира), партнёр, дети, стиль общения, предпочтения эмодзи

### 💎 Подписки

- **Free** — 10 сообщений в день
- **Trial** — 3 дня Premium бесплатно для новых пользователей
- **Premium** — безлимит, расширенный контекст (20 сообщений), долгосрочная память

### 🎁 Реферальная программа

Уникальные реферальные ссылки, отслеживание приглашённых пользователей и бонусы +7 дней для обоих.

### 🧘 Ритуалы

Медитации, дыхательные практики, аффирмации для поддержки ментального здоровья.

**Типы:** Утренние check-in, вечерние check-in, медитации, дыхательные упражнения

### ⚙️ WebApp (Mini App)

Telegram Mini App для удобного управления настройками и просмотра статистики.

**Возможности:**

- 📊 Детальная статистика (сообщения, настроение, темы, эмоции)
- ⚙️ Управление персоной, именем, партнёром
- 🎂 Праздничные даты (день рождения, годовщина)
- ⏰ Настройка ритуалов (утренние/вечерние check-in)
- 📬 Проактивные сообщения
- 📈 График настроения за неделю
- 💎 Статус подписки

**Доступ:** Кнопка "⚙️ Настройки" в меню бота или команда `/settings`

### 🛡️ Админ-панель

Управление пользователями, статистика, broadcast рассылки, экспорт данных в Excel.

**Доступ:** Только для администраторов (ADMIN_TELEGRAM_IDS)

## Технологический стек

### Backend

- **Python 3.10+** — основной язык
- **python-telegram-bot 21.0** — Telegram Bot API
- **Anthropic Claude API** — AI для генерации ответов
- **SQLAlchemy 2.0** — ORM + async поддержка
- **PostgreSQL / SQLite** — база данных
- **Redis** — кэширование и rate limiting
- **Alembic** — миграции БД
- **FastAPI** — WebApp backend API
- **uvicorn** — ASGI сервер для WebApp

### Infrastructure

- **Docker** — контейнеризация
- **GitHub Actions** — CI/CD
- **systemd** — production deployment (bot + webapp)
- **nginx** — reverse proxy для WebApp
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

```text
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

### Ключевые модули

#### Context Builder - Построение контекста

```python
# Загрузка последних N сообщений из истории
history = await conversation_repo.get_history(
    user_id=user.id,
    limit=20  # Free: 10, Premium: 20
)

# Форматирование для Claude API
messages = [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
]
```

#### Rate Limiting - Ограничение частоты

```python
# Redis-based ограничения
async def check_rate_limit(user_id: int, is_premium: bool):
    if is_premium:
        return True  # Безлимит

    # Free: 10 сообщений/день
    count = await redis.incr(f"msg_count:{user_id}:{today}")
    await redis.expire(f"msg_count:{user_id}:{today}", 86400)

    return count <= FREE_MESSAGES_PER_DAY
```

#### Text Parsing - Парсинг имени

```python
# Извлечение имени из текста пользователя
def extract_name_from_text(text: str) -> str:
    # "Меня зовут Аня" → "Аня"
    # "Я Маша" → "Маша"
    patterns = [
        r"(?:зовут|имя)\s+([А-ЯЁа-яё]+)",
        r"^я\s+([А-ЯЁа-яё]+)",
        r"меня\s+([А-ЯЁа-яё]+)",
    ]
    # Санитизация через sanitize_name()
```

#### Error Handling - Обработка ошибок

```python
# Graceful degradation
try:
    response = await claude.generate_response(...)
except anthropic.APIConnectionError:
    await notify_user("Не могу связаться с сервером...")
    await save_message(tags=["error:api_connection"])
except anthropic.RateLimitError:
    await notify_user("Слишком много запросов...")
    await save_message(tags=["error:rate_limit"])
```

## Алгоритмы

### MoodAnalyzer — Анализ настроения

Определяет эмоциональное состояние пользователя по тексту сообщения.

**Процесс:**

1. Получение текста сообщения
2. Нормализация текста (lowercase, удаление punctuation)
3. Токенизация на слова
4. Поиск эмоциональных маркеров
5. Подсчёт совпадений по 12 эмоциям
6. Расчёт mood_score (-1.0 до +1.0)
7. Определение primary_emotion
8. Расчёт confidence (0.0 до 1.0)
9. Возврат MoodAnalysisResult

**12 отслеживаемых эмоций:**

| Эмоция | Примеры маркеров | Вес |
|--------|------------------|-----|
| happy | счастлив, радост, весел | +1.0 |
| sad | грустн, печаль, тоска | -0.8 |
| anxious | тревож, волну, беспоко | -0.6 |
| angry | злой, бесит, раздража | -0.7 |
| calm | спокой, умиротвор | +0.7 |
| excited | вдохновлён, энергия | +0.9 |
| lonely | одинок, скуча, пуст | -0.5 |
| stressed | стресс, напряж, устал | -0.6 |

**Формулы расчёта:**

```python
mood_score = Σ(emotion_weight × match_count) / total_words
confidence = min(1.0, total_matches / 5)
primary_emotion = emotion с max(match_count)
```

### HintGenerator — Генерация подсказок

Создаёт контекстные quick reply кнопки на основе ответа AI и настроения.

**Процесс:**

1. Получение response (ответ AI) и mood
2. Нормализация текста (lowercase)
3. Поиск триггеров в RESPONSE_TRIGGERS
4. Добавление универсальных хинтов
5. Добавление mood-специфичных хинтов
6. Сортировка по приоритету (DESC)
7. Удаление дубликатов
8. Лимит: макс. 6 подсказок
9. Возврат List[Hint]

**Приоритеты подсказок:**

| Тип | Приоритет | Примеры |
|-----|-----------|---------|
| Вопросы | 15 | "Да", "Нет", "Может быть" |
| Эмоциональные | 12-14 | "😊 Лучше!", "😔 Не очень" |
| Действия | 10-11 | "🧘 Медитация", "🌙 Спать" |
| Универсальные | 1-5 | "💬 Продолжим?", "🔄 Сменить тему" |

### Crisis Detection — Детекция кризиса

Выявляет критические состояния пользователя для немедленного реагирования.

**Процесс:**

1. Получение сообщения пользователя
2. Нормализация текста
3. Проверка суицидальных маркеров
4. Проверка панических атак
5. Формирование экстренного ответа
6. Отправка номеров горячих линий
7. Логирование (crisis_detected=True)

**Критические маркеры:**

- **Суицид:** "хочу умереть", "покончить с собой"
- **Паника:** "не могу дышать", "сердце колотится"
- **Кризис:** "больше не могу", "всё бессмысленно"

### Input Sanitization — Безопасность ввода

Очистка и валидация пользовательского ввода для защиты от атак.

**Процесс:**

1. Получение raw text
2. Удаление control characters
3. Нормализация Unicode (NFC)
4. Проверка длины (1-4096 символов)
5. Детекция SQL injection
6. Детекция XSS паттернов
7. Логирование подозрительного ввода
8. Возврат очищенного текста

**Проверки безопасности:**

- SQL injection: `SELECT`, `DROP`, `--`
- XSS: `<script>`, `javascript:`
- Path traversal: `../`
- Command injection: `$(`, `;`

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

### Слоистая архитектура

Проект использует многослойную архитектуру для разделения ответственности:

```text
🖥️ Presentation Layer (bot/handlers)
         ↓
🧠 Business Logic Layer (ai/, services/)
         ↓
💾 Data Access Layer (repositories)
         ↓
🗄️ Database Layer (SQLAlchemy + PostgreSQL)
```

**Слои:**

- **Presentation** — Обработчики Telegram (commands, messages, callbacks)
- **Business Logic** — AI-модули, анализаторы, генераторы
- **Data Access** — Repository pattern для работы с БД
- **Database** — SQLAlchemy ORM + миграции Alembic

## Структура проекта

```text
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
├── webapp/                  # WebApp (Mini App)
│   ├── api/                 # FastAPI backend
│   │   ├── main.py          # Главное приложение
│   │   ├── auth.py          # Telegram авторизация
│   │   └── routes/          # API endpoints
│   │       ├── settings.py  # Настройки пользователя
│   │       └── stats.py     # Статистика
│   ├── frontend/            # Frontend
│   │   ├── index.html       # Главная страница
│   │   ├── styles.css       # Стили
│   │   └── app.js           # JavaScript логика
│   ├── run_server.py        # Запуск сервера
│   └── README.md            # Документация WebApp
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

- `/start` — начать диалог, онбординг (автоматический Trial период)
- `/help` — справка по боту
- `/settings` — открыть WebApp с настройками и статистикой
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

# WebApp
WEBAPP_DOMAIN=mira.uspeshnyy.ru
WEBAPP_PORT=8081

# Settings
LOG_LEVEL=INFO
FREE_MESSAGES_PER_DAY=10
TRIAL_PERIOD_DAYS=3
```

Полный список: [.env.example](.env.example)

## Changelog

См. [TODO.md](TODO.md) для детальной истории изменений.

### Последние обновления (14.12.2024)

- ✅ **WebApp (Mini App)** — полноценное веб-приложение для настроек и статистики
- ✅ **Trial период** — 3 дня Premium бесплатно для новых пользователей
- ✅ Добавлена инфраструктура тестирования (pytest, 46 тестов)
- ✅ Настроена типизация (mypy)
- ✅ Docker контейнеризация
- ✅ CI/CD через GitHub Actions
- ✅ Автоматические бэкапы БД
- ✅ Отключена музыкальная функция
- ✅ Убраны упоминания "виртуальный"
- ✅ Оптимизированы контекстные подсказки (убраны универсальные хинты)

## Документация

- [DEVELOPMENT.md](DEVELOPMENT.md) — руководство для разработчиков
- [DOCKER.md](DOCKER.md) — Docker deployment
- [TODO.md](TODO.md) — план развития и changelog
- [webapp/README.md](webapp/README.md) — документация WebApp
- [tests/README.md](tests/README.md) — документация по тестированию
- [CHANGELOG.md](CHANGELOG.md) — детальная история изменений
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
- [ ] Мультиязычность (EN)

### Планируется

- [ ] Интеграция YooKassa (реальные платежи)
- [ ] Мониторинг (Prometheus + Grafana)
- [ ] Inline mode
- [ ] График настроения в WebApp с Chart.js

## Лицензия

MIT License - см. [LICENSE](LICENSE)

## Контакты

- GitHub: [@ircitdev](https://github.com/ircitdev)
- Telegram Bot: [@MiraSupportBot](https://t.me/your_bot_username)

---

🤖 **Powered by Claude Sonnet 4.5**

Made with ❤️ using [Claude Code](https://claude.com/claude-code)
