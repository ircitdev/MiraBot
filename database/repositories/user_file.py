"""
UserFile repository.
CRUD операции для файлов пользователей в GCS.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import UserFile, User, Subscription


class UserFileRepository:
    """Репозиторий для работы с файлами пользователей."""

    async def create(
        self,
        user_id: int,
        telegram_id: int,
        file_type: str,
        telegram_file_id: str,
        gcs_path: str,
        expires_at: datetime,
        gcs_url: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        mime_type: Optional[str] = None,
        message_id: Optional[int] = None,
        is_premium: bool = False,
    ) -> UserFile:
        """
        Создать запись о файле.

        Args:
            user_id: ID пользователя в БД
            telegram_id: Telegram ID пользователя
            file_type: Тип файла (photo, voice, document и т.д.)
            telegram_file_id: ID файла в Telegram
            gcs_path: Путь в GCS бакете
            expires_at: Дата истечения
            gcs_url: Публичный URL (опционально)
            file_name: Имя файла
            file_size: Размер в байтах
            mime_type: MIME тип
            message_id: ID сообщения в Telegram
            is_premium: Premium ли пользователь на момент загрузки

        Returns:
            Созданная запись UserFile
        """
        async with get_session_context() as session:
            user_file = UserFile(
                user_id=user_id,
                file_type=file_type,
                telegram_file_id=telegram_file_id,
                gcs_path=gcs_path,
                gcs_url=gcs_url,
                file_name=file_name,
                file_size=file_size,
                mime_type=mime_type,
                message_id=message_id,
                expires_at=expires_at,
                is_premium_at_upload=is_premium,
            )
            session.add(user_file)
            await session.commit()
            await session.refresh(user_file)
            return user_file

    async def get(self, file_id: int) -> Optional[UserFile]:
        """Получить файл по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserFile).where(UserFile.id == file_id)
            )
            return result.scalar_one_or_none()

    async def get_by_gcs_path(self, gcs_path: str) -> Optional[UserFile]:
        """Получить файл по пути в GCS."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserFile).where(UserFile.gcs_path == gcs_path)
            )
            return result.scalar_one_or_none()

    async def get_user_files(
        self,
        user_id: int,
        file_type: Optional[str] = None,
        include_deleted: bool = False,
    ) -> List[UserFile]:
        """
        Получить файлы пользователя.

        Args:
            user_id: ID пользователя
            file_type: Фильтр по типу файла
            include_deleted: Включать удалённые

        Returns:
            Список файлов
        """
        async with get_session_context() as session:
            query = select(UserFile).where(UserFile.user_id == user_id)

            if not include_deleted:
                query = query.where(UserFile.is_deleted == False)

            if file_type:
                query = query.where(UserFile.file_type == file_type)

            query = query.order_by(UserFile.created_at.desc())

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_expired_files(
        self,
        limit: int = 100,
    ) -> List[UserFile]:
        """
        Получить файлы с истёкшим сроком хранения.

        Args:
            limit: Максимальное количество файлов

        Returns:
            Список файлов для удаления
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(UserFile)
                .where(
                    and_(
                        UserFile.expires_at <= datetime.now(),
                        UserFile.is_deleted == False,
                    )
                )
                .order_by(UserFile.expires_at.asc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def mark_as_deleted(self, file_id: int) -> bool:
        """
        Пометить файл как удалённый.

        Args:
            file_id: ID файла

        Returns:
            True если успешно
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(UserFile).where(UserFile.id == file_id)
            )
            user_file = result.scalar_one_or_none()

            if not user_file:
                return False

            user_file.is_deleted = True
            user_file.deleted_at = datetime.now()
            await session.commit()
            return True

    async def mark_batch_as_deleted(self, file_ids: List[int]) -> int:
        """
        Пометить несколько файлов как удалённые.

        Args:
            file_ids: Список ID файлов

        Returns:
            Количество обновлённых записей
        """
        if not file_ids:
            return 0

        async with get_session_context() as session:
            result = await session.execute(
                update(UserFile)
                .where(UserFile.id.in_(file_ids))
                .values(is_deleted=True, deleted_at=datetime.now())
            )
            await session.commit()
            return result.rowcount

    async def update_retention(
        self,
        user_id: int,
        new_expires_at: datetime,
    ) -> int:
        """
        Обновить срок хранения для всех файлов пользователя.
        Используется при переходе на/с Premium.

        Args:
            user_id: ID пользователя
            new_expires_at: Новая дата истечения

        Returns:
            Количество обновлённых записей
        """
        async with get_session_context() as session:
            result = await session.execute(
                update(UserFile)
                .where(
                    and_(
                        UserFile.user_id == user_id,
                        UserFile.is_deleted == False,
                        UserFile.expires_at < new_expires_at,  # Только продлеваем
                    )
                )
                .values(expires_at=new_expires_at)
            )
            await session.commit()
            return result.rowcount

    async def get_storage_stats(self, user_id: Optional[int] = None) -> dict:
        """
        Получить статистику хранилища.

        Args:
            user_id: ID пользователя (если None — общая статистика)

        Returns:
            Словарь со статистикой
        """
        async with get_session_context() as session:
            base_filter = UserFile.is_deleted == False
            if user_id:
                base_filter = and_(base_filter, UserFile.user_id == user_id)

            # Общее количество и размер
            total_query = select(
                func.count(UserFile.id),
                func.coalesce(func.sum(UserFile.file_size), 0),
            ).where(base_filter)
            total_result = await session.execute(total_query)
            total_count, total_size = total_result.one()

            # По типам
            by_type_query = select(
                UserFile.file_type,
                func.count(UserFile.id),
                func.coalesce(func.sum(UserFile.file_size), 0),
            ).where(base_filter).group_by(UserFile.file_type)
            by_type_result = await session.execute(by_type_query)
            by_type = {
                row[0]: {"count": row[1], "size": row[2]}
                for row in by_type_result.fetchall()
            }

            # Истекающие в ближайшие 7 дней
            week_later = datetime.now() + timedelta(days=7)
            expiring_query = select(func.count(UserFile.id)).where(
                and_(
                    base_filter,
                    UserFile.expires_at <= week_later,
                )
            )
            expiring_result = await session.execute(expiring_query)
            expiring_soon = expiring_result.scalar() or 0

            return {
                "total_count": total_count or 0,
                "total_size_bytes": total_size or 0,
                "total_size_mb": round((total_size or 0) / (1024 * 1024), 2),
                "by_type": by_type,
                "expiring_in_7_days": expiring_soon,
            }

    async def count_by_user(self, user_id: int) -> int:
        """Подсчитать количество файлов пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(UserFile.id)).where(
                    and_(
                        UserFile.user_id == user_id,
                        UserFile.is_deleted == False,
                    )
                )
            )
            return result.scalar() or 0


# Глобальный экземпляр
user_file_repository = UserFileRepository()
