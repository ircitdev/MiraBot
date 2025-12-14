# Mira Bot WebApp

Telegram Mini App для настроек и статистики бота Мира.

## Структура

```
webapp/
├── api/                    # FastAPI backend
│   ├── main.py            # Главный файл приложения
│   └── routes/            # API endpoints
│       ├── settings.py    # Настройки пользователя
│       └── stats.py       # Статистика и аналитика
├── frontend/              # Frontend приложения
│   ├── index.html        # Главная страница
│   ├── styles.css        # Стили
│   └── app.js            # JavaScript логика
└── run_server.py         # Скрипт запуска сервера
```

## Возможности

### Статистика
- 📊 Общее количество сообщений
- 📈 График настроения за неделю
- 💭 Топ обсуждаемых тем
- 😊 Распределение эмоций
- 🎁 Статус подписки

### Настройки
- ⚙️ Персона (Мира/Марк)
- 👤 Имя и партнёр
- 🎂 Праздничные даты
- ⏰ Ритуалы (утренние/вечерние check-in)
- 📬 Проактивные сообщения

## Запуск локально

1. Установить зависимости:
```bash
pip install -r requirements.txt
```

2. Запустить сервер:
```bash
python webapp/run_server.py
```

Сервер запустится на порту из `WEBAPP_PORT` (по умолчанию 8081).

## Деплой

### На сервере

1. Настроить переменные в `.env`:
```env
WEBAPP_DOMAIN=webapp.mirabot.com
WEBAPP_PORT=8081
```

2. Настроить nginx для проксирования:
```nginx
server {
    listen 443 ssl;
    server_name webapp.mirabot.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

3. Создать systemd service:
```ini
[Unit]
Description=Mira Bot WebApp
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/mira_bot
ExecStart=/root/mira_bot/venv/bin/python webapp/run_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

4. Запустить:
```bash
sudo systemctl enable mira-webapp
sudo systemctl start mira-webapp
```

### Настройка в BotFather

Для установки WebApp как кнопку меню:

```
/mybots
→ Выбрать бота
→ Bot Settings
→ Menu Button
→ Configure Menu Button
→ Ввести URL: https://webapp.mirabot.com
→ Текст кнопки: Настройки
```

## Безопасность

WebApp использует Telegram initData для авторизации:
- Проверка HMAC подписи
- Валидация данных пользователя
- Только HTTPS в production

## API Endpoints

### Settings
- `GET /api/settings/` - получить настройки
- `PATCH /api/settings/` - обновить настройки
- `POST /api/settings/rituals/{type}/enable` - включить ритуал
- `POST /api/settings/rituals/{type}/disable` - отключить ритуал

### Stats
- `GET /api/stats/` - получить статистику
- `GET /api/stats/mood/history?days=30` - история настроения
- `GET /api/stats/topics?limit=20` - список тем

## Разработка

### Горячая перезагрузка
Сервер запускается с `reload=True`, изменения применяются автоматически.

### Тестирование
Для локального тестирования можно использовать Telegram Web K:
```
https://web.telegram.org/k/#@your_bot?startapp
```

### Debug
Логи доступны в stdout при запуске сервера.

## Troubleshooting

**Проблема**: "Invalid hash"
**Решение**: Проверить что `TELEGRAM_BOT_TOKEN` в `.env` корректный

**Проблема**: CORS ошибки
**Решение**: Убедиться что домен в `allow_origins` совпадает с Telegram

**Проблема**: "User not found"
**Решение**: Пользователь должен сначала написать /start боту
