"""Check users with API costs."""
import asyncio
from database.repositories.api_cost import ApiCostRepository


async def main():
    repo = ApiCostRepository()
    all_users = await repo.get_all_users_total_costs()
    print(f'Users with API costs: {len(all_users)}')
    for user in all_users:
        print(f"  User {user['user_id']} (TG: {user['telegram_id']}): ${user['total_cost']:.6f}")


asyncio.run(main())
