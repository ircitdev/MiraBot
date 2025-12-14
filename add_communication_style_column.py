"""
Миграция: добавление поля communication_style в таблицу users.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from database.session import async_session


async def add_column():
    """Добавляет колонку communication_style в таблицу users."""
    async with async_session() as session:
        try:
            # Проверяем, существует ли колонка
            check_sql = text("""
                SELECT COUNT(*) FROM pragma_table_info('users')
                WHERE name = 'communication_style'
            """)
            result = await session.execute(check_sql)
            exists = result.scalar() > 0

            if exists:
                print("Колонка communication_style уже существует")
                return

            # Добавляем колонку
            alter_sql = text("""
                ALTER TABLE users ADD COLUMN communication_style JSON DEFAULT '{}'
            """)
            await session.execute(alter_sql)
            await session.commit()
            print("Колонка communication_style успешно добавлена!")

        except Exception as e:
            print(f"Ошибка: {e}")
            await session.rollback()


if __name__ == "__main__":
    asyncio.run(add_column())
