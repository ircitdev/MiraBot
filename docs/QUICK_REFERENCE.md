# Quick Reference Guide - Mira Bot

**Версия:** 2.1.1
**Дата обновления:** 28.12.2025
**Назначение:** Шпаргалка для быстрого доступа к командам, путям и конфигурации

---

## 🚀 Быстрый старт

### Подключение к серверу
```bash
ssh root@31.44.7.144
cd /root/mira_bot
```

### Управлениеботом
```bash
# Статус
systemctl status mira_bot

# Рестарт
systemctl restart mira_bot

# Остановка
systemctl stop mira_bot

# Запуск
systemctl start mira_bot

# Логи (реал-тайм)
journalctl -u mira_bot -f

# Логи (последние 100 строк)
journalctl -u mira_bot -n 100

# Проверка процессов
ps aux | grep "python.*mira_bot"

# Убить все процессы бота (если зависли)
pkill -f "python.*bot/main.py"
```

---

## 📁 Структура проекта

```
/root/mira_bot/                    # Корень проекта на сервере
├── ai/                            # AI логика
│   ├── claude_client.py           # Claude API клиент
│   ├── crisis_detector.py         # Детектор кризисов
│   ├── crisis_protocol.py         # Кризисный протокол
│   ├── mood_analyzer.py           # Анализ настроения
│   ├── whisper_client.py          # Whisper для голосовых
│   └── prompts/
│       ├── system_prompt.py       # Системный промпт
│       └── mira_legend.py         # Легенда персоны
├── bot/                           # Telegram bot
│   ├── main.py                    # Точка входа
│   ├── handlers/
│   │   ├── message.py             # Обработчик сообщений ⭐
│   │   ├── voice.py               # Голосовые сообщения
│   │   ├── photos.py              # Фотографии
│   │   └── commands.py            # Команды (/start, /help)
│   └── keyboards/
│       └── inline.py              # Inline кнопки
├── webapp/                        # WebApp + Админка
│   ├── app.py                     # FastAPI приложение
│   ├── frontend/                  # Telegram WebApp
│   │   ├── index.html
│   │   ├── app.js
│   │   └── styles.css
│   ├── admin/                     # Админ-панель
│   │   ├── app.py                 # Flask приложение
│   │   ├── templates/
│   │   └── static/
│   └── api/
│       └── routes/                # API endpoints
├── database/                      # База данных
│   ├── models.py                  # SQLAlchemy модели ⭐
│   ├── session.py                 # DB сессии
│   └── repositories/              # Репозитории
│       ├── user.py
│       ├── conversation.py
│       ├── subscription.py
│       ├── referral.py
│       └── memory.py
├── services/                      # Бизнес-логика
│   ├── referral.py                # Реферальная программа
│   └── storage/
│       └── file_storage.py        # Google Cloud Storage
├── config/
│   ├── settings.py                # Конфигурация ⭐
│   └── .env                       # Секретные ключи (НЕ в git!)
├── alembic/                       # Миграции БД
│   └── versions/
├── docs/                          # Документация
│   ├── QUICK_REFERENCE.md         # Этот файл
│   ├── 22.12.25/                  # Документы от 22.12
│   └── 23.12.25/                  # Документы от 23.12
├── pic/                           # Фотографии персоны Миры
├── CHANGELOG.md                   # История версий ⭐
├── requirements.txt               # Зависимости Python
└── .gitignore
```

---

## 🗄️ База данных

### Подключение
```bash
# Через psql
psql -U mirabot -d mirabot_db

# Через Python (в коде)
from database.session import get_session_context

async with get_session_context() as session:
    # Ваш код здесь
```

### Основные таблицы
| Таблица | Описание | Ключевые поля |
|---------|----------|---------------|
| `users` | Пользователи | telegram_id, display_name, is_blocked |
| `messages` | История сообщений | user_id, role, content, created_at |
| `subscriptions` | Подписки | user_id, plan, expires_at |
| `referrals` | Рефералы | referrer_id, referred_id, activated |
| `memory_entries` | Долговременная память | user_id, category, content, importance |
| `admin_users` | Администраторы (будущее) | telegram_id, role, accent_color |
| `admin_logs` | Логи админов (будущее) | admin_user_id, action, resource_type |

### Миграции
```bash
# Создать миграцию
alembic revision --autogenerate -m "описание изменений"

# Применить миграцию
alembic upgrade head

# Откатить на одну версию назад
alembic downgrade -1

# История миграций
alembic history

# Текущая версия
alembic current
```

---

## 🔑 Переменные окружения (.env)

```bash
# Telegram
TELEGRAM_BOT_TOKEN=7xxxxxx:AAHxxxxxx
TELEGRAM_BOT_USERNAME=mira_support_bot

# Claude AI
ANTHROPIC_API_KEY=sk-ant-xxxxx
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# OpenAI (для Whisper)
OPENAI_API_KEY=sk-xxxxx

# Database
DATABASE_URL=postgresql+asyncpg://mirabot:password@localhost/mirabot_db

# Google Cloud Storage
GCS_BUCKET_NAME=mira-bot-storage
GCS_CREDENTIALS_PATH=/root/mira_bot/config/gcs-credentials.json

# Yandex Cloud (TTS)
YANDEX_CLOUD_API_KEY=xxxxx
YANDEX_FOLDER_ID=xxxxx

# Лимиты
FREE_MESSAGES_PER_DAY=10
PREMIUM_PRICE_RUB=299

# Кризисные контакты
CRISIS_HOTLINE=8-800-2000-122
WOMENS_CRISIS_CENTER=8-800-7000-600

# Реферальная программа
REFERRAL_BONUS_DAYS=7
REFERRAL_MILESTONE_3=14
```

---

## 🛠️ Основные команды разработки

### Локальная разработка
```bash
# Активировать виртуальное окружение
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Установить зависимости
pip install -r requirements.txt

# Запустить бота локально
python -m bot.main

# Запустить WebApp локально
python -m webapp.app

# Запустить админку локально
python -m webapp.admin.app

# Тесты (если есть)
pytest
```

### Git workflow
```bash
# Статус
git status

# Добавить файлы
git add .

# Коммит (с шаблоном)
git commit -m "feat: описание изменений

Детали:
- Изменение 1
- Изменение 2

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Пуш
git push origin main

# Проверить последние коммиты
git log --oneline -10
```

### Бэкапы
```bash
# Создать бэкап на сервере
cd /root
tar --exclude='mira_bot/__pycache__' \
    --exclude='mira_bot/.git' \
    --exclude='mira_bot/venv' \
    --exclude='mira_bot/logs' \
    -czf /backup/mira_bot_$(date +%Y%m%d_%H%M%S).tar.gz mira_bot

# Скачать бэкап на локалку
scp root@31.44.7.144:/backup/mira_bot_*.tar.gz d:/DevTools/Database/MIRABOT/backups/

# Список бэкапов
ls -lh /backup/mira_bot_*.tar.gz
```

### Деплой изменений
```bash
# 1. Закоммитить изменения локально
git add .
git commit -m "описание"
git push

# 2. На сервере обновить код
ssh root@31.44.7.144
cd /root/mira_bot
git pull

# 3. Если изменены зависимости
pip install -r requirements.txt

# 4. Если изменена БД
alembic upgrade head

# 5. Рестарт бота
systemctl restart mira_bot

# 6. Проверить логи
journalctl -u mira_bot -f
```

---

## 👥 Пользователи и роли

### Администраторы (текущие)
| Имя | Telegram ID | Роль | Статус |
|-----|-------------|------|--------|
| Aleksandr Uspeshnyy | (владелец) | Admin | Создатель |

### Модераторы (назначенные)
| Имя | Telegram ID | Роль | Назначен |
|-----|-------------|------|----------|
| Лиза | 1392513515 | Moderator | Планируется |

### Премиум пользователи
| Имя | Telegram ID | План | Срок |
|-----|-------------|------|------|
| Елена | 1926322383 | Premium | 30 дней (от 28.12.25) |

### Переименованные пользователи
| Telegram ID | Старое имя | Новое имя | Дата |
|-------------|------------|-----------|------|
| 620828717 | Привет | Настя | 28.12.25 |

---

## 🔧 Полезные скрипты

### Назначить модератора
```bash
cd /root/mira_bot
python scripts/init_moderator.py --telegram-id 1392513515
```

### Проверить пользователей без ответа
```python
# /root/mira_bot
python3 -c "
import asyncio
from database.repositories.conversation import ConversationRepository

async def check():
    repo = ConversationRepository()
    # Ваш код проверки
    pass

asyncio.run(check())
"
```

### Отправить сообщение пользователю
```python
# /root/mira_bot
python3 -c "
import asyncio
from telegram import Bot
from config.settings import settings

async def send():
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_ID, text='Текст сообщения')

asyncio.run(send())
"
```

### Проверить статус API
```bash
# Claude API
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-sonnet-4-20250514","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'

# OpenAI API
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

## 🐛 Troubleshooting (Частые проблемы)

### Бот не отвечает на сообщения
```bash
# 1. Проверить статус
systemctl status mira_bot

# 2. Проверить логи
journalctl -u mira_bot -n 50

# 3. Проверить процессы (не должно быть дубликатов!)
ps aux | grep "python.*bot/main.py"

# 4. Если несколько процессов - убить все
pkill -f "python.*bot/main.py"
systemctl restart mira_bot

# 5. Проверить доступность API
curl https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe
```

### Ошибки базы данных
```bash
# 1. Проверить подключение
psql -U mirabot -d mirabot_db -c "SELECT version();"

# 2. Проверить текущую миграцию
cd /root/mira_bot
alembic current

# 3. Если миграция не применена
alembic upgrade head

# 4. Если нужно откатить
alembic downgrade -1
```

### Ошибки API Claude/OpenAI
```bash
# 1. Проверить .env файл
cat /root/mira_bot/config/.env | grep API_KEY

# 2. Проверить квоты (через dashboard)
# Claude: https://console.anthropic.com
# OpenAI: https://platform.openai.com/usage

# 3. Проверить логи на ошибки API
journalctl -u mira_bot | grep -i "api\|error" | tail -20
```

### Бот запускается несколько раз
```bash
# Это происходит если запускать через nohup без проверки процессов

# 1. Убить все процессы
pkill -f "python.*bot/main.py"

# 2. Запустить через systemd (правильно)
systemctl restart mira_bot

# 3. Проверить что только один процесс
ps aux | grep "python.*bot/main.py" | grep -v grep
```

### WebApp не загружается
```bash
# 1. Проверить запущен ли FastAPI
ps aux | grep "python.*webapp"

# 2. Проверить порты
netstat -tulpn | grep :8000
netstat -tulpn | grep :5000

# 3. Проверить Nginx конфиг
nginx -t
systemctl status nginx

# 4. Перезапустить Nginx
systemctl restart nginx
```

---

## 📊 Мониторинг и статистика

### Проверить количество пользователей
```sql
-- Всего пользователей
SELECT COUNT(*) FROM users;

-- Активных за последние 7 дней
SELECT COUNT(*) FROM users WHERE last_active_at > NOW() - INTERVAL '7 days';

-- С премиум подпиской
SELECT COUNT(*) FROM subscriptions WHERE plan = 'premium' AND expires_at > NOW();
```

### Проверить количество сообщений
```sql
-- Всего сообщений
SELECT COUNT(*) FROM messages;

-- Сообщений за сегодня
SELECT COUNT(*) FROM messages WHERE created_at::date = CURRENT_DATE;

-- По ролям
SELECT role, COUNT(*) FROM messages GROUP BY role;
```

### Проверить использование диска
```bash
# Размер директории
du -sh /root/mira_bot

# Размер бэкапов
du -sh /backup

# Размер БД
psql -U mirabot -d mirabot_db -c "
SELECT pg_size_pretty(pg_database_size('mirabot_db'));
"
```

### Проверить использование RAM
```bash
# Память процесса бота
ps aux | grep "python.*bot/main.py" | awk '{print $6/1024 " MB"}'

# Общая память системы
free -h
```

---

## 🔐 Безопасность

### Важные правила
1. ✅ **Никогда** не коммитить `.env` файл
2. ✅ **Всегда** использовать переменные окружения для секретов
3. ✅ **Регулярно** делать бэкапы БД
4. ✅ **Проверять** логи на подозрительную активность
5. ✅ **Обновлять** зависимости (проверка уязвимостей)

### Проверка уязвимостей
```bash
# Проверить устаревшие зависимости
pip list --outdated

# Проверить уязвимости (требует pip-audit)
pip install pip-audit
pip-audit
```

### Ротация секретов
```bash
# 1. Создать новый токен в BotFather
# 2. Обновить .env
nano /root/mira_bot/config/.env

# 3. Рестарт бота
systemctl restart mira_bot
```

---

## 📝 Шаблоны кода

### Отправить сообщение пользователю
```python
from telegram import Bot
from config.settings import settings

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
await bot.send_message(chat_id=TELEGRAM_ID, text="Ваше сообщение")
```

### Сохранить сообщение в БД
```python
from database.repositories.conversation import ConversationRepository

repo = ConversationRepository()
await repo.save_message(
    user_id=user.id,
    role='assistant',
    content='Текст сообщения',
    tags=['recovery', 'apology']
)
```

### Получить пользователя из БД
```python
from database.repositories.user import UserRepository

user_repo = UserRepository()
user = await user_repo.get_by_telegram_id(telegram_id)
```

### Создать подписку
```python
from database.repositories.subscription import SubscriptionRepository
from datetime import datetime, timedelta

sub_repo = SubscriptionRepository()
expires_at = datetime.now() + timedelta(days=30)

await sub_repo.create(
    user_id=user.id,
    plan='premium',
    expires_at=expires_at
)
```

### Логирование
```python
from loguru import logger

logger.info(f"User {user_id} sent message")
logger.warning(f"API rate limit approaching")
logger.error(f"Failed to process message: {error}")
```

---

## 📚 Полезные ссылки

### Документация
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [python-telegram-bot](https://docs.python-telegram-bot.org/)
- [Claude API](https://docs.anthropic.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)

### Дашборды
- [Anthropic Console](https://console.anthropic.com/)
- [OpenAI Platform](https://platform.openai.com/)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Yandex Cloud](https://console.cloud.yandex.ru/)

### GitHub репозиторий
- [MiraBot](https://github.com/ircitdev/MiraBot)

---

## 🎯 Чек-лист перед деплоем

- [ ] Все изменения закоммичены
- [ ] Обновлён CHANGELOG.md
- [ ] Создан бэкап текущей версии
- [ ] Код загружен на GitHub
- [ ] На сервере выполнен `git pull`
- [ ] Применены миграции БД (если есть)
- [ ] Обновлены зависимости (если нужно)
- [ ] Бот перезапущен
- [ ] Проверены логи (нет ошибок)
- [ ] Протестирован основной функционал
- [ ] Проверена WebApp (если изменения там)

---

## 🆘 Контакты для экстренной связи

### Кризисные службы (для пользователей)
- Телефон доверия: **8-800-2000-122**
- Центр помощи женщинам: **8-800-7000-600**
- Экстренные службы: **112**

### Техническая поддержка
- Сервер: `root@31.44.7.144`
- Репозиторий: [github.com/ircitdev/MiraBot](https://github.com/ircitdev/MiraBot)

---

**Последнее обновление:** 28.12.2025
**Версия документа:** 1.0
**Автор:** Claude Sonnet 4.5 via Claude Code
