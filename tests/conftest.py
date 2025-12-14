"""
Pytest fixtures and configuration.
"""

import pytest
from unittest.mock import Mock, AsyncMock


@pytest.fixture
def mock_bot():
    """Mock Telegram Bot instance."""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    bot.send_chat_action = AsyncMock()
    return bot


@pytest.fixture
def mock_update():
    """Mock Telegram Update."""
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_user.first_name = "Test"
    update.message = Mock()
    update.message.text = "Test message"
    update.message.reply_text = AsyncMock()
    update.effective_chat = Mock()
    update.effective_chat.id = 12345
    return update


@pytest.fixture
def mock_context():
    """Mock Telegram Context."""
    context = Mock()
    context.bot = AsyncMock()
    context.user_data = {}
    return context


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "persona": "mira",
        "display_name": "Тестовая",
        "partner_name": "Тест",
        "partner_gender": "male",
        "children_info": None,
        "marriage_years": None,
        "communication_style": "balanced",
    }
