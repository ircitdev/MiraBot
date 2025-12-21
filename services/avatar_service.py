"""
Avatar Service.
Сервис для загрузки и хранения аватарок пользователей.
"""

from typing import Optional
from loguru import logger
from telegram import Bot

from config.settings import settings
from services.storage.gcs_client import gcs_client


class AvatarService:
    """
    Сервис для работы с аватарками пользователей.

    Загружает фото профиля из Telegram и сохраняет в GCS.
    """

    async def fetch_and_save_avatar(
        self,
        bot: Bot,
        telegram_id: int,
        user_id: int,
    ) -> Optional[str]:
        """
        Загружает аватарку пользователя из Telegram и сохраняет в GCS.

        Args:
            bot: Telegram Bot instance
            telegram_id: Telegram ID пользователя
            user_id: Internal user ID

        Returns:
            URL аватарки в GCS или None
        """
        if not settings.USE_GCS:
            logger.debug("GCS disabled, skipping avatar fetch")
            return None

        try:
            # Получаем фото профиля
            photos = await bot.get_user_profile_photos(telegram_id, limit=1)

            if not photos or not photos.photos:
                logger.debug(f"No profile photo for user {telegram_id}")
                return None

            # Берём самое маленькое фото (первое в списке размеров)
            # photos.photos[0] - массив размеров одного фото
            # Берём средний размер для баланса качество/размер
            photo_sizes = photos.photos[0]

            # Выбираем подходящий размер (около 160px)
            photo = None
            for size in photo_sizes:
                if size.width >= 160:
                    photo = size
                    break

            if not photo:
                photo = photo_sizes[-1]  # Берём самый большой если нет подходящего

            # Скачиваем файл
            file = await bot.get_file(photo.file_id)
            photo_bytes = await file.download_as_bytearray()

            # Загружаем в GCS
            gcs_path = await gcs_client.upload_file(
                data=bytes(photo_bytes),
                user_id=user_id,
                telegram_id=telegram_id,
                file_type="avatars",
                file_extension="jpg",
                content_type="image/jpeg",
                metadata={
                    "type": "avatar",
                    "telegram_id": str(telegram_id),
                },
            )

            if not gcs_path:
                logger.warning(f"Failed to upload avatar to GCS for user {telegram_id}")
                return None

            # Генерируем публичный URL
            # Для аватарок используем публичный URL (без подписи)
            avatar_url = gcs_client.get_public_url(gcs_path)

            logger.info(f"Saved avatar for user {telegram_id}: {gcs_path}")
            return avatar_url

        except Exception as e:
            logger.warning(f"Failed to fetch avatar for user {telegram_id}: {e}")
            return None

    async def update_avatar_if_needed(
        self,
        bot: Bot,
        telegram_id: int,
        user_id: int,
        current_avatar_url: Optional[str],
    ) -> Optional[str]:
        """
        Обновляет аватарку если её нет или она устарела.

        Args:
            bot: Telegram Bot instance
            telegram_id: Telegram ID пользователя
            user_id: Internal user ID
            current_avatar_url: Текущий URL аватарки

        Returns:
            Новый URL или текущий если не обновлялся
        """
        # Если аватарки нет — загружаем
        if not current_avatar_url:
            return await self.fetch_and_save_avatar(bot, telegram_id, user_id)

        # Если есть — возвращаем текущую
        # TODO: можно добавить проверку на свежесть по времени
        return current_avatar_url


# Глобальный экземпляр
avatar_service = AvatarService()
