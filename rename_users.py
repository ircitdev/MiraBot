"""Скрипт для переименования пользователей."""
import asyncio
from database.repositories.user import UserRepository


async def rename_users():
    """Переименовать пользователей."""
    repo = UserRepository()

    # Переименовываем Юлю
    user1 = await repo.get_by_telegram_id(1443680424)
    if user1:
        await repo.update(user1.id, first_name="Юля")
        print(f"✅ Пользователь 1443680424 переименован: Юля (было: {user1.first_name})")
    else:
        print(f"❌ Пользователь 1443680424 не найден")

    # Переименовываем Ангелину
    user2 = await repo.get_by_telegram_id(1919839521)
    if user2:
        await repo.update(user2.id, first_name="Ангелина")
        print(f"✅ Пользователь 1919839521 переименован: Ангелина (было: {user2.first_name})")
    else:
        print(f"❌ Пользователь 1919839521 не найден")


if __name__ == "__main__":
    asyncio.run(rename_users())
