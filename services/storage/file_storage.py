"""
File Storage Service.
Высокоуровневый сервис для сохранения файлов пользователей.
Интегрируется с GCS и БД для хранения метаданных.
"""

from typing import Optional
from datetime import datetime, timedelta
from loguru import logger

from config.settings import settings
from services.storage.gcs_client import gcs_client
from database.repositories.user_file import UserFileRepository
from database.repositories.subscription import SubscriptionRepository


class FileStorageService:
    """
    Сервис хранения файлов пользователей.

    Возможности:
    - Сохранение фото, голосовых, документов
    - Хранение метаданных в БД
    - Очистка старых файлов (3 мес для free, 12 мес для premium)
    """

    def __init__(self):
        self.file_repo = UserFileRepository()
        self.subscription_repo = SubscriptionRepository()

    def _get_retention_days(self, is_premium: bool) -> int:
        """Получить срок хранения из настроек."""
        if is_premium:
            return settings.GCS_RETENTION_PREMIUM_DAYS
        return settings.GCS_RETENTION_FREE_DAYS

    async def _is_user_premium(self, user_id: int) -> bool:
        """Проверить премиум статус пользователя."""
        subscription = await self.subscription_repo.get_active(user_id)
        return subscription and subscription.plan in ("premium", "trial")

    async def save_photo(
        self,
        photo_bytes: bytes,
        user_id: int,
        telegram_id: int,
        telegram_file_id: str,
        file_size: int,
        message_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Сохраняет фото пользователя.

        Returns:
            ID записи в БД или None если ошибка
        """
        if not settings.USE_GCS:
            logger.debug("GCS disabled, skipping photo save")
            return None

        try:
            # Загружаем в GCS
            gcs_path = await gcs_client.upload_file(
                data=photo_bytes,
                user_id=user_id,
                telegram_id=telegram_id,
                file_type="photos",
                file_extension="jpg",
                content_type="image/jpeg",
                metadata={
                    "telegram_file_id": telegram_file_id,
                },
            )

            if not gcs_path:
                logger.warning(f"GCS upload failed for photo, user={user_id}")
                return None

            # Определяем срок хранения
            is_premium = await self._is_user_premium(user_id)
            retention_days = self._get_retention_days(is_premium)
            expires_at = datetime.now() + timedelta(days=retention_days)

            # Сохраняем в БД
            file_record = await self.file_repo.create(
                user_id=user_id,
                telegram_id=telegram_id,
                file_type="photo",
                telegram_file_id=telegram_file_id,
                gcs_path=gcs_path,
                expires_at=expires_at,
                file_size=file_size,
                mime_type="image/jpeg",
                message_id=message_id,
                is_premium=is_premium,
            )

            logger.info(
                f"Saved photo for user {telegram_id}: "
                f"gcs_path={gcs_path}, db_id={file_record.id}, "
                f"expires={expires_at.date()}"
            )

            return file_record.id

        except Exception as e:
            logger.error(f"Failed to save photo for user {user_id}: {e}")
            return None

    async def save_voice(
        self,
        voice_bytes: bytes,
        user_id: int,
        telegram_id: int,
        telegram_file_id: str,
        file_size: int,
        duration: int,
        message_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Сохраняет голосовое сообщение.

        Returns:
            ID записи в БД или None если ошибка
        """
        if not settings.USE_GCS:
            logger.debug("GCS disabled, skipping voice save")
            return None

        try:
            # Загружаем в GCS
            gcs_path = await gcs_client.upload_file(
                data=voice_bytes,
                user_id=user_id,
                telegram_id=telegram_id,
                file_type="voice",
                file_extension="ogg",
                content_type="audio/ogg",
                metadata={
                    "telegram_file_id": telegram_file_id,
                    "duration": str(duration),
                },
            )

            if not gcs_path:
                logger.warning(f"GCS upload failed for voice, user={user_id}")
                return None

            # Определяем срок хранения
            is_premium = await self._is_user_premium(user_id)
            retention_days = self._get_retention_days(is_premium)
            expires_at = datetime.now() + timedelta(days=retention_days)

            # Сохраняем в БД
            file_record = await self.file_repo.create(
                user_id=user_id,
                telegram_id=telegram_id,
                file_type="voice",
                telegram_file_id=telegram_file_id,
                gcs_path=gcs_path,
                expires_at=expires_at,
                file_size=file_size,
                mime_type="audio/ogg",
                message_id=message_id,
                is_premium=is_premium,
            )

            logger.info(
                f"Saved voice for user {telegram_id}: "
                f"duration={duration}s, gcs_path={gcs_path}"
            )

            return file_record.id

        except Exception as e:
            logger.error(f"Failed to save voice for user {user_id}: {e}")
            return None

    async def save_document(
        self,
        doc_bytes: bytes,
        user_id: int,
        telegram_id: int,
        telegram_file_id: str,
        file_size: int,
        file_name: str,
        mime_type: str,
        message_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Сохраняет документ.

        Returns:
            ID записи в БД или None если ошибка
        """
        if not settings.USE_GCS:
            logger.debug("GCS disabled, skipping document save")
            return None

        try:
            # Определяем расширение
            extension = file_name.split(".")[-1] if "." in file_name else "bin"

            # Загружаем в GCS
            gcs_path = await gcs_client.upload_file(
                data=doc_bytes,
                user_id=user_id,
                telegram_id=telegram_id,
                file_type="documents",
                file_extension=extension,
                content_type=mime_type,
                metadata={
                    "telegram_file_id": telegram_file_id,
                    "original_name": file_name,
                },
            )

            if not gcs_path:
                logger.warning(f"GCS upload failed for document, user={user_id}")
                return None

            # Определяем срок хранения
            is_premium = await self._is_user_premium(user_id)
            retention_days = self._get_retention_days(is_premium)
            expires_at = datetime.now() + timedelta(days=retention_days)

            # Сохраняем в БД
            file_record = await self.file_repo.create(
                user_id=user_id,
                telegram_id=telegram_id,
                file_type="document",
                telegram_file_id=telegram_file_id,
                gcs_path=gcs_path,
                expires_at=expires_at,
                file_name=file_name,
                file_size=file_size,
                mime_type=mime_type,
                message_id=message_id,
                is_premium=is_premium,
            )

            logger.info(
                f"Saved document for user {telegram_id}: "
                f"name={file_name}, gcs_path={gcs_path}"
            )

            return file_record.id

        except Exception as e:
            logger.error(f"Failed to save document for user {user_id}: {e}")
            return None

    async def save_video(
        self,
        video_bytes: bytes,
        user_id: int,
        telegram_id: int,
        telegram_file_id: str,
        file_size: int,
        duration: int,
        message_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Сохраняет видео.

        Returns:
            ID записи в БД или None если ошибка
        """
        if not settings.USE_GCS:
            logger.debug("GCS disabled, skipping video save")
            return None

        try:
            # Загружаем в GCS
            gcs_path = await gcs_client.upload_file(
                data=video_bytes,
                user_id=user_id,
                telegram_id=telegram_id,
                file_type="videos",
                file_extension="mp4",
                content_type="video/mp4",
                metadata={
                    "telegram_file_id": telegram_file_id,
                    "duration": str(duration),
                },
            )

            if not gcs_path:
                logger.warning(f"GCS upload failed for video, user={user_id}")
                return None

            # Определяем срок хранения
            is_premium = await self._is_user_premium(user_id)
            retention_days = self._get_retention_days(is_premium)
            expires_at = datetime.now() + timedelta(days=retention_days)

            # Сохраняем в БД
            file_record = await self.file_repo.create(
                user_id=user_id,
                telegram_id=telegram_id,
                file_type="video",
                telegram_file_id=telegram_file_id,
                gcs_path=gcs_path,
                expires_at=expires_at,
                file_size=file_size,
                mime_type="video/mp4",
                message_id=message_id,
                is_premium=is_premium,
            )

            logger.info(
                f"Saved video for user {telegram_id}: "
                f"duration={duration}s, gcs_path={gcs_path}"
            )

            return file_record.id

        except Exception as e:
            logger.error(f"Failed to save video for user {user_id}: {e}")
            return None

    async def cleanup_expired_files(self, batch_size: int = 100) -> dict:
        """
        Удаляет файлы с истекшим сроком хранения.

        Args:
            batch_size: Количество файлов за одну итерацию

        Returns:
            Статистика удаления
        """
        stats = {
            "checked": 0,
            "deleted_gcs": 0,
            "marked_deleted": 0,
            "errors": 0,
        }

        try:
            # Получаем файлы с истекшим сроком
            expired_files = await self.file_repo.get_expired_files(limit=batch_size)
            stats["checked"] = len(expired_files)

            if not expired_files:
                logger.debug("No expired files to clean up")
                return stats

            file_ids_to_mark = []

            for file_record in expired_files:
                try:
                    # Удаляем из GCS если есть путь
                    if file_record.gcs_path:
                        deleted = await gcs_client.delete_file(file_record.gcs_path)
                        if deleted:
                            stats["deleted_gcs"] += 1

                    file_ids_to_mark.append(file_record.id)

                except Exception as e:
                    logger.error(f"Failed to delete file {file_record.id}: {e}")
                    stats["errors"] += 1

            # Помечаем удалёнными в БД пачкой
            if file_ids_to_mark:
                marked = await self.file_repo.mark_batch_as_deleted(file_ids_to_mark)
                stats["marked_deleted"] = marked

            logger.info(
                f"Cleanup completed: checked={stats['checked']}, "
                f"gcs_deleted={stats['deleted_gcs']}, "
                f"db_marked={stats['marked_deleted']}, "
                f"errors={stats['errors']}"
            )

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            stats["errors"] += 1

        return stats

    async def update_retention_for_user(self, user_id: int, is_premium: bool) -> int:
        """
        Обновляет срок хранения файлов при изменении подписки.

        Args:
            user_id: ID пользователя
            is_premium: Новый статус Premium

        Returns:
            Количество обновлённых записей
        """
        retention_days = self._get_retention_days(is_premium)
        new_expires_at = datetime.now() + timedelta(days=retention_days)

        updated = await self.file_repo.update_retention(
            user_id=user_id,
            new_expires_at=new_expires_at,
        )

        logger.info(
            f"Updated retention for user {user_id}: "
            f"premium={is_premium}, updated={updated} files, "
            f"new_expires={new_expires_at.date()}"
        )

        return updated

    async def get_storage_stats(self, user_id: Optional[int] = None) -> dict:
        """
        Получает статистику хранилища.

        Args:
            user_id: ID пользователя (если None — общая статистика)

        Returns:
            Словарь со статистикой
        """
        return await self.file_repo.get_storage_stats(user_id)


# Глобальный экземпляр
file_storage_service = FileStorageService()
