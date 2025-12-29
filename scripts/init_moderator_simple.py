"""
Упрощённый скрипт для назначения модератора.
Не требует наличия пользователя в users таблице.

Usage:
    python scripts/init_moderator_simple.py --telegram-id 1392513515 --first-name "Лиза"
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.repositories.admin_user import AdminUserRepository


async def init_moderator(
    telegram_id: int,
    role: str = 'moderator',
    first_name: str = None,
    last_name: str = None,
    username: str = None
):
    """Назначить модератора."""
    admin_user_repo = AdminUserRepository()

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
        username=username,
        first_name=first_name,
        last_name=last_name,
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
        description="Назначить пользователя модератором или администратором"
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
        help="Роль (по умолчанию: moderator)"
    )

    parser.add_argument(
        "--first-name",
        type=str,
        help="Имя"
    )

    parser.add_argument(
        "--last-name",
        type=str,
        help="Фамилия"
    )

    parser.add_argument(
        "--username",
        type=str,
        help="Username (без @)"
    )

    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"  Назначение {args.role}")
    print(f"{'=' * 60}\n")

    success = asyncio.run(init_moderator(
        telegram_id=args.telegram_id,
        role=args.role,
        first_name=args.first_name,
        last_name=args.last_name,
        username=args.username
    ))

    print(f"\n{'=' * 60}")
    if success:
        print(f"  ✅ Операция завершена успешно")
    else:
        print(f"  ❌ Операция не выполнена")
    print(f"{'=' * 60}\n")

    sys.exit(0 if success else 1)
