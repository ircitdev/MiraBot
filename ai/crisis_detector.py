"""
Crisis Detector.
Детекция кризисных сигналов в сообщениях пользователя.
"""

import re
from typing import Dict, Any, List
from config.settings import settings


class CrisisDetector:
    """Детектор кризисных состояний."""
    
    # Уровни кризиса
    LEVEL_LOW = "low"
    LEVEL_MEDIUM = "medium"
    LEVEL_HIGH = "high"
    LEVEL_CRITICAL = "critical"
    
    # Ключевые слова по уровням
    KEYWORDS = {
        LEVEL_CRITICAL: [
            "хочу умереть",
            "покончить с собой",
            "суицид",
            "убить себя",
            "не хочу жить",
            "конец всему",
            "лучше бы меня не было",
            "всем будет лучше без меня",
        ],
        LEVEL_HIGH: [
            "бьёт",
            "бьет",
            "ударил",
            "насилие",
            "боюсь за свою жизнь",
            "он угрожает",
            "порезать себя",
            "самоповреждение",
            "режу себя",
        ],
        LEVEL_MEDIUM: [
            "не вижу смысла",
            "всё бессмысленно",
            "не могу больше",
            "больше не могу",
            "хочу исчезнуть",
            "устала жить",
            "зачем я живу",
            "никому не нужна",
        ],
        LEVEL_LOW: [
            "очень плохо",
            "в отчаянии",
            "не выдержу",
            "на грани",
            "срываюсь",
            "панические атаки",
            "не могу дышать",
            "задыхаюсь от тревоги",
        ],
    }
    
    # Паттерны для более точного поиска
    PATTERNS = [
        r"хочу\s+(умереть|покончить|убить\s+себя)",
        r"(не\s+хочу|устала)\s+жить",
        r"лучше\s+бы\s+(меня|я)\s+не\s+было",
        r"(бьёт|бьет|ударил|избивает)\s+меня",
        r"(угрожает|грозится)\s+(убить|покалечить)",
    ]
    
    def __init__(self):
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.PATTERNS]
    
    def check(self, message: str) -> Dict[str, Any]:
        """
        Проверяет сообщение на наличие кризисных сигналов.
        
        Args:
            message: Текст сообщения
        
        Returns:
            {
                "is_crisis": bool,
                "level": Optional[str],  # low, medium, high, critical
                "matched_keywords": List[str],
                "recommendation": Optional[str]
            }
        """
        message_lower = message.lower()
        
        matched_keywords = []
        highest_level = None
        
        # Проверяем паттерны
        for pattern in self.compiled_patterns:
            if pattern.search(message_lower):
                # Паттерны обычно указывают на высокий уровень
                highest_level = self.LEVEL_HIGH
                matched_keywords.append(f"pattern:{pattern.pattern}")
        
        # Проверяем ключевые слова по уровням
        for level in [self.LEVEL_CRITICAL, self.LEVEL_HIGH, self.LEVEL_MEDIUM, self.LEVEL_LOW]:
            for keyword in self.KEYWORDS[level]:
                if keyword in message_lower:
                    matched_keywords.append(keyword)
                    if highest_level is None or self._level_priority(level) > self._level_priority(highest_level):
                        highest_level = level
        
        is_crisis = len(matched_keywords) > 0
        
        result = {
            "is_crisis": is_crisis,
            "level": highest_level,
            "matched_keywords": matched_keywords,
            "recommendation": self._get_recommendation(highest_level) if is_crisis else None,
        }
        
        return result
    
    def _level_priority(self, level: str) -> int:
        """Возвращает приоритет уровня (чем выше, тем критичнее)."""
        priorities = {
            self.LEVEL_LOW: 1,
            self.LEVEL_MEDIUM: 2,
            self.LEVEL_HIGH: 3,
            self.LEVEL_CRITICAL: 4,
        }
        return priorities.get(level, 0)
    
    def _get_recommendation(self, level: str) -> str:
        """Возвращает рекомендацию по действию."""
        recommendations = {
            self.LEVEL_CRITICAL: (
                f"Немедленно предоставить номер кризисной линии: {settings.CRISIS_HOTLINE}. "
                "Признать боль, выразить заботу, не оставлять одну."
            ),
            self.LEVEL_HIGH: (
                f"Мягко предложить помощь специалиста. Дать номер: {settings.CRISIS_HOTLINE}. "
                "Оставаться рядом, проявить эмпатию."
            ),
            self.LEVEL_MEDIUM: (
                "Проявить особую заботу и эмпатию. "
                "При необходимости упомянуть возможность профессиональной помощи."
            ),
            self.LEVEL_LOW: (
                "Быть особенно внимательным и поддерживающим. "
                "Отслеживать развитие ситуации."
            ),
        }
        return recommendations.get(level, "")
    
    def get_crisis_response_guide(self, level: str) -> Dict[str, Any]:
        """
        Возвращает гайд по реагированию на кризис.
        
        Args:
            level: Уровень кризиса
        
        Returns:
            Словарь с инструкциями для бота
        """
        guides = {
            self.LEVEL_CRITICAL: {
                "approach": "direct",
                "tone": "calm, warm, serious",
                "actions": [
                    "Признать боль и серьёзность",
                    "Не пытаться отвлечь или успокоить банальностями",
                    "Дать номер кризисной линии",
                    "Предложить остаться на связи",
                    "Спросить есть ли кто-то рядом",
                ],
                "avoid": [
                    "Истории и метафоры",
                    "Советы",
                    "Минимизация чувств",
                    "Паника",
                ],
                "hotline": settings.CRISIS_HOTLINE,
            },
            self.LEVEL_HIGH: {
                "approach": "supportive_direct",
                "tone": "warm, concerned, non-judgmental",
                "actions": [
                    "Признать серьёзность ситуации",
                    "Выразить заботу",
                    "Мягко предложить профессиональную помощь",
                    "Предоставить ресурсы",
                ],
                "avoid": [
                    "Давление обращаться за помощью",
                    "Осуждение",
                    "Паника",
                ],
                "hotline": settings.CRISIS_HOTLINE,
            },
            self.LEVEL_MEDIUM: {
                "approach": "supportive",
                "tone": "warm, understanding",
                "actions": [
                    "Выслушать без осуждения",
                    "Нормализовать чувства",
                    "Помочь разобраться в ситуации",
                    "При необходимости упомянуть профессиональную помощь",
                ],
                "avoid": [
                    "Банальные советы",
                    "Обесценивание",
                ],
            },
            self.LEVEL_LOW: {
                "approach": "attentive",
                "tone": "warm, supportive",
                "actions": [
                    "Быть внимательным",
                    "Проявлять эмпатию",
                    "Отслеживать изменения",
                ],
                "avoid": [
                    "Игнорирование сигналов",
                ],
            },
        }
        
        return guides.get(level, guides[self.LEVEL_LOW])
