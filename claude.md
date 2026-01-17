# MIRA BOT — Context & Rules

## ⚡ Основные команды (Commands)
*Запускать из корня проекта. Используй `venv`.*

- **Запуск (Local):** `python -m bot.main`
- **WebApp (Local):** `uvicorn webapp.api.main:app --reload --port 8081`
- **Тесты:** `pytest` (или `pytest --cov=.` для покрытия)
- **Линтинг (Fix):** `black . && isort .`
- **Типизация:** `mypy .` (Строгий режим, игнорировать ошибки только через `# type: ignore` с комментарием почему)
- **Миграции:**
  - Создать: `alembic revision --autogenerate -m "message"`
  - Применить: `alembic upgrade head`

### Deployment на сервер
- **Сервер:** `root@31.44.7.144`
- **WebApp location:** `/var/www/miradrug/webapp/` (nginx раздаёт статику)
- **Backend location:** `/root/mira_bot/` (код бота и API)
- **Деплой HTML:** `scp webapp/frontend/admin.html root@31.44.7.144:/var/www/miradrug/webapp/admin.html`
- **Деплой Python:** `scp webapp/api/routes/admin.py root@31.44.7.144:/root/mira_bot/webapp/api/routes/admin.py`
- **Рестарт API:**
  ```bash
  ssh root@31.44.7.144 "lsof -ti:8081 | xargs kill -9 2>/dev/null; \
    cd /root/mira_bot && \
    nohup /root/mira_bot/venv/bin/python -m uvicorn webapp.api.main:app \
      --host 0.0.0.0 --port 8081 > /var/log/mira_webapp.log 2>&1 &"
  ```
- **Рестарт Бота:**
  ```bash
  ssh root@31.44.7.144 "pkill -f 'python.*bot.main.*mira_bot' && \
    cd /root/mira_bot && \
    nohup /root/mira_bot/venv/bin/python -m bot.main > /var/log/mira_bot.log 2>&1 &"
  ```
- **Проверка статуса:**
  ```bash
  # Процесс бота
  ssh root@31.44.7.144 "ps aux | grep 'python.*bot.main' | grep mira_bot | grep -v grep"

  # Процесс API
  ssh root@31.44.7.144 "lsof -ti:8081"
  ```

### Логи

⚠️ **ВАЖНО:** Бот создаёт лог-файлы с датой и временем запуска!

**Актуальные логи бота:**

```bash
# НЕ ИСПОЛЬЗУЙ: /var/log/mira_bot.log - это старый/неактивный файл!
# Правильно: логи в папке /root/mira_bot/logs/

# Найти актуальный лог-файл
ssh root@31.44.7.144 "ls -lt /root/mira_bot/logs/ | head -5"

# Или найти через процесс
ssh root@31.44.7.144 "lsof -p \$(pgrep -f 'python.*bot.main.*mira_bot') | grep '\.log'"

# Читать актуальный лог (замени на правильное имя файла)
ssh root@31.44.7.144 "tail -50 /root/mira_bot/logs/bot_YYYY-MM-DD_HH-MM-SS_XXXXXX.log"
```

**Логи API:**
```bash
ssh root@31.44.7.144 "tail -50 /var/log/mira_webapp.log"
```

## 🛠 Стек и Технические принципы (Stack)
*Python 3.10+ | PTB v21 | SQLAlchemy 2.0 (Async) | Claude Sonnet 4.5*

- **AsyncIO:** Весь I/O (БД, Telegram API, AI streaming) должен быть асинхронным (`async/await`). Не блокируй Event Loop.
- **Telegram Bot API:** Используем `python-telegram-bot` v21.0+.
  - Используй `ApplicationBuilder`, а не старый `Updater`.
  - Хендлеры в `bot/handlers/`.
- **Database (SQLAlchemy 2.0):**
  - **Только Async Session.**
  - Используй синтаксис 2.0 (`await session.execute(select(User)...)`), а не старый `query()`.
  - **Pattern:** Доступ к данным ТОЛЬКО через Repositories (`database/repositories/`). Не пиши SQL-запросы в хендлерах. **Почему:** Чтобы легко мокать БД в тестах и не дублировать логику.
- **WebApp (FastAPI):** Backend для Mini App лежит в `webapp/api`.
  - **Frontend:** HTML/CSS/JS в `webapp/frontend/`, раздаётся через nginx.
  - **API:** FastAPI routes в `webapp/api/routes/`.

## 🧠 Архитектура и Логика (Architecture)
*Ключевые особенности, которые нельзя ломать.*

- **AI Streaming:** Ответы Claude должны стримиться (обновлять сообщение в реальном времени). Не буферизируй весь ответ, если это не короткая команда.
- **Mood Analysis:** Анализ настроения (`ai/mood_analyzer.py`) происходит *после* генерации или параллельно, но не блокирует ответ. 12 эмоций.
- **Crisis Detection:** Детекция кризиса (`services/crisis.py`) имеет высший приоритор. Если обнаружен маркер суицида — прерываем обычный флоу и шлем хелплайн.
- **Onboarding System:**
  - Новые пользователи проходят онбординг через `ConversationHandler` в `bot/handlers/onboarding.py`.
  - Собирается расширенный профиль: партнёр, дети, интересы, музыкальные/фильмовые предпочтения.
  - Данные сохраняются в `user_profiles` и `onboarding_events` таблицы.
- **Profile Extraction:**
  - AI-парсинг профиля из переписки: `ai/profile_extractor.py`
  - Админ может триггернуть через кнопку "Собрать на основе диалога" в админке.
- **Безопасность:**
  - Весь пользовательский ввод прогонять через `utils/sanitizer.py` (XSS, SQLi, длина).
  - Rate Limits проверяются через Redis *до* вызова LLM.

## 📝 Стиль кода и Правила (Style)

- **Типизация:** Используй `msg: str | None` (Python 3.10 style) вместо `Union[str, None]`. Все функции должны иметь type hints.
- **Ошибки:** Graceful degradation. Если Claude API упал (`APIConnectionError`), бот должен ответить заготовкой и залогировать тег `error:api_connection`, а не крашиться.
- **Контекст:** Помни про лимиты токенов. История грузится через `Context Builder`, лимит 10 (Free) / 20 (Premium) сообщений.
- **Логирование:** Используй `loguru.logger` везде. Уровни: `DEBUG` (детали), `INFO` (важные события), `WARNING` (проблемы), `ERROR` (ошибки).
- **Именование:**
  - Python: `snake_case` для функций/переменных, `PascalCase` для классов.
  - JavaScript: `camelCase` для функций/переменных.
  - CSS: `kebab-case` для классов.

## 🎨 Frontend Guidelines (Admin Panel)

### Структура
- **HTML:** `webapp/frontend/admin.html` - монолитный SPA
- **CSS:** Inline в `<style>` блоке, Material Design 3 переменные
- **JavaScript:** Inline в `<script>` блоке, нативный JS (без фреймворков)

### Design System
- **Цвета:** Используй CSS variables (`var(--md-sys-color-primary)`) из Material Design 3
- **Компоненты:**
  - Кнопки: `.md-button`, `.md-button-filled`, `.md-button-outlined`
  - Карточки: `.profile-section`, `.config-card`
  - Модальные окна: `.dialog-overlay` + `.dialog`
- **Анимации:** Используй `@keyframes` для плавности (fade, slide, spin)
- **Адаптивность:** Grid layouts с `repeat(auto-fill, minmax(280px, 1fr))`

### JavaScript Patterns
- **API Calls:** Через `apiRequest(endpoint, options)` helper
- **State Management:** Простые глобальные переменные (`currentChatTelegramId`, `userDialogCache`)
- **Error Handling:** `try/catch` + `showToast()` для уведомлений
- **Caching:** Кеш данных в объектах (`userFilesCache`, `apiCostsCache`)

### Common Pitfalls
- **XSS:** Всегда используй `escapeHtml()` перед вставкой пользовательских данных в DOM
- **Date Formatting:** Используй `toLocaleString('ru-RU', ...)` для русских дат
- **Material Icons:** Шрифт уже подключен, используй `<span class="material-icons">icon_name</span>`

## 🚫 Запреты (Never Do)
- **Музыка:** Функционал музыки выпилен. Не предлагай и не пытайся восстановить код, связанный с генерацией музыки.
- **Синхронные вызовы:** Никаких `requests` или `time.sleep()`. Только `httpx` и `asyncio.sleep()`.
- **Хардкод:** Токены и ID админов берем только из `config/settings.py` (Pydantic), который читает `.env`.
- **Прямые SQL запросы:** Только через Repositories, даже для простых SELECT.
- **Игнорирование ошибок:** Всегда логируй исключения с контекстом.

## 📊 Database Schema (Key Tables)

### users
- `telegram_id` (BIGINT, PK) - ID из Telegram
- `first_name`, `last_name`, `username` - данные из Telegram
- `display_name` - имя для отображения (приоритет над first_name)
- `subscription_plan` - free/trial/premium
- `onboarding_completed` (BOOL) - прошёл ли онбординг
- `last_active_at` - последняя активность

### user_profiles
- Расширенный профиль пользователя
- Базовая информация: `country`, `city`, `age`, `occupation`, `hobbies`
- Партнёр: `has_partner`, `partner_name`, `partner_age`, `partner_occupation`
- Отношения: `relationship_start_date`, `wedding_date`, `how_met`
- Дети: `has_children`, `children_count`, `children` (JSONB)
- Предпочтения: `music_preferences` (JSONB), `movie_preferences` (JSONB)

### messages
- История переписки
- `role` - user/assistant
- `content` - текст сообщения
- `message_type` - text/voice/photo
- `tags` (JSONB) - метки для поиска
- `tokens_used` - расход токенов

### user_files
- Файлы пользователей в GCS
- `file_type` - photo/voice/video/document
- `gcs_path`, `gcs_url` - путь в облаке
- `message_id` - связь с Telegram message
- `expires_at` - когда удалить (retention policy)

## 🔧 Troubleshooting

### "Изменения не применяются в браузере"
1. Проверь MD5: `md5sum /var/www/miradrug/webapp/admin.html` vs локальный файл
2. Проверь nginx config: `cat /etc/nginx/sites-enabled/miradrug.ru | grep admin`
3. Перезагрузи nginx: `ssh root@31.44.7.144 "systemctl reload nginx"`
4. Очисти кеш браузера: DevTools → Application → Clear site data
5. Попробуй режим инкогнито

### "API endpoint 404"
1. Проверь роут зарегистрирован: `grep "@router.post" webapp/api/routes/admin.py`
2. Проверь роут подключен в `webapp/api/main.py`
3. Проверь логи: `tail -f /var/log/mira_webapp.log`
4. Перезапусти API (см. команды деплоя выше)

### "Database migration failed"
1. Проверь подключение: `alembic current`
2. Откати: `alembic downgrade -1`
3. Пересоздай: `alembic revision --autogenerate -m "fix"`
4. Примени: `alembic upgrade head`

## 📚 Useful Links
- **Telegram Bot API:** https://docs.python-telegram-bot.org/
- **SQLAlchemy 2.0:** https://docs.sqlalchemy.org/en/20/
- **Claude API:** https://docs.anthropic.com/
- **Material Design 3:** https://m3.material.io/

## 🎯 Current Version
**v2.13.0** - Переработана вкладка Профиль с AI-парсингом + улучшены Файлы и Переписка
