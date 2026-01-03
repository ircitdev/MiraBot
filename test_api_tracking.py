"""Тест записи API costs."""
import asyncio
from database.repositories.api_cost import ApiCostRepository


async def test_tracking():
    """Тестируем создание записи API cost."""
    repo = ApiCostRepository()

    # Создаем тестовую запись
    await repo.create(
        user_id=1,
        provider='claude',
        operation='test_operation',
        cost_usd=0.001234,
        input_tokens=100,
        output_tokens=200,
        total_tokens=300,
        model='claude-sonnet-4-20250514',
    )

    print("OK: Created test API cost record")

    # Проверяем статистику
    stats = await repo.get_stats_summary()
    print(f"\nOverall stats:")
    print(f"  Total cost: ${stats['total_cost']:.6f}")
    print(f"  Total tokens: {stats['total_tokens']}")
    print(f"  Unique users: {stats['unique_users']}")

    # Check specific user costs
    user_total = await repo.get_total_cost_by_user(user_id=1)
    print(f"\nUser 1:")
    print(f"  Total cost: ${user_total:.6f}")

    # Check all users list
    all_users = await repo.get_all_users_total_costs()
    print(f"\nTotal users with costs: {len(all_users)}")
    for user in all_users[:5]:
        print(f"  - {user['display_name'] or 'ID ' + str(user['telegram_id'])}: ${user['total_cost']:.6f}")


if __name__ == "__main__":
    asyncio.run(test_tracking())
