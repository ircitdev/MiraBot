"""
Добавляет колонку sent_photos в таблицу users.
Работает как с PostgreSQL, так и с SQLite.
"""

import asyncio
from sqlalchemy import text
from database.session import engine


async def add_column():
    """Добавляет колонку sent_photos."""
    async with engine.begin() as conn:
        # Получаем диалект
        dialect_name = engine.dialect.name

        if dialect_name == "sqlite":
            # Для SQLite проверяем через PRAGMA
            result = await conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result.fetchall()]

            if "sent_photos" in columns:
                print("Column 'sent_photos' already exists")
                return

            # Добавляем колонку (SQLite использует JSON вместо JSONB)
            await conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN sent_photos JSON DEFAULT '[]'
            """))

        else:
            # Для PostgreSQL
            result = await conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'sent_photos'
            """))

            if result.fetchone():
                print("Column 'sent_photos' already exists")
                return

            await conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN sent_photos JSONB DEFAULT '[]'::jsonb
            """))

        print("Column 'sent_photos' added successfully!")


if __name__ == "__main__":
    asyncio.run(add_column())
