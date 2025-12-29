"""
Скрипт для назначения модератора.

Usage:
    python scripts/init_moderator.py --telegram-id 1392513515 --role moderator
    python scripts/init_moderator.py --telegram-id 123456789 --role admin
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.repositories.admin_user import AdminUserRepository
from database.repositories.user import UserRepository


async def init_moderator(telegram_id: int, role: str = 'moderator'):
    """Назначить пользователя модератором или администратором."""
    admin_user_repo = AdminUserRepository()
    user_repo = UserRepository()

    # Проверяем существует ли пользователь в базе
    user = await user_repo.get_by_telegram_id(telegram_id)

    if not user:
        print(f"❌ Пользователь с Telegram ID {telegram_id} не найден в базе данных")
        print(f"   Пользователь должен сначала запустить бота")
        return False

    # Проверяем не является ли уже модератором/админом
    existing = await admin_user_repo.get_by_telegram_id(telegram_id)

    if existing:
        print(f"✅ Пользователь {telegram_id} уже имеет роль '{existing.role}'")
        if existing.role != role:
            print(f"   Обновляю роль с '{existing.role}' на '{role}'...")
            updated = await admin_user_repo.update(existing.id, role=role)
            print(f"✅ Роль успешно обновлена на '{updated.role}'")
        return True

    # Создаём запись модератора/админа
    moderator = await admin_user_repo.create(
        telegram_id=telegram_id,
        role=role,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        created_by_id=None  # Системная инициализация
    )

    print(f"✅ Пользователь {telegram_id} назначен как '{role}'")
    print(f"   ID записи: {moderator.id}")
    print(f"   Имя: {moderator.first_name} {moderator.last_name or ''}")
    print(f"   Username: @{moderator.username or '—'}")
    print(f"   Роль: {moderator.role}")
    print(f"   Активен: {moderator.is_active}")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Назначить пользователя модератором или администратором",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Назначить модератора
  python scripts/init_moderator.py --telegram-id 1392513515

  # Назначить администратора
  python scripts/init_moderator.py --telegram-id 123456789 --role admin

  # Обновить роль существующего модератора на админа
  python scripts/init_moderator.py --telegram-id 1392513515 --role admin
        """
    )

    parser.add_argument(
        "--telegram-id",
        type=int,
        required=True,
        help="Telegram ID пользователя"
    )

    parser.add_argument(
        "--role",
        type=str,
        choices=['admin', 'moderator'],
        default='moderator',
        help="Роль: 'admin' или 'moderator' (по умолчанию: moderator)"
    )

    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"  Назначение {args.role}")
    print(f"{'=' * 60}\n")

    success = asyncio.run(init_moderator(args.telegram_id, args.role))

    print(f"\n{'=' * 60}")
    if success:
        print(f"  ✅ Операция завершена успешно")
    else:
        print(f"  ❌ Операция не выполнена")
    print(f"{'=' * 60}\n")

    sys.exit(0 if success else 1)
