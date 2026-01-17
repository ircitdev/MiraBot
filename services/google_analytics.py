"""
Google Analytics Data API integration.
Получение статистики лендинга через GA4 API.
"""

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    RunRealtimeReportRequest,
)
from google.oauth2 import service_account
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger

from config.settings import settings


class GoogleAnalyticsService:
    """Сервис для работы с Google Analytics Data API."""

    def __init__(self):
        self._client: Optional[BetaAnalyticsDataClient] = None
        self._initialized = False
        self._init_client()

    def _init_client(self):
        """Ленивая инициализация клиента GA4."""
        if self._initialized:
            return

        try:
            # Путь к credentials
            credentials_path = Path(__file__).parent.parent / settings.GOOGLE_ANALYTICS_CREDENTIALS_PATH

            if not credentials_path.exists():
                logger.warning(f"GA credentials not found: {credentials_path}")
                return

            # Инициализация credentials
            credentials = service_account.Credentials.from_service_account_file(
                str(credentials_path),
                scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            )

            # Создание клиента
            self._client = BetaAnalyticsDataClient(credentials=credentials)
            self._initialized = True

            logger.info("Google Analytics client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Google Analytics client: {e}")
            self._initialized = False

    @property
    def is_available(self) -> bool:
        """Проверяет доступность GA4 API."""
        return self._initialized and self._client is not None

    def get_landing_stats(self, days: int = 7) -> Dict:
        """
        Получить статистику лендинга за последние N дней.

        Args:
            days: Количество дней для анализа (по умолчанию 7)

        Returns:
            Dict с метриками:
            - views_total: Общее количество просмотров за период
            - views_today: Просмотры сегодня
            - unique_users: Уникальные пользователи
            - avg_session_duration: Средняя длительность сессии (секунды)
            - bounce_rate: Показатель отказов (%)
            - conversions: Количество конверсий (клики на кнопку)
            - top_sources: Топ-5 источников трафика
        """
        if not self.is_available:
            logger.warning("Google Analytics not available")
            return self._get_empty_stats()

        try:
            property_id = f"properties/{settings.GOOGLE_ANALYTICS_PROPERTY_ID}"

            # Запрос за весь период
            request = RunReportRequest(
                property=property_id,
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
                metrics=[
                    Metric(name="screenPageViews"),
                    Metric(name="activeUsers"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="bounceRate"),
                    Metric(name="eventCount"),
                ],
                dimensions=[
                    Dimension(name="date"),
                ],
            )

            response = self._client.run_report(request)

            # Запрос за сегодня
            today_request = RunReportRequest(
                property=property_id,
                date_ranges=[DateRange(start_date="today", end_date="today")],
                metrics=[Metric(name="screenPageViews")],
            )

            today_response = self._client.run_report(today_request)

            # Запрос источников трафика
            sources_request = RunReportRequest(
                property=property_id,
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
                metrics=[Metric(name="activeUsers")],
                dimensions=[Dimension(name="sessionSource")],
                limit=5,
                order_bys=[{"metric": {"metric_name": "activeUsers"}, "desc": True}],
            )

            sources_response = self._client.run_report(sources_request)

            # Парсинг данных - суммируем метрики по всем дням
            total_views = 0
            total_users = 0
            total_duration = 0
            total_bounce = 0
            timeline = []

            for row in response.rows:
                date_str = row.dimension_values[0].value  # YYYYMMDD
                views = int(row.metric_values[0].value)
                users = int(row.metric_values[1].value)
                duration = float(row.metric_values[2].value)
                bounce = float(row.metric_values[3].value)

                total_views += views
                total_users += users
                total_duration += duration
                total_bounce += bounce

                # Форматируем дату для timeline
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

                # Получаем конверсии для этого дня
                day_conversions = self._get_conversions_by_date(property_id, formatted_date)

                timeline.append({
                    "date": formatted_date,
                    "views": views,
                    "users": users,
                    "conversions": day_conversions,
                })

            # Средние значения
            num_days = len(response.rows) if response.rows else 1
            avg_duration = round(total_duration / num_days) if num_days > 0 else 0
            avg_bounce = round((total_bounce / num_days) * 100, 1) if num_days > 0 else 0

            stats = {
                "views_total": total_views,
                "views_today": int(today_response.rows[0].metric_values[0].value) if today_response.rows else 0,
                "unique_users": total_users,
                "avg_session_duration": avg_duration,
                "bounce_rate": avg_bounce,
                "conversions": self._get_conversions(property_id, days),
                "top_sources": self._parse_sources(sources_response),
                "timeline": timeline,
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get landing stats: {e}")
            return self._get_empty_stats()

    def get_realtime_users(self) -> int:
        """
        Получить количество пользователей онлайн (за последние 30 минут).

        Returns:
            Количество активных пользователей
        """
        if not self.is_available:
            return 0

        try:
            property_id = f"properties/{settings.GOOGLE_ANALYTICS_PROPERTY_ID}"

            request = RunRealtimeReportRequest(
                property=property_id,
                metrics=[Metric(name="activeUsers")],
            )

            response = self._client.run_realtime_report(request)

            if response.rows:
                return int(response.rows[0].metric_values[0].value)

            return 0

        except Exception as e:
            logger.error(f"Failed to get realtime users: {e}")
            return 0

    def _get_conversions(self, property_id: str, days: int) -> int:
        """Получить количество конверсий (событие: bot_start_click)."""
        try:
            request = RunReportRequest(
                property=property_id,
                date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
                metrics=[Metric(name="eventCount")],
                dimension_filter={
                    "filter": {
                        "field_name": "eventName",
                        "string_filter": {"value": "bot_start_click"}
                    }
                },
            )

            response = self._client.run_report(request)

            if response.rows:
                return int(response.rows[0].metric_values[0].value)

            return 0

        except Exception as e:
            logger.warning(f"Failed to get conversions: {e}")
            return 0

    def _get_conversions_by_date(self, property_id: str, date: str) -> int:
        """
        Получить количество конверсий за конкретную дату.

        Args:
            property_id: ID Google Analytics property
            date: Дата в формате YYYY-MM-DD

        Returns:
            Количество конверсий
        """
        try:
            request = RunReportRequest(
                property=property_id,
                date_ranges=[DateRange(start_date=date, end_date=date)],
                metrics=[Metric(name="eventCount")],
                dimension_filter={
                    "filter": {
                        "field_name": "eventName",
                        "string_filter": {"value": "bot_start_click"}
                    }
                },
            )

            response = self._client.run_report(request)

            if response.rows:
                return int(response.rows[0].metric_values[0].value)

            return 0

        except Exception as e:
            # Не логируем ошибки для каждой даты, чтобы не засорять логи
            return 0

    def _parse_sources(self, response) -> list:
        """Парсинг топ источников трафика."""
        sources = []
        for row in response.rows[:5]:
            source = row.dimension_values[0].value
            users = int(row.metric_values[0].value)
            sources.append({"source": source, "users": users})
        return sources

    def _get_empty_stats(self) -> Dict:
        """Возвращает пустую статистику при ошибке."""
        return {
            "views_total": 0,
            "views_today": 0,
            "unique_users": 0,
            "avg_session_duration": 0,
            "bounce_rate": 0,
            "conversions": 0,
            "top_sources": [],
            "timeline": [],
        }


# Глобальный экземпляр сервиса (Singleton)
analytics_service = GoogleAnalyticsService()
