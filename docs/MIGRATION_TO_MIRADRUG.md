# Миграция на домен miradrug.ru

## 📋 Дата миграции: 03.01.2026

---

## 🎯 Цель миграции

Перенос всех сервисов с `mira.uspeshnyy.ru` на новый домен `miradrug.ru`

**Причины:**
- Более запоминающийся домен
- Соответствие позиционированию "Мира — друг"
- Собственный бренд без привязки к uspeshnyy.ru

---

## ✅ Выполненные изменения

### 1. DNS конфигурация
- ✅ Зарегистрирован домен `miradrug.ru`
- ✅ Настроена A-запись: `31.44.7.144`
- ✅ Получен SSL сертификат через Let's Encrypt

### 2. Nginx конфигурация
**Файл:** `/etc/nginx/sites-available/miradrug.ru`

**Структура:**
- Landing page: `https://miradrug.ru/` → `/var/www/miradrug/landing/`
- Админка: `https://miradrug.ru/admin` → `/var/www/miradrug/webapp/`
- API: `https://miradrug.ru/api/` → `http://127.0.0.1:8081/`
- Privacy: `https://miradrug.ru/privacy` → `/var/www/freescout/docs/privacy.html`

**Редирект старого домена:**
```nginx
# Старый домен автоматически перенаправляет на новый
server {
    listen 443 ssl http2;
    server_name mira.uspeshnyy.ru;
    return 301 https://miradrug.ru$request_uri;
}
```

### 3. Landing Page
**Файл:** `docs/landing/index.html`

**Изменения:**
- ✅ Обновлены CTA ссылки: `https://t.me/mira_psychologist_bot?start=landing`
- ✅ Обновлена ссылка на privacy: `/privacy`
- ✅ Загружен на сервер: `/var/www/miradrug/landing/index.html`

### 4. Админка
**Файл:** `webapp/api/main.py`

**Изменения CORS:**
```python
allow_origins=[
    "https://web.telegram.org",
    "https://miradrug.ru",
    "http://miradrug.ru",
    "https://www.miradrug.ru",
    "http://www.miradrug.ru",
    # Старый домен для обратной совместимости
    "https://mira.uspeshnyy.ru",
    "http://mira.uspeshnyy.ru",
]
```

**Загружено на сервер:**
- ✅ `admin.html` → `/var/www/miradrug/webapp/`
- ✅ `main.py` → `/root/mira_bot/webapp/api/`

### 5. Telegram Bot
**Файл:** `bot/handlers/admin.py`

**Изменения:**
```python
# Было:
admin_url = f"https://mira.uspeshnyy.ru/admin?token={jwt_token}"

# Стало:
admin_url = f"https://miradrug.ru/admin?token={jwt_token}"
```

**Обновлено в 2 местах:**
- Команда `/admin`
- Callback `admin:web_admin`

**Загружено на сервер:**
- ✅ `admin.py` → `/root/mira_bot/bot/handlers/`

### 6. SSL Сертификат
**Команда получения:**
```bash
certbot certonly --webroot \
  -w /var/www/miradrug/landing \
  -d miradrug.ru \
  -d www.miradrug.ru \
  --non-interactive --agree-tos \
  --email noreply@miradrug.ru
```

**Сертификаты:**
- Certificate: `/etc/letsencrypt/live/miradrug.ru/fullchain.pem`
- Key: `/etc/letsencrypt/live/miradrug.ru/privkey.pem`
- Срок действия: до 03.04.2026 (90 дней)
- Автообновление: настроено через certbot

---

## 🔗 Новые URL

### Публичные
- **Landing:** https://miradrug.ru
- **Privacy:** https://miradrug.ru/privacy
- **Админка:** https://miradrug.ru/admin?token=JWT_TOKEN

### API (внутренние)
- **API Endpoint:** https://miradrug.ru/api/
- **Порт на сервере:** 8081

### Telegram Bot
- **Бот:** https://t.me/mira_psychologist_bot
- **Landing link:** https://t.me/mira_psychologist_bot?start=landing

---

## 📂 Структура на сервере

```
/var/www/miradrug/
├── landing/
│   └── index.html              # Landing page
└── webapp/
    └── admin.html              # Админка

/root/mira_bot/
├── bot/
│   └── handlers/
│       └── admin.py            # Обновлённые URL
├── webapp/
│   └── api/
│       └── main.py             # Обновлённый CORS
└── docs/
    └── privacy.html            # Используется через symlink

/etc/nginx/sites-available/
└── miradrug.ru                 # Nginx конфигурация
```

---

## 🔄 Сервисы

### Запущенные сервисы
```bash
# Бот
systemctl status mirabot
# Active: active (running)

# WebApp (API)
systemctl status mira-webapp
# Active: active (running) on port 8081
```

### Команды управления
```bash
# Перезапуск бота
systemctl restart mirabot

# Перезапуск webapp
systemctl restart mira-webapp

# Перезагрузка Nginx
systemctl reload nginx

# Проверка SSL
certbot certificates
```

---

## ✔️ Проверка работоспособности

### 1. Landing Page
```bash
curl -I https://miradrug.ru
# Ожидается: HTTP/2 200
```

### 2. Админка
```bash
curl -I https://miradrug.ru/admin
# Ожидается: HTTP/2 200 (редирект на /admin)
```

### 3. API
```bash
curl https://miradrug.ru/api/health
# Ожидается: {"status":"ok"}
```

### 4. Privacy
```bash
curl -I https://miradrug.ru/privacy
# Ожидается: HTTP/2 200
```

### 5. Редирект старого домена
```bash
curl -I https://mira.uspeshnyy.ru
# Ожидается: HTTP/2 301 → https://miradrug.ru
```

---

## 📝 Обратная совместимость

### CORS
Старый домен `mira.uspeshnyy.ru` **СОХРАНЁН** в allow_origins для:
- Поддержки существующих сессий
- Плавного перехода пользователей
- Избежания ошибок CORS

### Редирект
Все запросы на `mira.uspeshnyy.ru` **автоматически перенаправляются** на `miradrug.ru`

### Telegram Bot
Бот **СРАЗУ** начинает отдавать новый URL при команде `/admin`

---

## 🚨 Важные замечания

### 1. Порт API
⚠️ **Важно:** API работает на порту **8081**, а не 8000!

В Nginx конфигурации указано:
```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8081/;
}
```

### 2. Privacy Page
Privacy page расположен в `/root/mira_bot/docs/privacy.html` и доступен по двум URL:
- `https://miradrug.ru/privacy`
- `https://miradrug.ru/privacy.html`

### 3. SSL Auto-Renewal
Certbot автоматически продлевает сертификат. Проверка:
```bash
systemctl status certbot.timer
# Должен быть active (waiting)
```

### 4. Старые ссылки
Все старые ссылки на `mira.uspeshnyy.ru` в боте заменены на `miradrug.ru`. Пользователи получат новые ссылки при следующем вызове `/admin`.

### 5. Очистка кэша браузера
После обновления admin.html необходимо очистить кэш браузера:
- **Chrome/Edge**: Ctrl+Shift+R или Ctrl+F5
- **Firefox**: Ctrl+Shift+R или Ctrl+F5
- **Safari**: Cmd+Option+R

Или открыть админку в режиме инкогнито для проверки.

---

## 📊 Метрики после миграции

### Проверить через 24 часа:
- [ ] Landing page загружается < 3 секунд
- [ ] Админка открывается корректно
- [ ] API отвечает без ошибок
- [ ] Нет ошибок CORS в браузере
- [ ] Редирект работает для всех страниц
- [ ] SSL сертификат валиден

### Проверить через 7 дней:
- [ ] Нет жалоб от пользователей
- [ ] Аналитика показывает трафик на новом домене
- [ ] Старый домен корректно редиректит

---

## 🔧 Rollback (если нужно)

### Откат на старый домен

**1. Nginx:**
```bash
# Отключить новый конфиг
rm /etc/nginx/sites-enabled/miradrug.ru

# Включить старый (если был отключен)
ln -sf /etc/nginx/sites-available/mira.uspeshnyy.ru /etc/nginx/sites-enabled/

# Перезагрузить
nginx -t && systemctl reload nginx
```

**2. Код бота:**
```bash
cd /root/mira_bot
git checkout HEAD -- bot/handlers/admin.py webapp/api/main.py
systemctl restart mirabot mira-webapp
```

**3. Landing:**
Восстановить старые ссылки вручную.

---

## 📞 Контакты и поддержка

**В случае проблем:**
1. Проверить логи Nginx: `/var/log/nginx/miradrug_error.log`
2. Проверить логи бота: `journalctl -u mirabot -f`
3. Проверить логи webapp: `journalctl -u mira-webapp -f`

**Telegram:** @uspeshnyy

---

**Дата создания:** 03.01.2026 04:22 MSK
**Статус:** ✅ Миграция завершена успешно
**Автор:** Claude Sonnet 4.5
