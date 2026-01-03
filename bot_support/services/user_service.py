"""
User Service.
Сервис для работы с пользователями бота поддержки.
"""

from typing import Optional
from telegram import User as TelegramUser, Bot
from loguru import logger

from database.models import SupportUser
from database.repositories.support_user import SupportUserRepository
from bot_support.services.topic_service import TopicService
from config.settings import settings


class UserService:
    """Сервис для управления пользователями поддержки."""

    def __init__(self):
        self.user_repo = SupportUserRepository()
        self.topic_service = TopicService()

    async def get_or_create_user(
        self,
        bot: Bot,
        telegram_user: TelegramUser,
    ) -> Optional[SupportUser]:
        """
        Получает существующего или создаёт нового пользователя поддержки.

        Args:
            bot: Экземпляр Telegram Bot
            telegram_user: Объект User из Telegram

        Returns:
            SupportUser: Объект пользователя или None в случае ошибки
        """
        try:
            # Проверяем, существует ли пользователь
            existing_user = await self.user_repo.get_by_telegram_id(telegram_user.id)

            if existing_user:
                logger.info(
                    f"User {telegram_user.id} already exists with topic {existing_user.topic_id}"
                )
                return existing_user

            # Создаём нового пользователя
            logger.info(f"Creating new support user for telegram_id={telegram_user.id}")

            # Сначала создаём временный объект для создания топика
            temp_user = SupportUser(
                telegram_id=telegram_user.id,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                username=telegram_user.username,
                photo_url=None,  # Заполним позже
                topic_id=0,  # Заполним после создания топика
            )

            # Создаём топик в супергруппе
            topic_id = await self.topic_service.create_topic_for_user(
                bot=bot,
                user=temp_user,
            )

            if not topic_id:
                logger.error(
                    f"Failed to create topic for user {telegram_user.id}, cannot create user"
                )
                return None

            # Получаем фото профиля
            photo_url = await self._get_user_photo(bot, telegram_user.id)

            # Создаём пользователя в БД
            new_user = await self.user_repo.create(
                telegram_id=telegram_user.id,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
                username=telegram_user.username,
                photo_url=photo_url,
                topic_id=topic_id,
            )

            # Отправляем карточку пользователя в топик
            await self.topic_service.send_user_card(
                bot=bot,
                group_id=settings.SUPPORT_GROUP_ID,
                topic_id=topic_id,
                user=new_user,
            )

            logger.info(
                f"Successfully created user {new_user.id} "
                f"(telegram_id={telegram_user.id}) with topic {topic_id}"
            )

            return new_user

        except Exception as e:
            logger.error(f"Error in get_or_create_user: {e}", exc_info=True)
            return None

    async def _get_user_photo(self, bot: Bot, user_id: int) -> Optional[str]:
        """
        Получает фото профиля пользователя.

        Args:
            bot: Экземпляр Telegram Bot
            user_id: Telegram ID пользователя

        Returns:
            str: file_id фотографии или None
        """
        try:
            photos = await bot.get_user_profile_photos(user_id, limit=1)

            if photos.total_count > 0 and photos.photos:
                # Берём самое большое фото (последнее в списке)
                photo = photos.photos[0][-1]
                return photo.file_id

            return None

        except Exception as e:
            logger.warning(f"Failed to get user photo for {user_id}: {e}")
            return None

    async def update_user_photo(
        self,
        bot: Bot,
        user_id: int,
        telegram_id: int,
    ) -> bool:
        """
        Обновляет фото пользователя.

        Args:
            bot: Экземпляр Telegram Bot
            user_id: ID пользователя в БД
            telegram_id: Telegram ID пользователя

        Returns:
            bool: True если успешно
        """
        try:
            photo_url = await self._get_user_photo(bot, telegram_id)

            if photo_url:
                await self.user_repo.update_photo(user_id, photo_url)
                logger.info(f"Updated photo for user {user_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error updating user photo: {e}")
            return False
