"""
Tests for utils.text_parser module.
"""

import pytest
from utils.text_parser import extract_name_from_text


class TestExtractNameFromText:
    """Tests for extract_name_from_text function."""

    def test_extract_simple_name(self):
        """Should extract simple name."""
        assert extract_name_from_text("Меня зовут Анна") == "Анна"
        assert extract_name_from_text("Я Мария") == "Мария"
        assert extract_name_from_text("зовут Катя") == "Катя"

    def test_extract_name_with_prefix(self):
        """Should extract name with 'Называй меня' prefix."""
        assert extract_name_from_text("Называй меня Ниночка") == "Ниночка"
        assert extract_name_from_text("называй Лена") == "Лена"

    def test_extract_capitalized_name(self):
        """Should extract capitalized name from middle of sentence."""
        assert extract_name_from_text("Привет, меня зовут Оля, рада знакомству") == "Оля"
        assert extract_name_from_text("Можешь называть меня Настя") == "Настя"

    def test_reject_questions(self):
        """Should reject questions as names."""
        assert extract_name_from_text("Забыла?") is None
        assert extract_name_from_text("Серьёзно?") is None
        assert extract_name_from_text("Правда?") is None

    def test_reject_lowercase_words(self):
        """Should reject lowercase words."""
        assert extract_name_from_text("меня зовут") is None
        assert extract_name_from_text("привет как дела") is None

    def test_reject_common_words(self):
        """Should reject common Russian words."""
        assert extract_name_from_text("Хорошо") is None
        assert extract_name_from_text("Спасибо") is None
        assert extract_name_from_text("Привет") is None

    def test_reject_short_words(self):
        """Should reject words shorter than 2 characters."""
        assert extract_name_from_text("Я А") is None
        assert extract_name_from_text("К") is None

    def test_reject_long_phrases(self):
        """Should reject phrases longer than 20 characters."""
        assert extract_name_from_text("Очень длинное имя которое не должно пройти") is None

    def test_extract_from_complex_sentence(self):
        """Should extract name from complex sentence."""
        assert extract_name_from_text("Привет! Меня зовут Светлана, очень приятно") == "Светлана"
        assert extract_name_from_text("Я Виктория, хочу поговорить") == "Виктория"

    def test_empty_input(self):
        """Should handle empty input."""
        assert extract_name_from_text("") is None
        assert extract_name_from_text("   ") is None

    def test_special_characters(self):
        """Should handle special characters."""
        assert extract_name_from_text("Меня зовут Анна-Мария") == "Анна-Мария"
        assert extract_name_from_text("Я О'Коннор") == "О'Коннор"
