"""
Google Cloud Storage Client.
Клиент для загрузки и управления файлами в GCS.
"""

from google.cloud import storage
from google.oauth2 import service_account
from pathlib import Path
from typing import Optional, BinaryIO
from datetime import datetime, timedelta
from loguru import logger
import mimetypes

from config.settings import settings


class GCSClient:
    """Клиент для работы с Google Cloud Storage."""

    def __init__(self):
        self._client: Optional[storage.Client] = None
        self._bucket: Optional[storage.Bucket] = None
        self._initialized = False

    def _init_client(self):
        """Ленивая инициализация клиента GCS."""
        if self._initialized:
            return

        if not settings.USE_GCS:
            logger.info("GCS disabled in settings")
            return

        try:
            credentials_path = Path(settings.GCS_CREDENTIALS_PATH)
            if not credentials_path.exists():
                logger.warning(f"GCS credentials not found: {credentials_path}")
                return

            credentials = service_account.Credentials.from_service_account_file(
                str(credentials_path)
            )
            self._client = storage.Client(credentials=credentials)
            self._bucket = self._client.bucket(settings.GCS_BUCKET_NAME)

            # Проверяем доступ к бакету
            if not self._bucket.exists():
                logger.error(f"GCS bucket not found: {settings.GCS_BUCKET_NAME}")
                return

            self._initialized = True
            logger.info(f"GCS client initialized, bucket: {settings.GCS_BUCKET_NAME}")

        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {e}")

    @property
    def is_available(self) -> bool:
        """Проверяет доступность GCS."""
        self._init_client()
        return self._initialized and self._bucket is not None

    def _get_file_path(
        self,
        user_id: int,
        telegram_id: int,
        file_type: str,
        file_extension: str,
    ) -> str:
        """
        Генерирует путь файла в GCS.

        Структура:
        users/{telegram_id}/photos/2025/12/20/filename.jpg
        users/{telegram_id}/voice/2025/12/20/filename.ogg
        users/{telegram_id}/documents/2025/12/20/filename.pdf
        """
        now = datetime.now()
        date_path = now.strftime("%Y/%m/%d")
        timestamp = now.strftime("%H%M%S")
        filename = f"{timestamp}_{user_id}.{file_extension}"

        return f"users/{telegram_id}/{file_type}/{date_path}/{filename}"

    async def upload_file(
        self,
        data: bytes,
        user_id: int,
        telegram_id: int,
        file_type: str,  # photos, voice, documents
        file_extension: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Загружает файл в GCS.

        Args:
            data: Байты файла
            user_id: ID пользователя в БД
            telegram_id: Telegram ID пользователя
            file_type: Тип файла (photos, voice, documents)
            file_extension: Расширение файла
            content_type: MIME тип
            metadata: Дополнительные метаданные

        Returns:
            Путь файла в GCS или None если ошибка
        """
        if not self.is_available:
            return None

        try:
            file_path = self._get_file_path(
                user_id, telegram_id, file_type, file_extension
            )

            blob = self._bucket.blob(file_path)

            # Устанавливаем метаданные
            if metadata:
                blob.metadata = metadata

            # Определяем content type
            if not content_type:
                content_type, _ = mimetypes.guess_type(f"file.{file_extension}")
                content_type = content_type or "application/octet-stream"

            # Загружаем
            blob.upload_from_string(data, content_type=content_type)

            logger.info(f"Uploaded file to GCS: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to upload file to GCS: {e}")
            return None

    async def upload_file_from_stream(
        self,
        file_stream: BinaryIO,
        user_id: int,
        telegram_id: int,
        file_type: str,
        file_extension: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """Загружает файл из потока."""
        data = file_stream.read()
        return await self.upload_file(
            data=data,
            user_id=user_id,
            telegram_id=telegram_id,
            file_type=file_type,
            file_extension=file_extension,
            content_type=content_type,
            metadata=metadata,
        )

    async def delete_file(self, file_path: str) -> bool:
        """Удаляет файл из GCS."""
        if not self.is_available:
            return False

        try:
            blob = self._bucket.blob(file_path)
            blob.delete()
            logger.info(f"Deleted file from GCS: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file from GCS: {e}")
            return False

    async def delete_files_batch(self, file_paths: list[str]) -> int:
        """Удаляет пакет файлов. Возвращает количество удалённых."""
        if not self.is_available:
            return 0

        deleted = 0
        for path in file_paths:
            if await self.delete_file(path):
                deleted += 1

        return deleted

    async def list_files(
        self,
        prefix: str,
        max_results: int = 1000,
    ) -> list[dict]:
        """
        Получает список файлов по префиксу.

        Returns:
            Список словарей с информацией о файлах
        """
        if not self.is_available:
            return []

        try:
            blobs = self._bucket.list_blobs(prefix=prefix, max_results=max_results)

            files = []
            for blob in blobs:
                files.append({
                    "path": blob.name,
                    "size": blob.size,
                    "created": blob.time_created,
                    "updated": blob.updated,
                    "content_type": blob.content_type,
                    "metadata": blob.metadata,
                })

            return files
        except Exception as e:
            logger.error(f"Failed to list files from GCS: {e}")
            return []

    async def get_files_older_than(
        self,
        prefix: str,
        days: int,
    ) -> list[str]:
        """
        Получает пути файлов старше указанного количества дней.
        """
        if not self.is_available:
            return []

        try:
            cutoff = datetime.now() - timedelta(days=days)
            blobs = self._bucket.list_blobs(prefix=prefix)

            old_files = []
            for blob in blobs:
                if blob.time_created and blob.time_created.replace(tzinfo=None) < cutoff:
                    old_files.append(blob.name)

            return old_files
        except Exception as e:
            logger.error(f"Failed to get old files from GCS: {e}")
            return []

    def get_public_url(self, file_path: str) -> Optional[str]:
        """Возвращает публичный URL файла (если бакет публичный)."""
        return f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/{file_path}"

    async def get_signed_url(
        self,
        file_path: str,
        expiration_minutes: int = 60,
    ) -> Optional[str]:
        """Генерирует подписанный URL для временного доступа."""
        if not self.is_available:
            return None

        try:
            blob = self._bucket.blob(file_path)
            url = blob.generate_signed_url(
                expiration=timedelta(minutes=expiration_minutes),
                method="GET",
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate signed URL: {e}")
            return None


# Глобальный экземпляр
gcs_client = GCSClient()
