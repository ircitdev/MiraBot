"""
Детектор и трекер целей пользователя.
Помогает конвертировать расплывчатые цели в SMART формат.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from loguru import logger

from ai.claude_client import ClaudeClient
from database.repositories.goal import GoalRepository


class GoalTracker:
    """Детектор целей и конвертер в SMART формат."""

    # Паттерны упоминания целей
    GOAL_PATTERNS = [
        # Прямые формулировки
        "хочу", "хотела бы", "мечтаю", "планирую", "собираюсь",
        "моя цель", "моя мечта", "стремлюсь",

        # Желания
        "было бы здорово", "было бы классно", "мне бы",

        # Намерения
        "надо бы", "нужно", "стоит", "пора бы",

        # С будущим временем
        "буду", "начну", "попробую",
    ]

    # Категории целей
    GOAL_CATEGORIES = {
        "health": ["похудеть", "вес", "здоровье", "спорт", "зал", "йога", "питание", "диета"],
        "relationships": ["отношения", "муж", "дети", "семья", "мама", "папа", "друзья"],
        "work": ["работа", "карьера", "зарплата", "проект", "бизнес", "заработать"],
        "personal_growth": ["развитие", "курс", "учеба", "книга", "навык", "хобби"],
        "habits": ["привычка", "перестать", "бросить", "начать делать", "каждый день"],
        "emotions": ["спокойнее", "увереннее", "счастливее", "меньше нервничать"],
    }

    def __init__(self):
        self.goal_repo = GoalRepository()
        self.claude_client = ClaudeClient()

    def detect_goal_mention(self, message: str) -> bool:
        """
        Детектит упоминание цели в сообщении.

        Args:
            message: Текст сообщения

        Returns:
            True если обнаружено упоминание цели
        """
        message_lower = message.lower()

        # Проверяем наличие паттернов
        has_pattern = any(pattern in message_lower for pattern in self.GOAL_PATTERNS)

        if not has_pattern:
            return False

        # Проверяем что это не вопрос о прошлом
        past_indicators = ["хотела", "хотелось", "мечтала", "планировала"]
        is_past = any(ind in message_lower for ind in past_indicators)

        # Если в прошедшем времени — не цель
        if is_past and "но" not in message_lower and "теперь" not in message_lower:
            return False

        logger.debug(f"Detected potential goal mention in message: {message[:50]}...")
        return True

    def detect_category(self, message: str) -> Optional[str]:
        """
        Определяет категорию цели на основе ключевых слов.

        Args:
            message: Текст с упоминанием цели

        Returns:
            Название категории или None
        """
        message_lower = message.lower()

        for category, keywords in self.GOAL_CATEGORIES.items():
            if any(keyword in message_lower for keyword in keywords):
                return category

        return "other"

    async def convert_to_smart(
        self,
        user_id: int,
        original_goal: str,
    ) -> Dict[str, Any]:
        """
        Конвертирует расплывчатую цель в SMART формат через Claude API.

        Args:
            user_id: ID пользователя
            original_goal: Исходная формулировка цели

        Returns:
            Dict с SMART компонентами
        """
        # Промпт для конвертации
        prompt = self._build_smart_conversion_prompt(original_goal)

        # Генерируем через Claude
        response = await self.claude_client.generate_simple(
            system_prompt=self._get_smart_system_prompt(),
            user_prompt=prompt,
            max_tokens=600,
        )

        # Парсим ответ
        smart_components = self._parse_smart_response(response)

        logger.info(f"Converted goal to SMART for user {user_id}")
        return smart_components

    async def create_goal_with_smart(
        self,
        user_id: int,
        original_goal: str,
        reminder_frequency: str = "weekly",
    ) -> Optional[int]:
        """
        Создает цель с автоматической конвертацией в SMART.

        Args:
            user_id: ID пользователя
            original_goal: Исходная формулировка
            reminder_frequency: Частота напоминаний

        Returns:
            ID созданной цели или None
        """
        try:
            # Конвертируем в SMART
            smart = await self.convert_to_smart(user_id, original_goal)

            # Определяем категорию
            category = self.detect_category(original_goal)

            # Создаем цель
            goal = await self.goal_repo.create(
                user_id=user_id,
                original_goal=original_goal,
                smart_goal=smart.get("smart_goal"),
                specific=smart.get("specific"),
                measurable=smart.get("measurable"),
                achievable=smart.get("achievable"),
                relevant=smart.get("relevant"),
                time_bound=smart.get("time_bound"),
                category=category,
                reminder_frequency=reminder_frequency,
            )

            # Если есть milestones, добавляем их
            if smart.get("milestones"):
                goal.milestones = smart["milestones"]
                await self.goal_repo.update_progress(goal.id, progress=0)

            logger.info(f"Created SMART goal {goal.id} for user {user_id}")
            return goal.id

        except Exception as e:
            logger.error(f"Error creating SMART goal for user {user_id}: {e}")
            return None

    def _build_smart_conversion_prompt(self, goal: str) -> str:
        """Строит промпт для конвертации в SMART."""
        return f"""Преобразуй эту цель в SMART формат:

**Исходная цель:** "{goal}"

Создай SMART-версию цели, разбив на компоненты:

1. **Specific** (Конкретная) — что именно нужно сделать
2. **Measurable** (Измеримая) — как измерить прогресс
3. **Achievable** (Достижимая) — почему это реально
4. **Relevant** (Значимая) — почему это важно
5. **Time-bound** (Ограниченная во времени) — когда дедлайн

Также предложи 3-5 конкретных шагов (milestones) для достижения цели.

**Формат ответа:**

SMART цель: [одно предложение с SMART формулировкой]

Specific: [конкретика]
Measurable: [метрика]
Achievable: [почему достижимо]
Relevant: [почему важно]
Time-bound: [дата или срок]

Шаги:
1. [первый шаг]
2. [второй шаг]
3. [третий шаг]
"""

    def _get_smart_system_prompt(self) -> str:
        """Системный промпт для SMART конвертации."""
        return """Ты — эксперт по постановке целей (SMART framework).

Твоя задача — превратить расплывчатую цель в конкретную, измеримую, достижимую формулировку.

**Принципы:**
1. **Specific** — конкретная, понятная формулировка без абстракций
2. **Measurable** — четкая метрика (число, событие, наблюдаемое изменение)
3. **Achievable** — реалистичная для обычного человека
4. **Relevant** — связана с реальными потребностями
5. **Time-bound** — конкретный срок (не "когда-нибудь")

**Важно:**
- НЕ завышай ожидания ("стать самой счастливой" → "улучшить настроение")
- НЕ делай цели слишком долгосрочными (макс 3 месяца)
- Разбивай большие цели на маленькие шаги
- Используй метрики которые человек может сам отследить

**Тон:** дружелюбный, мотивирующий, но реалистичный.
"""

    def _parse_smart_response(self, response: str) -> Dict[str, Any]:
        """
        Парсит ответ от Claude и извлекает SMART компоненты.

        Args:
            response: Ответ от Claude API

        Returns:
            Dict с SMART компонентами
        """
        lines = response.strip().split("\n")

        smart_goal = None
        specific = None
        measurable = None
        achievable = None
        relevant = None
        time_bound_str = None
        milestones = []

        current_section = None

        for line in lines:
            line = line.strip()

            if line.startswith("SMART цель:") or line.startswith("SMART-цель:"):
                smart_goal = line.split(":", 1)[1].strip()
            elif line.startswith("Specific:"):
                specific = line.split(":", 1)[1].strip()
                current_section = "specific"
            elif line.startswith("Measurable:"):
                measurable = line.split(":", 1)[1].strip()
                current_section = "measurable"
            elif line.startswith("Achievable:"):
                achievable = line.split(":", 1)[1].strip()
                current_section = "achievable"
            elif line.startswith("Relevant:"):
                relevant = line.split(":", 1)[1].strip()
                current_section = "relevant"
            elif line.startswith("Time-bound:") or line.startswith("Time-Bound:"):
                time_bound_str = line.split(":", 1)[1].strip()
                current_section = "time_bound"
            elif line.startswith("Шаги:") or line.startswith("Steps:"):
                current_section = "milestones"
            elif current_section == "milestones" and line:
                # Извлекаем шаг (убираем нумерацию)
                if line[0].isdigit() and "." in line[:3]:
                    milestone_text = line.split(".", 1)[1].strip()
                    milestones.append({
                        "title": milestone_text,
                        "completed": False,
                        "completed_at": None
                    })

        # Парсим time_bound в datetime
        time_bound = self._parse_deadline(time_bound_str) if time_bound_str else None

        return {
            "smart_goal": smart_goal,
            "specific": specific,
            "measurable": measurable,
            "achievable": achievable,
            "relevant": relevant,
            "time_bound": time_bound,
            "milestones": milestones,
        }

    def _parse_deadline(self, deadline_str: str) -> Optional[datetime]:
        """
        Парсит строку с дедлайном в datetime.

        Args:
            deadline_str: Строка типа "через 2 недели", "30 дней", "1 месяц"

        Returns:
            datetime объект или None
        """
        deadline_lower = deadline_str.lower()

        try:
            # "через N дней/недель/месяцев"
            if "день" in deadline_lower or "дня" in deadline_lower or "дней" in deadline_lower:
                # Извлекаем число
                words = deadline_lower.split()
                for i, word in enumerate(words):
                    if word.isdigit():
                        days = int(word)
                        return datetime.utcnow() + timedelta(days=days)

            if "недел" in deadline_lower:
                words = deadline_lower.split()
                for i, word in enumerate(words):
                    if word.isdigit():
                        weeks = int(word)
                        return datetime.utcnow() + timedelta(weeks=weeks)

            if "месяц" in deadline_lower:
                words = deadline_lower.split()
                for i, word in enumerate(words):
                    if word.isdigit():
                        months = int(word)
                        # Примерно 30 дней на месяц
                        return datetime.utcnow() + timedelta(days=months * 30)

            # По умолчанию — через 30 дней
            return datetime.utcnow() + timedelta(days=30)

        except Exception as e:
            logger.warning(f"Failed to parse deadline '{deadline_str}': {e}")
            return datetime.utcnow() + timedelta(days=30)


# Глобальный экземпляр
goal_tracker = GoalTracker()
