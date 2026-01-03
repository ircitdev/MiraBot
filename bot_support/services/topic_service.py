"""
Topic Service.
Сервис для управления топиками в супергруппе.
"""

from typing import Optional
from telegram import Bot
from telegram.error import TelegramError
from loguru import logger

from database.models import SupportUser
from bot_support.utils.formatters import format_user_card
from config.settings import settings


class TopicService:
    """Сервис для работы с топиками форума в супергруппе."""

    async def create_topic_for_user(
        self,
        bot: Bot,
        user: SupportUser,
    ) -> Optional[int]:
        """
        Создаёт новый топик в супергруппе для пользователя.

        Args:
            bot: Экземпляр Telegram Bot
            user: Объект SupportUser

        Returns:
            int: ID созданного топика или None в случае ошибки
        """
        try:
            # Формируем название топика
            topic_name = user.first_name
            if user.last_name:
                topic_name += f" {user.last_name}"

            # Ограничиваем длину названия (максимум 128 символов для Telegram)
            if len(topic_name) > 128:
                topic_name = topic_name[:125] + "..."

            logger.info(
                f"Creating forum topic for user {user.telegram_id}: {topic_name}"
            )

            # Создаём топик в супергруппе
            # Примечание: для этого нужны права администратора с разрешением manage_topics
            forum_topic = await bot.create_forum_topic(
                chat_id=settings.SUPPORT_GROUP_ID,
                name=topic_name,
            )

            topic_id = forum_topic.message_thread_id

            logger.info(
                f"Successfully created topic {topic_id} for user {user.telegram_id}"
            )

            return topic_id

        except TelegramError as e:
            logger.error(
                f"Failed to create topic for user {user.telegram_id}: {e}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error creating topic for user {user.telegram_id}: {e}"
            )
            return None

    async def send_user_card(
        self,
        bot: Bot,
        group_id: int,
        topic_id: int,
        user: SupportUser,
    ) -> bool:
        """
        Отправляет карточку пользователя в топик поддержки.

        Args:
            bot: Экземпляр Telegram Bot
            group_id: ID супергруппы
            topic_id: ID топика
            user: Объект SupportUser

        Returns:
            bool: True если успешно, False в случае ошибки
        """
        try:
            # Форматируем карточку
            card_text = format_user_card(user)

            logger.info(
                f"Sending user card to topic {topic_id} for user {user.telegram_id}"
            )

            # Отправляем карточку в топик
            await bot.send_message(
                chat_id=group_id,
                text=card_text,
                message_thread_id=topic_id,
            )

            logger.info(
                f"Successfully sent user card to topic {topic_id}"
            )

            return True

        except TelegramError as e:
            logger.error(
                f"Failed to send user card to topic {topic_id}: {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error sending user card to topic {topic_id}: {e}"
            )
            return False

    async def edit_topic_name(
        self,
        bot: Bot,
        group_id: int,
        topic_id: int,
        new_name: str,
    ) -> bool:
        """
        Изменяет название топика.

        Args:
            bot: Экземпляр Telegram Bot
            group_id: ID супергруппы
            topic_id: ID топика
            new_name: Новое название

        Returns:
            bool: True если успешно, False в случае ошибки
        """
        try:
            # Ограничиваем длину
            if len(new_name) > 128:
                new_name = new_name[:125] + "..."

            await bot.edit_forum_topic(
                chat_id=group_id,
                message_thread_id=topic_id,
                name=new_name,
            )

            logger.info(f"Successfully renamed topic {topic_id} to '{new_name}'")
            return True

        except TelegramError as e:
            logger.error(f"Failed to rename topic {topic_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error renaming topic {topic_id}: {e}")
            return False
