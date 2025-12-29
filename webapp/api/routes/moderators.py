"""
API эндпоинты для управления администраторами и модераторами.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from database.repositories.admin_user import AdminUserRepository
from webapp.api.middleware import get_current_admin, require_admin_role
from webapp.api.decorators import log_admin_action, log_critical_action


router = APIRouter(prefix="/moderators", tags=["moderators"])


# === Pydantic Models ===

class ModeratorCreate(BaseModel):
    """Данные для создания модератора."""
    telegram_id: int
    role: str = "moderator"  # 'admin' или 'moderator'
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    accent_color: str = "#1976d2"


class ModeratorUpdate(BaseModel):
    """Данные для обновления модератора."""
    role: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    accent_color: Optional[str] = None
    is_active: Optional[bool] = None


class ModeratorResponse(BaseModel):
    """Ответ с данными модератора."""
    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    role: str
    avatar_url: Optional[str]
    accent_color: str
    is_active: bool
    created_at: str
    last_login_at: Optional[str]

    class Config:
        from_attributes = True


# === Эндпоинты ===

@router.get("/me")
async def get_current_moderator(
    admin_data: dict = Depends(get_current_admin)
) -> ModeratorResponse:
    """
    Получить информацию о текущем авторизованном модераторе/админе.
    """
    admin_user = admin_data["admin_user"]

    return ModeratorResponse(
        id=admin_user.id,
        telegram_id=admin_user.telegram_id,
        username=admin_user.username,
        first_name=admin_user.first_name,
        last_name=admin_user.last_name,
        role=admin_user.role,
        avatar_url=admin_user.avatar_url,
        accent_color=admin_user.accent_color,
        is_active=admin_user.is_active,
        created_at=admin_user.created_at.isoformat(),
        last_login_at=admin_user.last_login_at.isoformat() if admin_user.last_login_at else None,
    )


@router.get("/")
async def list_moderators(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    admin_data: dict = Depends(require_admin_role)
) -> List[ModeratorResponse]:
    """
    Получить список всех модераторов и админов.

    Требует права администратора (role='admin').

    Query params:
        - role: Фильтр по роли ('admin', 'moderator')
        - is_active: Фильтр по активности (true/false)
    """
    repo = AdminUserRepository()
    moderators = await repo.list_all(role=role, is_active=is_active)

    return [
        ModeratorResponse(
            id=m.id,
            telegram_id=m.telegram_id,
            username=m.username,
            first_name=m.first_name,
            last_name=m.last_name,
            role=m.role,
            avatar_url=m.avatar_url,
            accent_color=m.accent_color,
            is_active=m.is_active,
            created_at=m.created_at.isoformat(),
            last_login_at=m.last_login_at.isoformat() if m.last_login_at else None,
        )
        for m in moderators
    ]


@router.get("/{moderator_id}")
async def get_moderator(
    moderator_id: int,
    admin_data: dict = Depends(get_current_admin)
) -> ModeratorResponse:
    """
    Получить информацию о конкретном модераторе по ID.
    """
    repo = AdminUserRepository()
    moderator = await repo.get(moderator_id)

    if not moderator:
        raise HTTPException(status_code=404, detail="Модератор не найден")

    return ModeratorResponse(
        id=moderator.id,
        telegram_id=moderator.telegram_id,
        username=moderator.username,
        first_name=moderator.first_name,
        last_name=moderator.last_name,
        role=moderator.role,
        avatar_url=moderator.avatar_url,
        accent_color=moderator.accent_color,
        is_active=moderator.is_active,
        created_at=moderator.created_at.isoformat(),
        last_login_at=moderator.last_login_at.isoformat() if moderator.last_login_at else None,
    )


@router.post("/")
@log_admin_action(
    action="moderator_create",
    resource_type="admin_user",
    extract_resource_id=lambda kwargs: kwargs.get("result", {}).get("id")
)
async def create_moderator(
    request: Request,
    data: ModeratorCreate,
    admin_data: dict = Depends(require_admin_role)
) -> ModeratorResponse:
    """
    Создать нового модератора или администратора.

    Требует права администратора (role='admin').

    Body:
        - telegram_id: Telegram ID пользователя
        - role: Роль ('admin' или 'moderator')
        - username: Username (опционально)
        - first_name: Имя (опционально)
        - last_name: Фамилия (опционально)
        - avatar_url: URL аватара (опционально)
        - accent_color: Цвет в HEX формате (по умолчанию #1976d2)
    """
    repo = AdminUserRepository()

    # Проверяем что такой модератор ещё не существует
    existing = await repo.get_by_telegram_id(data.telegram_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Пользователь с Telegram ID {data.telegram_id} уже является модератором"
        )

    # Создаём
    moderator = await repo.create(
        telegram_id=data.telegram_id,
        role=data.role,
        username=data.username,
        first_name=data.first_name,
        last_name=data.last_name,
        created_by_id=admin_data["admin_id"],
        avatar_url=data.avatar_url,
        accent_color=data.accent_color,
    )

    return ModeratorResponse(
        id=moderator.id,
        telegram_id=moderator.telegram_id,
        username=moderator.username,
        first_name=moderator.first_name,
        last_name=moderator.last_name,
        role=moderator.role,
        avatar_url=moderator.avatar_url,
        accent_color=moderator.accent_color,
        is_active=moderator.is_active,
        created_at=moderator.created_at.isoformat(),
        last_login_at=None,
    )


@router.patch("/{moderator_id}")
@log_admin_action(
    action="moderator_update",
    resource_type="admin_user",
    extract_resource_id=lambda kwargs: kwargs.get("moderator_id")
)
async def update_moderator(
    request: Request,
    moderator_id: int,
    data: ModeratorUpdate,
    admin_data: dict = Depends(require_admin_role)
) -> ModeratorResponse:
    """
    Обновить данные модератора.

    Требует права администратора (role='admin').
    """
    repo = AdminUserRepository()

    # Обновляем только переданные поля
    update_data = data.dict(exclude_unset=True)

    moderator = await repo.update(moderator_id, **update_data)

    if not moderator:
        raise HTTPException(status_code=404, detail="Модератор не найден")

    return ModeratorResponse(
        id=moderator.id,
        telegram_id=moderator.telegram_id,
        username=moderator.username,
        first_name=moderator.first_name,
        last_name=moderator.last_name,
        role=moderator.role,
        avatar_url=moderator.avatar_url,
        accent_color=moderator.accent_color,
        is_active=moderator.is_active,
        created_at=moderator.created_at.isoformat(),
        last_login_at=moderator.last_login_at.isoformat() if moderator.last_login_at else None,
    )


@router.post("/{moderator_id}/activate")
@log_admin_action(
    action="moderator_activate",
    resource_type="admin_user",
    extract_resource_id=lambda kwargs: kwargs.get("moderator_id")
)
async def activate_moderator(
    request: Request,
    moderator_id: int,
    admin_data: dict = Depends(require_admin_role)
) -> dict:
    """
    Активировать модератора.

    Требует права администратора (role='admin').
    """
    repo = AdminUserRepository()
    success = await repo.activate(moderator_id)

    if not success:
        raise HTTPException(status_code=404, detail="Модератор не найден")

    return {"success": True, "message": "Модератор активирован"}


@router.post("/{moderator_id}/deactivate")
@log_critical_action(action="moderator_deactivate", resource_type="admin_user")
async def deactivate_moderator(
    request: Request,
    moderator_id: int,
    admin_data: dict = Depends(require_admin_role)
) -> dict:
    """
    Деактивировать модератора (мягкое удаление).

    Требует права администратора (role='admin').

    Деактивированный модератор теряет доступ к админ-панели,
    но его данные и логи сохраняются.
    """
    repo = AdminUserRepository()

    # Нельзя деактивировать самого себя
    if moderator_id == admin_data["admin_id"]:
        raise HTTPException(
            status_code=400,
            detail="Нельзя деактивировать самого себя"
        )

    success = await repo.deactivate(moderator_id)

    if not success:
        raise HTTPException(status_code=404, detail="Модератор не найден")

    return {"success": True, "message": "Модератор деактивирован"}


@router.put("/me/accent-color")
async def update_my_accent_color(
    request: Request,
    data: dict,
    admin_data: dict = Depends(get_current_admin)
) -> dict:
    """
    Обновить акцентный цвет текущего модератора/админа.

    Body:
        - accent_color: Цвет в HEX формате (например, #1976d2)
    """
    accent_color = data.get("accent_color")

    if not accent_color or not accent_color.startswith("#"):
        raise HTTPException(status_code=400, detail="Неверный формат цвета. Используйте HEX формат (#RRGGBB)")

    repo = AdminUserRepository()
    moderator = await repo.update(admin_data["admin_id"], accent_color=accent_color)

    if not moderator:
        raise HTTPException(status_code=404, detail="Модератор не найден")

    return {
        "success": True,
        "accent_color": moderator.accent_color,
        "message": "Акцентный цвет обновлён"
    }


@router.get("/{moderator_id}/check-permission")
async def check_moderator_permission(
    moderator_id: int,
    required_role: str = "moderator",
    admin_data: dict = Depends(get_current_admin)
) -> dict:
    """
    Проверить права доступа модератора.

    Query params:
        - required_role: Требуемая роль ('admin' или 'moderator')

    Returns:
        {"has_permission": true/false, "role": "admin"/"moderator"}
    """
    repo = AdminUserRepository()
    moderator = await repo.get(moderator_id)

    if not moderator:
        raise HTTPException(status_code=404, detail="Модератор не найден")

    has_permission = await repo.check_permission(
        telegram_id=moderator.telegram_id,
        required_role=required_role
    )

    return {
        "has_permission": has_permission,
        "role": moderator.role,
        "is_active": moderator.is_active
    }
