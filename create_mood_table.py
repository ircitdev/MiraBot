"""Create mood_entries table."""
import asyncio
from sqlalchemy import text
from database.session import async_session


async def create_table():
    async with async_session() as session:
        await session.execute(text('''
            CREATE TABLE IF NOT EXISTS mood_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                message_id INTEGER REFERENCES messages(id),
                mood_score INTEGER NOT NULL,
                energy_level INTEGER,
                anxiety_level INTEGER,
                primary_emotion VARCHAR(50) NOT NULL,
                secondary_emotions TEXT,
                triggers TEXT,
                context_tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        await session.execute(text('''
            CREATE INDEX IF NOT EXISTS idx_mood_user_created ON mood_entries(user_id, created_at)
        '''))
        await session.commit()
        print('Table mood_entries created successfully!')


if __name__ == "__main__":
    asyncio.run(create_table())
