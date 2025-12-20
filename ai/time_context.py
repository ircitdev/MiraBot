"""
Time Context Module.
Предоставляет информацию о текущем времени, дне недели, праздниках.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from loguru import logger
import pytz


# Русские названия дней недели
WEEKDAY_NAMES = {
    0: "понедельник",
    1: "вторник",
    2: "среда",
    3: "четверг",
    4: "пятница",
    5: "суббота",
    6: "воскресенье",
}

# Русские названия месяцев (родительный падеж для дат)
MONTH_NAMES_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}

# Российские праздники (месяц, день) -> название
RUSSIAN_HOLIDAYS = {
    (1, 1): "Новый год",
    (1, 2): "Новогодние каникулы",
    (1, 3): "Новогодние каникулы",
    (1, 4): "Новогодние каникулы",
    (1, 5): "Новогодние каникулы",
    (1, 6): "Новогодние каникулы",
    (1, 7): "Рождество",
    (1, 8): "Новогодние каникулы",
    (2, 14): "День святого Валентина",
    (2, 23): "День защитника Отечества",
    (3, 8): "Международный женский день",
    (5, 1): "Праздник Весны и Труда",
    (5, 9): "День Победы",
    (6, 12): "День России",
    (11, 4): "День народного единства",
    (12, 31): "Канун Нового года",
}

# Особые дни (не выходные, но значимые)
SPECIAL_DAYS = {
    (9, 1): "День знаний",
    (10, 5): "День учителя",
    (6, 1): "День защиты детей",
}


class TimeContext:
    """Контекст времени для бота."""

    def __init__(self, timezone: str = "Europe/Moscow"):
        """
        Args:
            timezone: Часовой пояс пользователя
        """
        self.timezone_str = timezone
        try:
            self.timezone = pytz.timezone(timezone)
        except Exception:
            self.timezone = pytz.timezone("Europe/Moscow")
            self.timezone_str = "Europe/Moscow"

    def get_current_datetime(self) -> datetime:
        """Возвращает текущее время в часовом поясе пользователя."""
        return datetime.now(self.timezone)

    def get_weekday_name(self, dt: Optional[datetime] = None) -> str:
        """Возвращает название дня недели по-русски."""
        if dt is None:
            dt = self.get_current_datetime()
        return WEEKDAY_NAMES[dt.weekday()]

    def is_weekend(self, dt: Optional[datetime] = None) -> bool:
        """Проверяет, является ли день выходным (суббота или воскресенье)."""
        if dt is None:
            dt = self.get_current_datetime()
        return dt.weekday() >= 5

    def get_holiday(self, dt: Optional[datetime] = None) -> Optional[str]:
        """
        Проверяет, является ли день праздником.

        Returns:
            Название праздника или None
        """
        if dt is None:
            dt = self.get_current_datetime()

        key = (dt.month, dt.day)

        # Сначала проверяем официальные праздники
        if key in RUSSIAN_HOLIDAYS:
            return RUSSIAN_HOLIDAYS[key]

        # Потом особые дни
        if key in SPECIAL_DAYS:
            return SPECIAL_DAYS[key]

        return None

    def get_time_of_day(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Определяет время суток.

        Returns:
            Dict с периодом и рекомендацией по тону
        """
        if dt is None:
            dt = self.get_current_datetime()

        hour = dt.hour

        if 5 <= hour < 10:
            return {
                "period": "раннее утро",
                "period_short": "утро",
                "tone_hint": "мягкая, пробуждающая",
                "greeting": "Доброе утро",
            }
        elif 10 <= hour < 12:
            return {
                "period": "утро",
                "period_short": "утро",
                "tone_hint": "бодрая, энергичная",
                "greeting": "Доброе утро",
            }
        elif 12 <= hour < 17:
            return {
                "period": "день",
                "period_short": "день",
                "tone_hint": "деловая, поддерживающая",
                "greeting": "Добрый день",
            }
        elif 17 <= hour < 21:
            return {
                "period": "вечер",
                "period_short": "вечер",
                "tone_hint": "расслабленная, рефлексивная",
                "greeting": "Добрый вечер",
            }
        elif 21 <= hour < 24:
            return {
                "period": "поздний вечер",
                "period_short": "вечер",
                "tone_hint": "спокойная, интимная",
                "greeting": "Добрый вечер",
            }
        else:  # 0-5
            return {
                "period": "ночь",
                "period_short": "ночь",
                "tone_hint": "очень мягкая, заботливая (ночное время — может быть бессонница или тревога)",
                "greeting": "Привет",
            }

    def get_date_readable(self, dt: Optional[datetime] = None) -> str:
        """
        Возвращает дату в человекочитаемом формате.

        Example: "19 декабря"
        """
        if dt is None:
            dt = self.get_current_datetime()

        day = dt.day
        month = MONTH_NAMES_GENITIVE[dt.month]
        return f"{day} {month}"

    def calculate_day_change(
        self,
        last_message_time: Optional[datetime],
    ) -> Dict[str, Any]:
        """
        Вычисляет информацию о смене дней с последнего сообщения.

        Args:
            last_message_time: Время последнего сообщения пользователя

        Returns:
            Dict с информацией о смене дней
        """
        now = self.get_current_datetime()

        if last_message_time is None:
            return {
                "is_new_day": True,
                "is_first_conversation": True,
                "days_passed": None,
            }

        # Приводим к одному часовому поясу
        if last_message_time.tzinfo is None:
            last_message_time = self.timezone.localize(last_message_time)
        else:
            last_message_time = last_message_time.astimezone(self.timezone)

        # Сравниваем даты (без времени)
        last_date = last_message_time.date()
        current_date = now.date()

        days_passed = (current_date - last_date).days

        result = {
            "is_new_day": days_passed >= 1,
            "is_first_conversation": False,
            "days_passed": days_passed,
        }

        # Добавляем контекст для приветствия
        if days_passed == 0:
            result["day_context"] = "продолжение разговора"
        elif days_passed == 1:
            result["day_context"] = "новый день (вчера общались)"
        elif days_passed == 2:
            result["day_context"] = "прошло 2 дня"
        elif 3 <= days_passed <= 7:
            result["day_context"] = f"прошло {days_passed} дней"
        elif days_passed > 7:
            result["day_context"] = f"давно не общались ({days_passed} дней)"

        return result

    def get_full_context(
        self,
        last_message_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Собирает полный временной контекст.

        Args:
            last_message_time: Время последнего сообщения пользователя

        Returns:
            Полный временной контекст для AI
        """
        now = self.get_current_datetime()
        time_of_day = self.get_time_of_day(now)
        day_change = self.calculate_day_change(last_message_time)

        context = {
            # Текущее время
            "current_time": now.strftime("%H:%M"),
            "current_hour": now.hour,
            "current_date": self.get_date_readable(now),
            "current_year": now.year,  # Год явно!

            # День недели
            "weekday": self.get_weekday_name(now),
            "weekday_number": now.weekday(),  # 0=пн, 6=вс
            "is_weekend": self.is_weekend(now),

            # Время суток
            "time_of_day": time_of_day["period"],
            "tone_hint": time_of_day["tone_hint"],
            "suggested_greeting": time_of_day["greeting"],

            # Праздники
            "holiday": self.get_holiday(now),

            # Смена дней
            "is_new_day": day_change["is_new_day"],
            "days_since_last_message": day_change["days_passed"],
            "day_context": day_change.get("day_context"),
        }

        # Добавляем контекстные подсказки для AI
        hints = []

        # Выходные
        if context["is_weekend"]:
            hints.append("выходной день — можно спросить о планах на отдых")

        # Праздник
        if context["holiday"]:
            hints.append(f"сегодня {context['holiday']} — можно поздравить")

        # Ночное время
        if now.hour < 5 or now.hour >= 23:
            hints.append("ночное время — возможно бессонница или тревога, быть особенно мягкой")

        # Новый день
        if day_change["is_new_day"]:
            if day_change["days_passed"] == 1:
                hints.append("начало нового дня — можно спросить как прошла ночь")
            elif day_change["days_passed"] and day_change["days_passed"] > 3:
                hints.append("давно не общались — спросить как дела за это время")

        # Понедельник
        if now.weekday() == 0 and now.hour < 12:
            hints.append("утро понедельника — можно спросить о планах на неделю")

        # Пятница вечер
        if now.weekday() == 4 and now.hour >= 17:
            hints.append("пятница вечер — можно спросить о планах на выходные")

        context["contextual_hints"] = hints

        return context


def get_time_context_for_user(
    timezone: str = "Europe/Moscow",
    last_message_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Вспомогательная функция для быстрого получения контекста.

    Args:
        timezone: Часовой пояс пользователя
        last_message_time: Время последнего сообщения

    Returns:
        Полный временной контекст
    """
    tc = TimeContext(timezone)
    return tc.get_full_context(last_message_time)
