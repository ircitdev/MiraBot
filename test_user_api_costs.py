"""Test user API costs endpoint."""
import asyncio
import sys
from database.repositories.api_cost import ApiCostRepository
from database.repositories.user import UserRepository


async def test_user_api_costs():
    """Test API costs for a specific user."""
    telegram_id = 1392513515  # Лиза

    print("=" * 60)
    print(f"Testing API costs for user telegram_id={telegram_id}")
    print("=" * 60)

    # Get user
    user_repo = UserRepository()
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        print(f"❌ User with telegram_id={telegram_id} not found!")
        return

    print(f"✅ User found: {user.display_name} (user_id={user.id})")
    print()

    # Get API costs
    repo = ApiCostRepository()

    print("Testing get_total_cost_by_user()...")
    total_cost = await repo.get_total_cost_by_user(user.id)
    print(f"  total_cost: ${total_cost:.4f}")
    print()

    print("Testing get_costs_by_provider()...")
    by_provider = await repo.get_costs_by_provider(user.id)
    print(f"  by_provider: {by_provider}")
    print()

    # Simulate endpoint response
    response = {
        "total_cost": total_cost,
        "by_provider": by_provider
    }

    print("=" * 60)
    print("Endpoint response would be:")
    print("=" * 60)
    print(response)
    print()

    if total_cost == 0.0 and len(by_provider) == 0:
        print("✅ User has no API costs (expected result)")
    else:
        print(f"✅ User has API costs: ${total_cost:.2f}")


if __name__ == "__main__":
    try:
        asyncio.run(test_user_api_costs())
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
