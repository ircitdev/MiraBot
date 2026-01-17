# Google Analytics Integration - Инструкция по настройке

**Дата создания:** 10.01.2026
**Property ID:** G-3HDX50DR3W
**Landing URL:** https://miradrug.ru

---

## ✅ Что уже сделано

1. **Google Analytics подключен к лендингу**
   - Добавлен gtag.js в `docs/landing/index.html` (строки 24-32)
   - Файл загружен на сервер: `/var/www/miradrug/landing/index.html`
   - Tracking ID: `G-3HDX50DR3W`

2. **Лендинг доступен по адресу:** https://miradrug.ru

---

## 📊 Что нужно сделать для доступа к данным

Чтобы отображать статистику Google Analytics в админ-панели (Конфиг → Лендинг), нужно:

### Шаг 1: Создать Service Account в Google Cloud

1. Перейти в [Google Cloud Console](https://console.cloud.google.com/)
2. Создать новый проект или выбрать существующий
3. Включить **Google Analytics Data API (GA4)**:
   - Перейти в APIs & Services → Library
   - Найти "Google Analytics Data API"
   - Нажать "Enable"

4. Создать Service Account:
   - Перейти в APIs & Services → Credentials
   - Нажать "Create Credentials" → "Service Account"
   - Название: `mira-analytics-reader`
   - Описание: `Service account for Mira Bot analytics access`
   - Нажать "Create and Continue"

5. Выдать роль:
   - Выбрать роль: **Viewer** (только чтение)
   - Нажать "Continue" → "Done"

6. Создать ключ:
   - Нажать на созданный Service Account
   - Перейти в "Keys" → "Add Key" → "Create new key"
   - Формат: **JSON**
   - Скачать файл (например, `mira-analytics-credentials.json`)

### Шаг 2: Дать доступ Service Account к Google Analytics

1. Перейти в [Google Analytics](https://analytics.google.com/)
2. Выбрать нужный Property (G-3HDX50DR3W)
3. Перейти в Admin → Property → Property Access Management
4. Нажать "+" → "Add users"
5. Email: **email из Service Account** (найти в скачанном JSON в поле `client_email`)
   - Пример: `mira-analytics-reader@project-name.iam.gserviceaccount.com`
6. Роль: **Viewer**
7. Нажать "Add"

### Шаг 3: Загрузить credentials на сервер

```bash
# Скопировать JSON credentials на сервер
scp /path/to/mira-analytics-credentials.json root@31.44.7.144:/root/mira_bot/config/google_analytics_credentials.json

# Установить правильные права доступа
ssh root@31.44.7.144 "chmod 600 /root/mira_bot/config/google_analytics_credentials.json"
```

### Шаг 4: Установить Python библиотеку

```bash
ssh root@31.44.7.144
cd /root/mira_bot
source venv/bin/activate
pip install google-analytics-data
```

### Шаг 5: Узнать Property ID

1. Перейти в [Google Analytics](https://analytics.google.com/)
2. Admin → Property → Property Details
3. Скопировать **Property ID** (число, например: `123456789`)

---

## 🔧 Техническая реализация

### 1. Создать файл `services/google_analytics.py`

```python
"""
Google Analytics Data API integration.
"""

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class GoogleAnalyticsService:
    """Сервис для работы с Google Analytics Data API."""

    def __init__(self):
        """Инициализация клиента Google Analytics."""
        credentials_path = Path(__file__).parent.parent / "config" / "google_analytics_credentials.json"

        if not credentials_path.exists():
            raise FileNotFoundError(
                f"Google Analytics credentials not found at {credentials_path}. "
                "Please follow the setup instructions in docs/GOOGLE_ANALYTICS_SETUP.md"
            )

        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
        )

        self.client = BetaAnalyticsDataClient(credentials=credentials)

        # Property ID нужно указать после настройки
        # Найти в Google Analytics: Admin → Property → Property Details
        self.property_id = "properties/YOUR_PROPERTY_ID"  # Заменить на реальный ID

    def get_landing_stats(self, days: int = 7) -> Dict:
        """
        Получить статистику лендинга за последние N дней.

        Args:
            days: Количество дней для анализа (по умолчанию 7)

        Returns:
            Dict с ключами:
            - views_total: Общее количество просмотров
            - views_today: Просмотры сегодня
            - unique_users: Уникальные пользователи
            - avg_session_duration: Средняя длительность сессии (секунды)
            - bounce_rate: Показатель отказов (%)
            - conversions: Количество кликов на кнопку "Начать"
            - top_sources: Топ источников трафика
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        request = RunReportRequest(
            property=self.property_id,
            date_ranges=[
                DateRange(
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d"),
                )
            ],
            dimensions=[
                Dimension(name="date"),
                Dimension(name="sessionSource"),
            ],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="activeUsers"),
                Metric(name="averageSessionDuration"),
                Metric(name="bounceRate"),
                Metric(name="eventCount"),
            ],
        )

        response = self.client.run_report(request)

        # Обработка данных
        total_views = 0
        today_views = 0
        unique_users = 0
        total_duration = 0
        total_bounce = 0
        total_events = 0
        source_stats = {}

        today_str = datetime.now().strftime("%Y%m%d")

        for row in response.rows:
            date = row.dimension_values[0].value
            source = row.dimension_values[1].value
            views = int(row.metric_values[0].value)
            users = int(row.metric_values[1].value)
            duration = float(row.metric_values[2].value)
            bounce = float(row.metric_values[3].value)
            events = int(row.metric_values[4].value)

            total_views += views
            unique_users += users
            total_duration += duration
            total_bounce += bounce
            total_events += events

            if date == today_str:
                today_views += views

            # Агрегация по источникам
            if source not in source_stats:
                source_stats[source] = {"views": 0, "users": 0}
            source_stats[source]["views"] += views
            source_stats[source]["users"] += users

        # Топ источников (сортировка по количеству просмотров)
        top_sources = sorted(
            [{"source": k, **v} for k, v in source_stats.items()],
            key=lambda x: x["views"],
            reverse=True
        )[:5]

        row_count = len(response.rows)
        avg_session_duration = total_duration / row_count if row_count > 0 else 0
        bounce_rate = (total_bounce / row_count) if row_count > 0 else 0

        return {
            "views_total": total_views,
            "views_today": today_views,
            "unique_users": unique_users,
            "avg_session_duration": round(avg_session_duration, 2),
            "bounce_rate": round(bounce_rate * 100, 2),
            "conversions": total_events,  # Нужно настроить события в GA4
            "top_sources": top_sources,
        }

    def get_realtime_users(self) -> int:
        """
        Получить количество пользователей онлайн прямо сейчас.

        Returns:
            Количество активных пользователей
        """
        from google.analytics.data_v1beta.types import RunRealtimeReportRequest

        request = RunRealtimeReportRequest(
            property=self.property_id,
            metrics=[Metric(name="activeUsers")],
        )

        response = self.client.run_realtime_report(request)

        if response.rows:
            return int(response.rows[0].metric_values[0].value)
        return 0


# Singleton instance
analytics_service = GoogleAnalyticsService()
```

### 2. Создать API endpoint `webapp/api/routes/analytics.py`

```python
"""
Analytics API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from webapp.api.middleware import require_admin
from services.google_analytics import analytics_service


router = APIRouter(prefix="/analytics", tags=["analytics"])


class LandingStats(BaseModel):
    """Статистика лендинга."""
    views_total: int
    views_today: int
    unique_users: int
    avg_session_duration: float
    bounce_rate: float
    conversions: int
    top_sources: List[dict]
    realtime_users: int


@router.get("/landing", response_model=LandingStats)
async def get_landing_stats(
    days: int = 7,
    _admin: dict = Depends(require_admin)
):
    """
    Получить статистику лендинга за последние N дней.

    Требует права администратора.

    Query params:
        - days: Количество дней для анализа (по умолчанию 7, макс 30)
    """
    if days > 30:
        raise HTTPException(status_code=400, detail="Максимум 30 дней")

    try:
        stats = analytics_service.get_landing_stats(days=days)
        realtime = analytics_service.get_realtime_users()

        return {
            **stats,
            "realtime_users": realtime,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения статистики: {str(e)}"
        )
```

### 3. Зарегистрировать роутер в `webapp/api/main.py`

```python
from webapp.api.routes import analytics

app.include_router(analytics.router, prefix="/api", tags=["analytics"])
```

### 4. Обновить админ-панель `webapp/frontend/admin.html`

В функции `loadLandingStats()` (строка ~9250):

```javascript
async function loadLandingStats() {
    console.log('Loading landing stats...');
    const container = document.getElementById('landing-stats-container');

    try {
        // Показываем загрузку
        container.innerHTML = '<div class="loading"><div class="spinner"></div><div>Загрузка статистики...</div></div>';

        // Получаем данные из Google Analytics API
        const data = await apiRequest('analytics/landing?days=7');

        // Обновляем карточки
        document.getElementById('landing-views-today').textContent = data.views_today.toLocaleString();
        document.getElementById('landing-views-week').textContent = data.views_total.toLocaleString();
        document.getElementById('landing-unique-users').textContent = data.unique_users.toLocaleString();
        document.getElementById('landing-realtime-users').textContent = data.realtime_users.toLocaleString();
        document.getElementById('landing-bounce-rate').textContent = `${data.bounce_rate.toFixed(1)}%`;
        document.getElementById('landing-avg-session').textContent = `${Math.round(data.avg_session_duration)}s`;
        document.getElementById('landing-conversions').textContent = data.conversions.toLocaleString();

        // Отображаем топ источников
        const sourcesHTML = data.top_sources.map(source => `
            <div class="source-item">
                <div class="source-name">${source.source}</div>
                <div class="source-stats">
                    ${source.views} просмотров | ${source.users} пользователей
                </div>
            </div>
        `).join('');

        document.getElementById('landing-top-sources').innerHTML = sourcesHTML;

        showToast('Статистика лендинга загружена', 'success');
    } catch (error) {
        console.error('Failed to load landing stats:', error);
        showToast('Ошибка загрузки статистики Google Analytics', 'error');

        // Показываем ошибку
        container.innerHTML = `
            <div class="error-message">
                <span class="material-icons">error</span>
                <div>Ошибка загрузки статистики</div>
                <div style="font-size: 12px; margin-top: 8px;">
                    ${error.message || 'Проверьте настройки Google Analytics'}
                </div>
            </div>
        `;
    }
}
```

---

## 📈 Метрики для отображения в админке

### Основные показатели:
1. **Просмотры сегодня** - `views_today`
2. **Просмотры за неделю** - `views_total`
3. **Уникальные пользователи** - `unique_users`
4. **Пользователи онлайн** - `realtime_users`
5. **Показатель отказов** - `bounce_rate` (%)
6. **Средняя длительность сессии** - `avg_session_duration` (секунды)
7. **Конверсии** - `conversions` (клики на "Начать")

### Топ источников трафика:
- Список из 5 топовых источников с количеством просмотров и пользователей
- Например: Google Organic, Direct, Telegram, Instagram, etc.

---

## 🎯 Настройка событий (Events) в Google Analytics

Чтобы отслеживать клики на кнопку "Начать с Мирой", добавить в лендинг:

```javascript
// В index.html, в обработчик клика кнопки "Начать"
document.querySelectorAll('.cta-button').forEach(button => {
    button.addEventListener('click', () => {
        // Отправка события в Google Analytics
        gtag('event', 'start_bot_click', {
            'event_category': 'engagement',
            'event_label': 'landing_cta',
            'value': 1
        });

        // Открытие бота
        window.open('https://t.me/MiraDrug_bot', '_blank');
    });
});
```

---

## 🔒 Безопасность

1. **Credentials файл:**
   - Хранить в `/root/mira_bot/config/` (вне веб-директории)
   - Права доступа: `chmod 600`
   - Добавить в `.gitignore`

2. **API endpoint:**
   - Доступен только администраторам (`require_admin`)
   - Rate limiting (макс 100 запросов/час)

3. **Service Account:**
   - Только роль **Viewer** (read-only)
   - Доступ только к одному Property

---

## 📝 Чеклист

- [ ] Создать Service Account в Google Cloud
- [ ] Включить Google Analytics Data API
- [ ] Скачать JSON credentials
- [ ] Дать доступ Service Account к GA4 Property
- [ ] Загрузить credentials на сервер
- [ ] Установить `google-analytics-data` библиотеку
- [ ] Узнать Property ID
- [ ] Создать `services/google_analytics.py`
- [ ] Создать `webapp/api/routes/analytics.py`
- [ ] Обновить `webapp/api/main.py`
- [ ] Обновить `webapp/frontend/admin.html`
- [ ] Добавить события (Events) на лендинге
- [ ] Протестировать API endpoint
- [ ] Проверить отображение в админке

---

## 🆘 Troubleshooting

### Ошибка "Property ID not found"
- Убедитесь, что указали правильный Property ID (число)
- Формат: `properties/123456789`

### Ошибка "Permission denied"
- Проверьте, что Service Account email добавлен в Property Access Management
- Роль должна быть минимум **Viewer**

### Ошибка "API not enabled"
- Перейдите в Google Cloud Console
- APIs & Services → Library
- Найдите "Google Analytics Data API" и включите

### Данные не обновляются
- Google Analytics обрабатывает данные с задержкой 24-48 часов для полных отчётов
- Real-time данные доступны мгновенно
- Для тестирования используйте Real-time отчёты

---

## 📚 Документация

- [Google Analytics Data API](https://developers.google.com/analytics/devguides/reporting/data/v1)
- [Python Client Library](https://github.com/googleapis/python-analytics-data)
- [GA4 Events Guide](https://developers.google.com/analytics/devguides/collection/ga4/events)

---

**Дата обновления:** 10.01.2026
**Версия:** 1.0
