"""
Mood Analyzer.
Анализ эмоционального состояния пользователя из сообщений.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class MoodAnalysis:
    """Результат анализа настроения."""
    mood_score: int  # -5 до +5
    primary_emotion: str
    secondary_emotions: List[str]
    energy_level: Optional[int]  # 1-10
    anxiety_level: Optional[int]  # 1-10
    triggers: List[str]
    confidence: float  # 0.0-1.0


class MoodAnalyzer:
    """Анализатор настроения из текста сообщений."""

    # Эмоции и связанные ключевые слова
    EMOTIONS = {
        "happy": {
            "score": 4,
            "keywords": [
                "счастлива", "счастлив", "рада", "рад", "радость", "радуюсь",
                "прекрасно", "замечательно", "отлично", "супер", "класс",
                "люблю", "любовь", "нравится", "обожаю", "восторг",
                "воодушевление", "вдохновляет", "благодарна", "благодарю",
                "ура", "йес", "да!", "наконец-то", "получилось",
            ],
            "patterns": [
                r"так\s+хорошо",
                r"очень\s+рада?",
                r"наконец[- ]то",
            ],
        },
        "calm": {
            "score": 2,
            "keywords": [
                "спокойно", "спокойна", "умиротворение", "гармония",
                "расслабилась", "отдыхаю", "нормально", "хорошо",
                "стабильно", "ровно", "тихо", "мирно",
            ],
            "patterns": [
                r"всё\s+хорошо",
                r"всё\s+нормально",
            ],
        },
        "neutral": {
            "score": 0,
            "keywords": [
                "обычно", "как всегда", "ничего особенного",
                "так себе", "неплохо", "нормально",
            ],
            "patterns": [],
        },
        "tired": {
            "score": -1,
            "keywords": [
                "устала", "устал", "усталость", "вымоталась",
                "нет сил", "измотана", "выжата", "без сил",
                "хочу спать", "не высыпаюсь", "сонливость",
                "энергии нет", "опустошена",
            ],
            "patterns": [
                r"сил\s+нет",
                r"нет\s+сил",
                r"так\s+устала",
            ],
        },
        "sad": {
            "score": -2,
            "keywords": [
                "грустно", "грусть", "печаль", "печально",
                "тоскливо", "тоска", "уныние", "унынье",
                "одиноко", "одинока", "никому не нужна",
                "плачу", "слёзы", "слезы", "плакала",
                "расстроена", "расстроилась", "обидно", "обижена",
            ],
            "patterns": [
                r"на\s+душе\s+тяжело",
                r"сердце\s+болит",
                r"не\s+могу\s+перестать\s+плакать",
            ],
        },
        "anxious": {
            "score": -2,
            "keywords": [
                "тревога", "тревожно", "тревожусь", "беспокоюсь",
                "волнуюсь", "волнение", "переживаю", "нервничаю",
                "страшно", "страх", "боюсь", "паника",
                "не могу успокоиться", "сердце колотится",
                "напряжена", "напряжение", "стресс",
            ],
            "patterns": [
                r"не\s+нахожу\s+места",
                r"места\s+себе\s+не\s+нахожу",
                r"руки\s+трясутся",
                r"панические?\s+атак",
            ],
        },
        "angry": {
            "score": -2,
            "keywords": [
                "злюсь", "злость", "бешусь", "бесит",
                "ненавижу", "раздражает", "раздражена",
                "выводит из себя", "достало", "достали",
                "ярость", "гнев", "взбешена", "в ярости",
            ],
            "patterns": [
                r"выводит\s+из\s+себя",
                r"терпение\s+лопнуло",
                r"больше\s+не\s+могу\s+терпеть",
            ],
        },
        "frustrated": {
            "score": -2,
            "keywords": [
                "разочарована", "разочарование", "обманута",
                "не понимают", "никто не слышит",
                "бессмысленно", "бесполезно", "ничего не выходит",
                "опять не получилось", "снова провал",
            ],
            "patterns": [
                r"что\s+бы\s+ни\s+делала",
                r"сколько\s+можно",
            ],
        },
        "hopeless": {
            "score": -4,
            "keywords": [
                "безнадёжно", "безнадежно", "отчаяние",
                "ничего не изменится", "выхода нет", "тупик",
                "руки опускаются", "сдаюсь", "всё пропало",
                "не вижу смысла", "зачем всё это",
            ],
            "patterns": [
                r"выхода\s+нет",
                r"ничего\s+не\s+изменится",
                r"всё\s+бесполезно",
            ],
        },
        "overwhelmed": {
            "score": -3,
            "keywords": [
                "не справляюсь", "захлёстывает", "тону",
                "слишком много", "не успеваю", "всё навалилось",
                "разрываюсь", "на пределе", "на грани",
            ],
            "patterns": [
                r"не\s+справляюсь",
                r"всё\s+навалилось",
                r"на\s+пределе",
            ],
        },
    }

    # Триггеры настроения (контекст)
    TRIGGERS = {
        "partner": [
            "муж", "мужа", "мужем", "супруг", "партнёр", "партнер",
            "он сказал", "он сделал", "между нами",
        ],
        "children": [
            "ребёнок", "ребенок", "дети", "детей", "сын", "дочь",
            "школа", "садик", "уроки",
        ],
        "work": [
            "работа", "работе", "работу", "начальник", "коллеги",
            "офис", "карьера", "проект", "дедлайн",
        ],
        "family": [
            "родители", "мама", "папа", "свекровь", "тёща", "теща",
            "родственники", "семья",
        ],
        "health": [
            "здоровье", "болезнь", "болит", "врач", "больница",
            "диагноз", "лечение",
        ],
        "finance": [
            "деньги", "денег", "финансы", "кредит", "долг",
            "зарплата", "расходы",
        ],
        "self": [
            "я сама", "для себя", "моя жизнь", "мечта", "цели",
            "саморазвитие", "хобби",
        ],
    }

    # Маркеры уровня энергии
    ENERGY_MARKERS = {
        "high": (8, [
            "энергия", "бодрость", "сила", "активна", "много дел",
            "продуктивно", "всё успеваю",
        ]),
        "medium": (5, [
            "нормально", "обычно", "средне",
        ]),
        "low": (2, [
            "устала", "нет сил", "вымотана", "еле двигаюсь",
            "не могу встать", "лежу", "апатия",
        ]),
    }

    # Маркеры уровня тревоги
    ANXIETY_MARKERS = {
        "high": (8, [
            "паника", "панические атаки", "не могу дышать",
            "сердце выскакивает", "трясёт", "трясусь",
        ]),
        "medium": (5, [
            "тревожно", "беспокоюсь", "переживаю", "волнуюсь",
        ]),
        "low": (2, [
            "немного волнуюсь", "чуть переживаю",
        ]),
    }

    def __init__(self):
        # Компилируем паттерны для каждой эмоции
        self.compiled_patterns = {}
        for emotion, data in self.EMOTIONS.items():
            self.compiled_patterns[emotion] = [
                re.compile(p, re.IGNORECASE) for p in data.get("patterns", [])
            ]

    def analyze(self, message: str) -> MoodAnalysis:
        """
        Анализирует сообщение и определяет настроение.

        Args:
            message: Текст сообщения пользователя

        Returns:
            MoodAnalysis с результатами
        """
        message_lower = message.lower()

        # 1. Определяем эмоции
        emotion_scores = self._detect_emotions(message_lower)

        # 2. Выбираем основную и вторичные эмоции
        primary_emotion, secondary_emotions = self._select_emotions(emotion_scores)

        # 3. Вычисляем mood_score
        mood_score = self._calculate_mood_score(emotion_scores)

        # 4. Определяем уровень энергии
        energy_level = self._detect_energy_level(message_lower)

        # 5. Определяем уровень тревоги
        anxiety_level = self._detect_anxiety_level(message_lower)

        # 6. Определяем триггеры
        triggers = self._detect_triggers(message_lower)

        # 7. Рассчитываем уверенность
        confidence = self._calculate_confidence(emotion_scores, message)

        return MoodAnalysis(
            mood_score=mood_score,
            primary_emotion=primary_emotion,
            secondary_emotions=secondary_emotions,
            energy_level=energy_level,
            anxiety_level=anxiety_level,
            triggers=triggers,
            confidence=confidence,
        )

    def _detect_emotions(self, message: str) -> Dict[str, float]:
        """Детектирует эмоции и их силу."""
        scores = {}

        for emotion, data in self.EMOTIONS.items():
            score = 0.0

            # Проверяем ключевые слова
            for keyword in data["keywords"]:
                if keyword in message:
                    score += 1.0

            # Проверяем паттерны
            for pattern in self.compiled_patterns.get(emotion, []):
                if pattern.search(message):
                    score += 1.5  # Паттерны имеют больший вес

            if score > 0:
                scores[emotion] = score

        return scores

    def _select_emotions(
        self, scores: Dict[str, float]
    ) -> Tuple[str, List[str]]:
        """Выбирает основную и вторичные эмоции."""
        if not scores:
            return "neutral", []

        # Сортируем по силе
        sorted_emotions = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        primary = sorted_emotions[0][0]

        # Вторичные — с силой больше 0.5 от основной
        primary_score = sorted_emotions[0][1]
        threshold = primary_score * 0.5

        secondary = [
            emotion for emotion, score in sorted_emotions[1:4]
            if score >= threshold
        ]

        return primary, secondary

    def _calculate_mood_score(self, emotion_scores: Dict[str, float]) -> int:
        """Вычисляет общий mood score от -5 до +5."""
        if not emotion_scores:
            return 0

        # Взвешенное среднее по силе эмоций
        total_weight = 0.0
        weighted_score = 0.0

        for emotion, strength in emotion_scores.items():
            base_score = self.EMOTIONS[emotion]["score"]
            weighted_score += base_score * strength
            total_weight += strength

        if total_weight == 0:
            return 0

        raw_score = weighted_score / total_weight

        # Ограничиваем диапазоном [-5, 5]
        return max(-5, min(5, round(raw_score)))

    def _detect_energy_level(self, message: str) -> Optional[int]:
        """Определяет уровень энергии."""
        for level, (score, keywords) in self.ENERGY_MARKERS.items():
            for keyword in keywords:
                if keyword in message:
                    return score
        return None

    def _detect_anxiety_level(self, message: str) -> Optional[int]:
        """Определяет уровень тревоги."""
        for level, (score, keywords) in self.ANXIETY_MARKERS.items():
            for keyword in keywords:
                if keyword in message:
                    return score
        return None

    def _detect_triggers(self, message: str) -> List[str]:
        """Определяет триггеры настроения."""
        triggers = []

        for trigger, keywords in self.TRIGGERS.items():
            for keyword in keywords:
                if keyword in message:
                    triggers.append(trigger)
                    break

        return triggers

    def _calculate_confidence(
        self, emotion_scores: Dict[str, float], message: str
    ) -> float:
        """Рассчитывает уверенность в анализе."""
        if not emotion_scores:
            return 0.3  # Базовая уверенность для нейтрального

        # Факторы уверенности:
        # 1. Количество найденных маркеров
        total_markers = sum(emotion_scores.values())

        # 2. Длина сообщения (больше текста — лучше анализ)
        message_length = len(message)

        # 3. Доминирование одной эмоции
        if emotion_scores:
            max_score = max(emotion_scores.values())
            total_score = sum(emotion_scores.values())
            dominance = max_score / total_score if total_score > 0 else 0
        else:
            dominance = 0

        # Формула уверенности
        confidence = min(1.0, (
            0.3 +  # Базовый уровень
            min(0.3, total_markers * 0.1) +  # До 0.3 за маркеры
            min(0.2, message_length / 500) +  # До 0.2 за длину
            dominance * 0.2  # До 0.2 за доминирование
        ))

        return round(confidence, 2)

    def get_mood_trend(
        self,
        mood_history: List[Dict[str, Any]],
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Анализирует тренд настроения за период.

        Args:
            mood_history: История записей mood
            days: Период анализа в днях

        Returns:
            Словарь с трендом и статистикой
        """
        if not mood_history:
            return {
                "trend": "unknown",
                "average_score": 0,
                "dominant_emotion": "neutral",
                "volatility": 0,
            }

        cutoff = datetime.now() - timedelta(days=days)
        recent = [m for m in mood_history if m.get("created_at", datetime.min) > cutoff]

        if not recent:
            return {
                "trend": "unknown",
                "average_score": 0,
                "dominant_emotion": "neutral",
                "volatility": 0,
            }

        scores = [m["mood_score"] for m in recent]
        emotions = [m["primary_emotion"] for m in recent]

        # Средний score
        average_score = sum(scores) / len(scores)

        # Тренд (сравниваем первую и вторую половину)
        mid = len(scores) // 2
        if mid > 0:
            first_half = sum(scores[:mid]) / mid
            second_half = sum(scores[mid:]) / len(scores[mid:])

            if second_half > first_half + 0.5:
                trend = "improving"
            elif second_half < first_half - 0.5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "unknown"

        # Доминирующая эмоция
        emotion_counts = {}
        for e in emotions:
            emotion_counts[e] = emotion_counts.get(e, 0) + 1
        dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0]

        # Волатильность (стандартное отклонение)
        if len(scores) > 1:
            mean = sum(scores) / len(scores)
            variance = sum((x - mean) ** 2 for x in scores) / len(scores)
            volatility = variance ** 0.5
        else:
            volatility = 0

        return {
            "trend": trend,
            "average_score": round(average_score, 1),
            "dominant_emotion": dominant_emotion,
            "volatility": round(volatility, 2),
            "entries_count": len(recent),
        }


# Глобальный экземпляр
mood_analyzer = MoodAnalyzer()
