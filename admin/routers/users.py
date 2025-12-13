"""
Users management router.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from admin.auth import get_current_admin, get_superadmin
from database.repositories.user import UserRepository
from database.repositories.subscription import SubscriptionRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.referral import ReferralRepository


router = APIRouter()
user_repo = UserRepository()
subscription_repo = SubscriptionRepository()
conversation_repo = ConversationRepository()
referral_repo = ReferralRepository()


class ExtendSubscriptionRequest(BaseModel):
    days: int


class BlockUserRequest(BaseModel):
    reason: str


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    subscription: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    admin = Depends(get_current_admin),
):
    """Список пользователей с пагинацией."""
    
    filters = {}
    if subscription:
        filters["subscription_plan"] = subscription
    
    users, total = await user_repo.get_paginated(
        page=page,
        per_page=per_page,
        search=search,
        filters=filters if filters else None,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    
    return {
        "users": [
            {
                "id": u.id,
                "telegram_id": u.telegram_id,
                "username": u.username,
                "display_name": u.display_name,
                "persona": u.persona,
                "is_blocked": u.is_blocked,
                "created_at": u.created_at.isoformat(),
                "last_active_at": u.last_active_at.isoformat() if u.last_active_at else None,
            }
            for u in users
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        },
    }


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    admin = Depends(get_current_admin),
):
    """Детальная информация о пользователе."""
    
    user = await user_repo.get(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription = await subscription_repo.get_active(user_id)
    
    # Статистика
    messages_count = await conversation_repo.count_by_user(user_id)
    sessions_count = await conversation_repo.count_sessions(user_id)
    avg_messages = await conversation_repo.avg_messages_per_session(user_id)
    crisis_count = await conversation_repo.count_crisis_episodes(user_id)
    
    # Рефералы
    referral_count = await referral_repo.count_by_referrer(user_id)
    
    return {
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "display_name": user.display_name,
            "persona": user.persona,
            "partner_name": user.partner_name,
            "children_info": user.children_info,
            "marriage_years": user.marriage_years,
            "rituals_enabled": user.rituals_enabled,
            "proactive_messages": user.proactive_messages,
            "is_blocked": user.is_blocked,
            "block_reason": user.block_reason,
            "special_status": user.special_status,
            "created_at": user.created_at.isoformat(),
            "last_active_at": user.last_active_at.isoformat() if user.last_active_at else None,
        },
        "subscription": {
            "plan": subscription.plan if subscription else "free",
            "status": subscription.status if subscription else None,
            "expires_at": subscription.expires_at.isoformat() if subscription and subscription.expires_at else None,
            "auto_renew": subscription.auto_renew if subscription else False,
            "messages_today": subscription.messages_today if subscription else 0,
        } if subscription else None,
        "stats": {
            "messages_count": messages_count,
            "sessions_count": sessions_count,
            "avg_messages_per_session": avg_messages,
            "crisis_episodes": crisis_count,
            "referrals_count": referral_count,
            "days_active": await user_repo.get_days_active(user_id),
        },
    }


@router.get("/{user_id}/conversations")
async def get_user_conversations(
    user_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    admin = Depends(get_current_admin),
):
    """История сообщений пользователя."""
    
    user = await user_repo.get(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    messages, total = await conversation_repo.get_paginated(
        user_id=user_id,
        page=page,
        per_page=per_page,
    )
    
    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "tags": m.tags,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        },
    }


@router.post("/{user_id}/extend-subscription")
async def extend_subscription(
    user_id: int,
    request: ExtendSubscriptionRequest,
    admin = Depends(get_current_admin),
):
    """Продлить подписку пользователя (бонус)."""
    
    user = await user_repo.get(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription = await subscription_repo.get_active(user_id)
    
    if subscription:
        await subscription_repo.extend_days(subscription.id, request.days)
    else:
        subscription = await subscription_repo.create_trial(user_id, request.days)
    
    return {"success": True, "days_added": request.days}


@router.post("/{user_id}/block")
async def block_user(
    user_id: int,
    request: BlockUserRequest,
    admin = Depends(get_superadmin),
):
    """Заблокировать пользователя."""
    
    user = await user_repo.get(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await user_repo.update(
        user_id,
        is_blocked=True,
        block_reason=request.reason,
    )
    
    return {"success": True}


@router.post("/{user_id}/unblock")
async def unblock_user(
    user_id: int,
    admin = Depends(get_superadmin),
):
    """Разблокировать пользователя."""
    
    user = await user_repo.get(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await user_repo.update(
        user_id,
        is_blocked=False,
        block_reason=None,
    )
    
    return {"success": True}
