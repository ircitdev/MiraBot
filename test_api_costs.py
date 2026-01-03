"""Quick test of API costs."""
import asyncio
from database.repositories.api_cost import ApiCostRepository


async def check():
    repo = ApiCostRepository()
    stats = await repo.get_stats_summary()
    print(f'Total cost: ${stats["total_cost"]:.4f}')
    print(f'Total tokens: {stats["total_tokens"]}')
    print(f'Unique users: {stats["unique_users"]}')

    # Get all users costs
    all_costs = await repo.get_all_users_total_costs()
    print(f'\nUsers with API costs: {len(all_costs)}')


asyncio.run(check())
