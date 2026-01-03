"""Скрипт для проверки расходов API."""
import asyncio
from database.repositories.api_cost import ApiCostRepository


async def check_costs():
    """Проверить расходы API."""
    repo = ApiCostRepository()

    # Общая статистика
    stats = await repo.get_stats_summary()
    print('📊 Общая статистика:')
    print(f'   Всего потрачено: ${stats["total_cost"]:.4f}')
    print(f'   Всего токенов: {stats["total_tokens"]:,}')
    print(f'   Уникальных пользователей: {stats["unique_users"]}')
    print(f'   По провайдерам: {stats["by_provider"]}')
    print()

    # Топ 10 пользователей
    top_users = await repo.get_top_users_by_cost(limit=10)
    print('🏆 Топ-10 пользователей по расходам:')
    for i, user in enumerate(top_users, 1):
        name = user['display_name'] or f'ID {user["telegram_id"]}'
        print(f'   {i}. {name}: ${user["total_cost"]:.4f} ({user["total_tokens"]:,} токенов)')


if __name__ == "__main__":
    asyncio.run(check_costs())
