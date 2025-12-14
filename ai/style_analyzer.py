"""
Style Analyzer.
Анализирует стиль общения пользователя для персонализации ответов.
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
from loguru import logger


@dataclass
class StyleAnalysis:
    """Результат анализа стиля."""
    formality: str  # informal, neutral, formal
    emoji_preference: str  # none, few, many
    message_length: str  # short, medium, long
    response_depth: str  # surface, medium, deep
    humor_level: str  # none, light, frequent
    support_style: str  # gentle, direct, tough
    topics_avoided: List[str]
    triggers: List[str]


class StyleAnalyzer:
    """Анализатор стиля общения пользователя."""

    # Паттерны для определения формальности
    FORMAL_MARKERS = [
        r'\bВы\b', r'\bвас\b', r'\bвам\b', r'\bвашей?\b',
        r'\bпожалуйста\b', r'\bбудьте добры\b', r'\bизвините\b',
        r'\bблагодарю\b', r'\bс уважением\b',
    ]

    INFORMAL_MARKERS = [
        r'\bты\b', r'\bтебя\b', r'\bтебе\b', r'\bтвой\b',
        r'\bблин\b', r'\bчё\b', r'\bчо\b', r'\bнифига\b',
        r'\bваще\b', r'\bкороче\b', r'\bтипа\b', r'\bлол\b',
        r'\bржу\b', r'\bхах+\b', r'\bахах+\b',
    ]

    # Эмодзи паттерн
    EMOJI_PATTERN = re.compile(
        r'[\U0001F600-\U0001F64F'  # emoticons
        r'\U0001F300-\U0001F5FF'  # symbols & pictographs
        r'\U0001F680-\U0001F6FF'  # transport & map
        r'\U0001F1E0-\U0001F1FF'  # flags
        r'\U00002702-\U000027B0'
        r'\U000024C2-\U0001F251'
        r']+',
        flags=re.UNICODE
    )

    # Маркеры глубины
    DEEP_MARKERS = [
        r'\bпочему\b', r'\bзачем\b', r'\bкак думаешь\b',
        r'\bчто чувствую\b', r'\bчувствую себя\b',
        r'\bна самом деле\b', r'\bв глубине\b',
        r'\bпонимаю\b', r'\bосознаю\b', r'\bзадумалась\b',
    ]

    # Маркеры юмора
    HUMOR_MARKERS = [
        r'\bхах+\b', r'\bахах+\b', r'\bлол\b', r'\bржу\b',
        r'\bсмешно\b', r'\bшучу\b', r'\bприкол\b',
        r'😂', r'🤣', r'😆', r'😄', r'😁',
    ]

    # Чувствительные темы (триггеры)
    TRIGGER_PATTERNS = {
        'насилие': [r'\bударил\b', r'\bбьёт\b', r'\bнасилие\b', r'\bизбивает\b'],
        'суицид': [r'\bне хочу жить\b', r'\bпокончить\b', r'\bсуицид\b', r'\bубить себя\b'],
        'измена': [r'\bизменил\b', r'\bизменяет\b', r'\bлюбовница\b', r'\bизмена\b'],
        'развод': [r'\bразвод\b', r'\bразводиться\b', r'\bуйти от него\b'],
        'деньги': [r'\bденег нет\b', r'\bдолги\b', r'\bкредит\b', r'\bбезденежье\b'],
        'здоровье': [r'\bболезнь\b', r'\bдиагноз\b', r'\bонколог\b', r'\bумираю\b'],
    }

    def analyze_messages(
        self,
        messages: List[Dict[str, Any]],
        existing_style: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Анализирует сообщения пользователя и выводит его стиль.

        Args:
            messages: Список сообщений пользователя (role='user')
            existing_style: Существующий стиль для инкрементального обновления

        Returns:
            Словарь с характеристиками стиля
        """
        if not messages:
            return existing_style or self._default_style()

        # Фильтруем только сообщения пользователя
        user_messages = [
            m['content'] for m in messages
            if m.get('role') == 'user' and m.get('content')
        ]

        if not user_messages:
            return existing_style or self._default_style()

        # Анализируем характеристики
        formality = self._analyze_formality(user_messages)
        emoji_pref = self._analyze_emoji_preference(user_messages)
        msg_length = self._analyze_message_length(user_messages)
        depth = self._analyze_response_depth(user_messages)
        humor = self._analyze_humor(user_messages)
        triggers = self._detect_triggers(user_messages)

        # Определяем предпочитаемый стиль поддержки
        support_style = self._infer_support_style(
            formality, depth, humor, existing_style
        )

        style = {
            'formality': formality,
            'emoji_preference': emoji_pref,
            'message_length': msg_length,
            'response_depth': depth,
            'humor_level': humor,
            'support_style': support_style,
            'topics_avoided': existing_style.get('topics_avoided', []) if existing_style else [],
            'triggers': triggers,
            'updated_at': datetime.now().isoformat(),
        }

        logger.debug(f"Style analysis result: {style}")
        return style

    def _default_style(self) -> Dict[str, Any]:
        """Возвращает стиль по умолчанию."""
        return {
            'formality': 'neutral',
            'emoji_preference': 'few',
            'message_length': 'medium',
            'response_depth': 'medium',
            'humor_level': 'light',
            'support_style': 'gentle',
            'topics_avoided': [],
            'triggers': [],
            'updated_at': datetime.now().isoformat(),
        }

    def _analyze_formality(self, messages: List[str]) -> str:
        """Определяет уровень формальности."""
        total_text = ' '.join(messages).lower()

        formal_count = sum(
            len(re.findall(pattern, total_text, re.IGNORECASE))
            for pattern in self.FORMAL_MARKERS
        )

        informal_count = sum(
            len(re.findall(pattern, total_text, re.IGNORECASE))
            for pattern in self.INFORMAL_MARKERS
        )

        if formal_count > informal_count * 2:
            return 'formal'
        elif informal_count > formal_count * 2:
            return 'informal'
        return 'neutral'

    def _analyze_emoji_preference(self, messages: List[str]) -> str:
        """Определяет предпочтение эмодзи."""
        total_text = ' '.join(messages)
        emoji_count = len(self.EMOJI_PATTERN.findall(total_text))
        msg_count = len(messages)

        if msg_count == 0:
            return 'few'

        avg_emoji = emoji_count / msg_count

        if avg_emoji < 0.3:
            return 'none'
        elif avg_emoji < 1.5:
            return 'few'
        return 'many'

    def _analyze_message_length(self, messages: List[str]) -> str:
        """Определяет предпочтительную длину сообщений."""
        if not messages:
            return 'medium'

        avg_length = sum(len(m) for m in messages) / len(messages)

        if avg_length < 50:
            return 'short'
        elif avg_length < 200:
            return 'medium'
        return 'long'

    def _analyze_response_depth(self, messages: List[str]) -> str:
        """Определяет глубину проработки тем."""
        total_text = ' '.join(messages).lower()

        deep_count = sum(
            len(re.findall(pattern, total_text, re.IGNORECASE))
            for pattern in self.DEEP_MARKERS
        )

        # Также учитываем длину сообщений
        avg_length = sum(len(m) for m in messages) / len(messages) if messages else 0

        if deep_count >= 3 or avg_length > 300:
            return 'deep'
        elif deep_count >= 1 or avg_length > 100:
            return 'medium'
        return 'surface'

    def _analyze_humor(self, messages: List[str]) -> str:
        """Определяет уровень юмора."""
        total_text = ' '.join(messages)

        humor_count = sum(
            len(re.findall(pattern, total_text, re.IGNORECASE))
            for pattern in self.HUMOR_MARKERS
        )

        if humor_count >= 5:
            return 'frequent'
        elif humor_count >= 1:
            return 'light'
        return 'none'

    def _detect_triggers(self, messages: List[str]) -> List[str]:
        """Определяет чувствительные темы пользователя."""
        total_text = ' '.join(messages).lower()
        detected = []

        for trigger_name, patterns in self.TRIGGER_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, total_text, re.IGNORECASE):
                    if trigger_name not in detected:
                        detected.append(trigger_name)
                    break

        return detected

    def _infer_support_style(
        self,
        formality: str,
        depth: str,
        humor: str,
        existing_style: Optional[Dict[str, Any]],
    ) -> str:
        """Выводит предпочитаемый стиль поддержки."""
        # Если уже есть явно заданный стиль, сохраняем его
        if existing_style and existing_style.get('support_style_explicit'):
            return existing_style['support_style']

        # Эвристика: формальные + глубокие = прямая поддержка
        if formality == 'formal' and depth == 'deep':
            return 'direct'

        # Много юмора = можно быть пожёстче
        if humor == 'frequent':
            return 'direct'

        # По умолчанию — мягкая поддержка
        return 'gentle'


# Глобальный экземпляр
style_analyzer = StyleAnalyzer()
