"""
Tests for ai.mood_analyzer module.
"""

import pytest
from ai.mood_analyzer import MoodAnalyzer, MoodAnalysis


@pytest.fixture
def analyzer():
    """Create MoodAnalyzer instance."""
    return MoodAnalyzer()


class TestMoodAnalyzer:
    """Tests for MoodAnalyzer class."""

    def test_analyze_happy_message(self, analyzer):
        """Should detect happy mood."""
        text = "Я так счастлива! Всё замечательно!"
        result = analyzer.analyze(text)

        assert isinstance(result, MoodAnalysis)
        assert result.mood_score > 0.5
        assert result.primary_emotion in ["happy", "joy", "excited"]
        assert result.confidence > 0.0

    def test_analyze_sad_message(self, analyzer):
        """Should detect sad mood."""
        text = "Мне так грустно... Ничего не получается"
        result = analyzer.analyze(text)

        assert result.mood_score < 0.5
        assert result.primary_emotion in ["sad", "disappointed", "hopeless"]
        assert result.anxiety_level >= 0.0

    def test_analyze_angry_message(self, analyzer):
        """Should detect angry mood."""
        text = "Я так злюсь! Всё бесит!"
        result = analyzer.analyze(text)

        assert result.primary_emotion in ["angry", "frustrated", "irritated"]
        assert result.energy_level > 0.5

    def test_analyze_anxious_message(self, analyzer):
        """Should detect anxiety."""
        text = "Я так переживаю... Боюсь что всё пойдёт не так"
        result = analyzer.analyze(text)

        assert result.anxiety_level > 0.5
        assert result.primary_emotion in ["anxious", "worried", "stressed"]

    def test_analyze_neutral_message(self, analyzer):
        """Should detect neutral mood."""
        text = "Сегодня был обычный день"
        result = analyzer.analyze(text)

        assert 0.3 < result.mood_score < 0.7
        assert result.primary_emotion in ["neutral", "calm"]

    def test_analyze_low_energy(self, analyzer):
        """Should detect low energy."""
        text = "Я так устала... Нет сил ни на что"
        result = analyzer.analyze(text)

        assert result.energy_level < 0.5
        assert result.primary_emotion in ["tired", "exhausted", "sad"]

    def test_analyze_high_energy(self, analyzer):
        """Should detect high energy."""
        text = "У меня столько энергии! Хочу всё успеть!"
        result = analyzer.analyze(text)

        assert result.energy_level > 0.5
        assert result.primary_emotion in ["excited", "energetic", "happy"]

    def test_detect_triggers(self, analyzer):
        """Should detect emotional triggers."""
        text = "Муж опять не помогает с детьми, работа задолбала"
        result = analyzer.analyze(text)

        assert len(result.triggers) > 0
        assert any("партнёр" in t or "муж" in t or "работа" in t for t in result.triggers)

    def test_detect_secondary_emotions(self, analyzer):
        """Should detect secondary emotions."""
        text = "Я рада что всё получилось, но немного переживаю о будущем"
        result = analyzer.analyze(text)

        assert len(result.secondary_emotions) > 0
        # Should have both happy and anxious
        emotions = [result.primary_emotion] + result.secondary_emotions
        assert any(e in ["happy", "joy"] for e in emotions)
        assert any(e in ["anxious", "worried"] for e in emotions)

    def test_empty_message(self, analyzer):
        """Should handle empty message."""
        result = analyzer.analyze("")

        assert result.primary_emotion == "neutral"
        assert result.confidence == 0.0
        assert result.mood_score == 0.5

    def test_short_message(self, analyzer):
        """Should handle short message."""
        result = analyzer.analyze("Ок")

        assert result.primary_emotion == "neutral"
        assert result.confidence < 0.5

    def test_confidence_scoring(self, analyzer):
        """Should have higher confidence for emotional messages."""
        neutral_text = "Сегодня был день"
        emotional_text = "Я так счастлива! Это лучший день в моей жизни!"

        neutral_result = analyzer.analyze(neutral_text)
        emotional_result = analyzer.analyze(emotional_text)

        assert emotional_result.confidence > neutral_result.confidence

    def test_mood_score_range(self, analyzer):
        """Mood score should be between 0 and 1."""
        texts = [
            "Всё ужасно",
            "Нормально",
            "Отлично!",
        ]

        for text in texts:
            result = analyzer.analyze(text)
            assert 0.0 <= result.mood_score <= 1.0

    def test_anxiety_level_range(self, analyzer):
        """Anxiety level should be between 0 and 1."""
        result = analyzer.analyze("Я очень переживаю")
        assert 0.0 <= result.anxiety_level <= 1.0

    def test_energy_level_range(self, analyzer):
        """Energy level should be between 0 and 1."""
        result = analyzer.analyze("Я полна энергии!")
        assert 0.0 <= result.energy_level <= 1.0
