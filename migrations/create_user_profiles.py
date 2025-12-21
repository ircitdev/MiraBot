"""
Create user_profiles table migration.
"""

import asyncio
from sqlalchemy import text
import sys
sys.path.insert(0, '/root/mira_bot')

from database.session import async_session


async def create_user_profiles_table():
    async with async_session() as session:
        # Create table
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                country VARCHAR(100),
                city VARCHAR(100),
                location_confidence INTEGER,
                occupation VARCHAR(200),
                occupation_confidence INTEGER,
                age INTEGER,
                age_confidence INTEGER,
                hobbies TEXT,
                partner_name VARCHAR(100),
                partner_age INTEGER,
                partner_occupation VARCHAR(200),
                partner_hobbies TEXT,
                partner_confidence INTEGER,
                relationship_start DATE,
                wedding_date DATE,
                how_met TEXT,
                children JSONB DEFAULT '[]',
                children_confidence INTEGER,
                important_dates JSONB DEFAULT '[]',
                notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )
        """))

        # Create index
        await session.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id)"
        ))

        await session.commit()
        print("Table user_profiles created successfully")


if __name__ == "__main__":
    asyncio.run(create_user_profiles_table())
