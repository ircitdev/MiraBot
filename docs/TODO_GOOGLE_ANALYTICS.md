# TODO: Интеграция Google Analytics API

## ✅ Выполнено (локально)

1. ✅ Перемещен `google_analytics_credentials.json` в `config/`
2. ✅ Обновлен `requirements.txt` - добавлен `google-analytics-data==0.18.0`
3. ✅ Обновлен `config/settings.py` - добавлены GA настройки
4. ✅ Обновлен `.env` - добавлен Property ID `519188524`
5. ✅ Создан `services/google_analytics.py` - сервис для работы с GA4 API
6. ✅ Создан `webapp/api/routes/analytics.py` - API endpoint
7. ✅ Обновлен `webapp/api/main.py` - зарегистрирован роут

## 📋 Осталось сделать

### Локальная разработка

#### 1. Обновить `webapp/frontend/admin.html`

**Найти функцию `loadLandingStats()` (около строки 9275) и заменить на:**

```javascript
async function loadLandingStats() {
    console.log('Loading landing stats...');
    try {
        // Загружаем статистику из GA API
        const data = await apiRequest('analytics/landing?days=7');

        // Обновляем метрики в UI
        document.getElementById('landing-views-today').textContent = data.views_today.toLocaleString('ru-RU');
        document.getElementById('landing-views-week').textContent = data.views_total.toLocaleString('ru-RU');
        document.getElementById('landing-unique-users').textContent = data.unique_users.toLocaleString('ru-RU');
        document.getElementById('landing-users-online').textContent = data.users_online.toLocaleString('ru-RU');
        document.getElementById('landing-bounce-rate').textContent = data.bounce_rate.toFixed(1) + '%';
        document.getElementById('landing-avg-duration').textContent = formatDuration(data.avg_session_duration);
        document.getElementById('landing-conversions').textContent = data.conversions.toLocaleString('ru-RU');

        // Топ источников трафика
        const sourcesHtml = data.top_sources.map((source, index) => `
            <div class="traffic-source-item">
                <span class="source-rank">${index + 1}.</span>
                <span class="source-name">${source.source}</span>
                <span class="source-users">${source.users.toLocaleString('ru-RU')}</span>
            </div>
        `).join('');

        document.getElementById('landing-top-sources').innerHTML = sourcesHtml || '<p style="text-align: center; color: var(--md-sys-color-outline);">Нет данных</p>';

        showToast('Статистика лендинга загружена', 'success');
    } catch (error) {
        console.error('Failed to load landing stats:', error);

        // Показываем плейсхолдеры при ошибке
        document.getElementById('landing-views-today').textContent = '—';
        document.getElementById('landing-views-week').textContent = '—';
        document.getElementById('landing-unique-users').textContent = '—';
        document.getElementById('landing-users-online').textContent = '—';
        document.getElementById('landing-bounce-rate').textContent = '—';
        document.getElementById('landing-avg-duration').textContent = '—';
        document.getElementById('landing-conversions').textContent = '—';
        document.getElementById('landing-top-sources').innerHTML = '<p style="text-align: center; color: var(--md-sys-color-error);">Ошибка загрузки</p>';

        showToast('Ошибка загрузки статистики: ' + error.message, 'error');
    }
}

// Вспомогательная функция для форматирования длительности
function formatDuration(seconds) {
    if (seconds < 60) {
        return `${seconds} сек`;
    }
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes} мин ${secs} сек`;
}
```

#### 2. Добавить Event Tracking в `docs/landing/index.html`

**Найти кнопку "Начать с Мирой" и добавить после closing `</script>` тега Google Analytics:**

```html
<script>
// Отслеживание кликов на кнопку запуска бота
document.addEventListener('DOMContentLoaded', function() {
    const ctaButtons = document.querySelectorAll('a[href*="t.me/MiraDrugBot"]');
    ctaButtons.forEach(button => {
        button.addEventListener('click', function() {
            gtag('event', 'bot_start_click', {
                'event_category': 'engagement',
                'event_label': 'landing_cta',
                'value': 1
            });
        });
    });
});
</script>
```

---

### Деплой на сервер

#### 3. Загрузить файлы на сервер

```bash
# Credentials
scp config/google_analytics_credentials.json root@31.44.7.144:/root/mira_bot/config/

# Python файлы
scp services/google_analytics.py root@31.44.7.144:/root/mira_bot/services/
scp webapp/api/routes/analytics.py root@31.44.7.144:/root/mira_bot/webapp/api/routes/
scp webapp/api/main.py root@31.44.7.144:/root/mira_bot/webapp/api/
scp config/settings.py root@31.44.7.144:/root/mira_bot/config/
scp requirements.txt root@31.44.7.144:/root/mira_bot/

# Frontend
scp webapp/frontend/admin.html root@31.44.7.144:/root/mira_bot/webapp/frontend/
scp docs/landing/index.html root@31.44.7.144:/var/www/miradrug/landing/
```

#### 4. Установить зависимости на сервере

```bash
ssh root@31.44.7.144
cd /root/mira_bot
/root/mira_bot/venv/bin/pip install google-analytics-data==0.18.0
```

#### 5. Обновить .env на сервере

```bash
ssh root@31.44.7.144
cat >> /root/mira_bot/.env << 'EOF'

# Google Analytics
GOOGLE_ANALYTICS_PROPERTY_ID=519188524
GOOGLE_ANALYTICS_CREDENTIALS_PATH=config/google_analytics_credentials.json
EOF
```

#### 6. Установить права на credentials

```bash
chmod 600 /root/mira_bot/config/google_analytics_credentials.json
```

#### 7. Перезапустить веб-сервер

```bash
# Остановить текущий процесс
lsof -ti:8081 | xargs kill -9 2>/dev/null

# Запустить новый
cd /root/mira_bot
nohup /root/mira_bot/venv/bin/python -m uvicorn webapp.api.main:app --host 0.0.0.0 --port 8081 > /var/log/mira_webapp.log 2>&1 &
```

#### 8. Проверить логи

```bash
tail -f /var/log/mira_webapp.log
```

Ожидаемое сообщение:
```
INFO - Google Analytics client initialized successfully
INFO - Application startup complete
```

---

## Проверка работоспособности

### 1. API Endpoint

```bash
curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  "https://miradrug.ru/api/analytics/landing?days=7"
```

Ожидаемый ответ (пример):
```json
{
  "views_total": 1234,
  "views_today": 56,
  "unique_users": 789,
  "users_online": 3,
  "avg_session_duration": 145,
  "bounce_rate": 45.2,
  "conversions": 23,
  "top_sources": [
    {"source": "google", "users": 450},
    {"source": "direct", "users": 200}
  ]
}
```

### 2. Админ-панель

1. Открыть: https://miradrug.ru/admin.html
2. Перейти: Конфиг → Лендинг
3. Нажать: "Обновить статистику"
4. Проверить отображение всех метрик

### 3. Event Tracking

1. Открыть: https://miradrug.ru
2. DevTools → Console
3. Кликнуть: "Начать с Мирой"
4. Проверить событие в консоли

---

## Возможные проблемы

### "Failed to initialize Google Analytics client"

**Решение:**
```bash
ls -la /root/mira_bot/config/google_analytics_credentials.json
chmod 600 /root/mira_bot/config/google_analytics_credentials.json
cat /root/mira_bot/.env | grep GOOGLE_ANALYTICS
```

### "403 Forbidden" при запросе к GA API

**Решение:**
1. Проверить права Service Account в GA4
2. Admin → Property → Property Access Management
3. Добавить: `mira-analytics-reader@usptgbots.iam.gserviceaccount.com`
4. Роль: "Viewer"

### Нулевые метрики

**Причины:**
- Неправильный Property ID
- Нет трафика за период
- GA4 еще не собрал данные (подождать 24-48 часов)

---

## Статус выполнения

- [x] Конфигурация (settings, .env)
- [x] Сервис Google Analytics
- [x] API endpoint
- [x] Регистрация роута
- [ ] Обновление admin.html (loadLandingStats)
- [ ] Event tracking на лендинге
- [ ] Деплой на сервер
- [ ] Тестирование

---

## Метрики для отображения

В админке будут показываться:

1. **Просмотры сегодня** - `views_today`
2. **Просмотры за неделю** - `views_total`
3. **Уникальные пользователи** - `unique_users`
4. **Пользователи онлайн** - `users_online` (real-time)
5. **Показатель отказов** - `bounce_rate` (%)
6. **Средняя длительность** - `avg_session_duration` (сек)
7. **Конверсии** - `conversions` (клики на кнопку)
8. **Топ-5 источников** - `top_sources`

---

## Примечания

- Данные обновляются с задержкой 24-48 часов
- Real-time данные обновляются каждые 30 секунд
- Квота GA4 Data API: 200,000 токенов/день
- Property ID: **519188524**
- Tracking ID: **G-3HDX50DR3W**
