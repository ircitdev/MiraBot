"""
Database session management.
Настройка подключения к БД и управление сессиями.
Поддерживает PostgreSQL и SQLite.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool, StaticPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from config.settings import settings
from loguru import logger


# Определяем параметры в зависимости от типа БД
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine_kwargs = {
    "echo": False,  # True для отладки SQL запросов
    "future": True,
}

if is_sqlite:
    # SQLite требует особых настроек для async
    engine_kwargs["poolclass"] = StaticPool
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL
    engine_kwargs["poolclass"] = NullPool

# Создаём engine
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

# Фабрика сессий
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для FastAPI.
    Возвращает асинхронную сессию БД.
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Контекстный менеджер для сессий вне FastAPI.
    Использование:
        async with get_session_context() as session:
            ...
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Инициализация базы данных.
    Создаёт все таблицы если их нет.
    """
    from database.models import Base
    
    logger.info("Initializing database...")
    
    async with engine.begin() as conn:
        # Создаём таблицы
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database initialized successfully")


async def close_db() -> None:
    """
    Закрытие подключения к БД.
    Вызывается при остановке приложения.
    """
    logger.info("Closing database connection...")
    await engine.dispose()
    logger.info("Database connection closed")


async def check_db_connection() -> bool:
    """
    Проверка подключения к БД.
    Возвращает True если подключение успешно.
    """
    try:
        async with async_session() as session:
            await session.execute("SELECT 1")
            return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
