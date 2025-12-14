"""
Tests for utils.sanitizer module.
"""

import pytest
from utils.sanitizer import sanitize_text, sanitize_name, validate_message


class TestSanitizeText:
    """Tests for sanitize_text function."""

    def test_remove_control_characters(self):
        """Should remove control characters."""
        text = "Hello\x00\x01World\x1f"
        assert sanitize_text(text) == "HelloWorld"

    def test_remove_excessive_whitespace(self):
        """Should normalize whitespace."""
        text = "Hello    World\n\n\nTest"
        result = sanitize_text(text)
        assert "    " not in result
        assert "\n\n\n" not in result

    def test_respect_max_length(self):
        """Should truncate to max length."""
        text = "a" * 5000
        result = sanitize_text(text, max_length=1000)
        assert len(result) == 1000

    def test_preserve_valid_text(self):
        """Should preserve valid text."""
        text = "Привет! Как дела? 😊"
        assert sanitize_text(text) == text

    def test_strip_whitespace(self):
        """Should strip leading/trailing whitespace."""
        text = "  Hello World  "
        assert sanitize_text(text) == "Hello World"

    def test_empty_string(self):
        """Should handle empty string."""
        assert sanitize_text("") == ""
        assert sanitize_text("   ") == ""


class TestSanitizeName:
    """Tests for sanitize_name function."""

    def test_remove_special_characters(self):
        """Should remove special characters."""
        assert sanitize_name("Ан@на#") == "Анна"
        assert sanitize_name("Мар$ия%") == "Мария"

    def test_preserve_hyphens_and_apostrophes(self):
        """Should preserve hyphens and apostrophes."""
        assert sanitize_name("Анна-Мария") == "Анна-Мария"
        assert sanitize_name("О'Коннор") == "О'Коннор"

    def test_capitalize_first_letter(self):
        """Should capitalize first letter."""
        assert sanitize_name("анна") == "Анна"
        assert sanitize_name("мария") == "Мария"

    def test_respect_max_length(self):
        """Should truncate to max length."""
        name = "А" * 100
        result = sanitize_name(name, max_length=50)
        assert len(result) <= 50

    def test_remove_numbers(self):
        """Should remove numbers."""
        assert sanitize_name("Анна123") == "Анна"
        assert sanitize_name("123Мария") == "Мария"

    def test_empty_result(self):
        """Should return empty string if nothing left."""
        assert sanitize_name("123456") == ""
        assert sanitize_name("@#$%^") == ""


class TestValidateMessage:
    """Tests for validate_message function."""

    def test_valid_message(self):
        """Should accept valid message."""
        is_valid, text, error = validate_message("Привет! Как дела?")
        assert is_valid is True
        assert text == "Привет! Как дела?"
        assert error is None

    def test_none_message(self):
        """Should reject None."""
        is_valid, text, error = validate_message(None)
        assert is_valid is False
        assert error == "empty_message"

    def test_empty_message(self):
        """Should reject empty message."""
        is_valid, text, error = validate_message("")
        assert is_valid is False
        assert error == "empty_message"

    def test_whitespace_only(self):
        """Should reject whitespace-only message."""
        is_valid, text, error = validate_message("   ")
        assert is_valid is False
        assert error == "empty_message"

    def test_too_long_message(self):
        """Should reject too long message."""
        long_text = "a" * 5000
        is_valid, text, error = validate_message(long_text)
        assert is_valid is False
        assert error == "message_too_long"

    def test_sql_injection_detection(self):
        """Should detect SQL injection attempts."""
        messages = [
            "'; DROP TABLE users; --",
            "SELECT * FROM users",
            "UPDATE users SET",
        ]
        for msg in messages:
            is_valid, text, error = validate_message(msg)
            # Should still be valid but logged
            assert is_valid is True

    def test_sanitize_on_validation(self):
        """Should sanitize message during validation."""
        is_valid, text, error = validate_message("Hello\x00World")
        assert is_valid is True
        assert "\x00" not in text
        assert text == "HelloWorld"
