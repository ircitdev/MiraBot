"""Test API endpoints manually."""
import asyncio
import sys
from datetime import datetime, timedelta
from database.repositories.api_cost import ApiCostRepository


async def test_endpoints():
    """Test the data that endpoints would return."""
    repo = ApiCostRepository()

    # Test /api/admin/api-costs/stats
    print("=" * 60)
    print("Testing /api/admin/api-costs/stats")
    print("=" * 60)

    to_date = datetime.now()
    from_date = to_date - timedelta(days=30)

    stats = await repo.get_stats_summary(from_date=from_date, to_date=to_date)
    print(f"Stats: {stats}")
    print()

    # Test /api/admin/api-costs/by-date
    print("=" * 60)
    print("Testing /api/admin/api-costs/by-date")
    print("=" * 60)

    costs_by_date = await repo.get_costs_by_date(
        from_date=from_date,
        to_date=to_date
    )
    print(f"Costs by date ({len(costs_by_date)} entries):")
    for cost in costs_by_date[:5]:
        print(f"  {cost}")
    print()

    # Test /api/admin/api-costs/users/summary
    print("=" * 60)
    print("Testing /api/admin/api-costs/users/summary")
    print("=" * 60)

    users_summary = await repo.get_all_users_total_costs()
    print(f"Users summary ({len(users_summary)} users):")
    for user in users_summary[:5]:
        print(f"  {user}")
    print()

    print("=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_endpoints())
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
