"""
Event Tracker utility for tracking user milestones and first-time events.
Использует флаги в базе данных для отслеживания первых событий.
"""

from typing import Optional
from database.repositories.user import UserRepository
from database.repositories.conversation import ConversationRepository
from database.models import User
from utils.system_logger import system_logger


class EventTracker:
    """Трекер событий пользователей."""

    def __init__(self):
        self.user_repo = UserRepository()
        self.conversation_repo = ConversationRepository()

    async def track_first_voice_message(
        self,
        user: User,
        duration: Optional[int] = None,
    ) -> bool:
        """
        Трекает первое голосовое сообщение пользователя.

        Returns:
            True если это было первое голосовое сообщение
        """
        # Проверяем, было ли уже голосовое сообщение
        conversations = await self.conversation_repo.get_by_user(
            user.id,
            limit=1000
        )

        # Ищем предыдущие голосовые сообщения (role=user, message_type=voice)
        voice_messages = [
            c for c in conversations
            if c.role == "user" and c.message_type == "voice"
        ]

        # Если это первое голосовое сообщение
        if len(voice_messages) == 1:  # Текущее только что добавлено
            try:
                await system_logger.log_first_voice_message(
                    user_id=user.id,
                    telegram_id=user.telegram_id,
                    username=user.username,
                    duration=duration,
                )
                return True
            except Exception as e:
                print(f"Failed to log first voice message: {e}")

        return False

    async def track_first_photo_message(self, user: User) -> bool:
        """
        Трекает первое сообщение с фото/изображением.

        Returns:
            True если это было первое фото
        """
        # Проверяем, было ли уже фото
        conversations = await self.conversation_repo.get_by_user(
            user.id,
            limit=1000
        )

        # Ищем предыдущие сообщения с фото (role=user, message_type=photo)
        photo_messages = [
            c for c in conversations
            if c.role == "user" and c.message_type == "photo"
        ]

        # Если это первое фото
        if len(photo_messages) == 1:  # Текущее только что добавлено
            try:
                await system_logger.log_first_photo_message(
                    user_id=user.id,
                    telegram_id=user.telegram_id,
                    username=user.username,
                )
                return True
            except Exception as e:
                print(f"Failed to log first photo message: {e}")

        return False

    async def track_message_milestone(self, user: User) -> Optional[int]:
        """
        Трекает вехи по количеству сообщений (50, 100, 300, 1000).

        Returns:
            Номер вехи, если достигнута, иначе None
        """
        # Получаем общее количество сообщений пользователя
        conversations = await self.conversation_repo.get_by_user(
            user.id,
            limit=2000  # Достаточно для проверки до 1000
        )

        # Считаем только сообщения пользователя
        user_messages = [c for c in conversations if c.role == "user"]
        total_messages = len(user_messages)

        # Вехи
        milestones = [50, 100, 300, 1000]

        for milestone in milestones:
            if total_messages == milestone:
                try:
                    await system_logger.log_message_milestone(
                        user_id=user.id,
                        telegram_id=user.telegram_id,
                        username=user.username,
                        milestone=milestone,
                        total_messages=total_messages,
                    )
                    return milestone
                except Exception as e:
                    print(f"Failed to log message milestone {milestone}: {e}")

        return None


# Глобальный экземпляр
event_tracker = EventTracker()
