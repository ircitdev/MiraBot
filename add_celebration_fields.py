"""
Миграция: добавление полей birthday и anniversary в таблицу users.
Поддержка SQLite и PostgreSQL.
"""

import asyncio
from sqlalchemy import text
from database.session import engine


async def migrate():
    """Добавляет поля birthday и anniversary."""
    async with engine.begin() as conn:
        # Проверяем тип БД
        dialect = engine.dialect.name

        if dialect == "sqlite":
            # Для SQLite проверяем через PRAGMA
            result = await conn.execute(text("PRAGMA table_info(users)"))
            columns = {row[1] for row in result.fetchall()}

            if "birthday" not in columns:
                await conn.execute(text("ALTER TABLE users ADD COLUMN birthday DATE"))
                print("Колонка birthday добавлена")
            else:
                print("Колонка birthday уже существует")

            if "anniversary" not in columns:
                await conn.execute(text("ALTER TABLE users ADD COLUMN anniversary DATE"))
                print("Колонка anniversary добавлена")
            else:
                print("Колонка anniversary уже существует")

        else:
            # Для PostgreSQL используем information_schema
            result = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name IN ('birthday', 'anniversary')"
            ))
            existing = [row[0] for row in result.fetchall()]

            if "birthday" not in existing:
                await conn.execute(text("ALTER TABLE users ADD COLUMN birthday DATE"))
                print("Колонка birthday добавлена")
            else:
                print("Колонка birthday уже существует")

            if "anniversary" not in existing:
                await conn.execute(text("ALTER TABLE users ADD COLUMN anniversary DATE"))
                print("Колонка anniversary добавлена")
            else:
                print("Колонка anniversary уже существует")

    print("Миграция завершена!")


if __name__ == "__main__":
    asyncio.run(migrate())
