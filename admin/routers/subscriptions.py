"""
Subscriptions management router.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from admin.auth import get_current_admin
from database.repositories.subscription import SubscriptionRepository
from database.repositories.payment import PaymentRepository


router = APIRouter()
subscription_repo = SubscriptionRepository()
payment_repo = PaymentRepository()


@router.get("/expiring")
async def get_expiring_subscriptions(
    days: int = Query(7, ge=1, le=30),
    admin = Depends(get_current_admin),
):
    """Подписки, истекающие в ближайшие N дней."""
    
    subscriptions = await subscription_repo.get_expiring(days=days)
    
    return {
        "count": len(subscriptions),
        "subscriptions": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "plan": s.plan,
                "expires_at": s.expires_at.isoformat(),
                "auto_renew": s.auto_renew,
            }
            for s in subscriptions
        ],
    }


@router.get("/stats")
async def get_subscription_stats(admin = Depends(get_current_admin)):
    """Статистика подписок."""
    
    premium_count = await subscription_repo.get_premium_count()
    free_count = await subscription_repo.get_free_count()
    
    return {
        "premium": premium_count,
        "free": free_count,
        "total": premium_count + free_count,
        "conversion_rate": round(premium_count / (premium_count + free_count) * 100, 2) if (premium_count + free_count) > 0 else 0,
    }


@router.get("/payments")
async def list_payments(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    admin = Depends(get_current_admin),
):
    """Список платежей."""
    
    # Для простоты пока без пагинации в репозитории
    from datetime import datetime, timedelta
    
    total_revenue = await payment_repo.get_total_revenue()
    payments_count = await payment_repo.get_payments_count(status=status)
    revenue_by_plan = await payment_repo.get_revenue_by_plan()
    
    return {
        "total_revenue_rub": total_revenue / 100,
        "payments_count": payments_count,
        "by_plan": revenue_by_plan,
    }


@router.get("/payments/{payment_id}")
async def get_payment(
    payment_id: int,
    admin = Depends(get_current_admin),
):
    """Детали платежа."""
    
    payment = await payment_repo.get(payment_id)
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    return {
        "id": payment.id,
        "user_id": payment.user_id,
        "yookassa_payment_id": payment.yookassa_payment_id,
        "yookassa_status": payment.yookassa_status,
        "amount_rub": payment.amount / 100,
        "plan": payment.plan,
        "status": payment.status,
        "is_recurring": payment.is_recurring,
        "created_at": payment.created_at.isoformat(),
        "completed_at": payment.completed_at.isoformat() if payment.completed_at else None,
    }
