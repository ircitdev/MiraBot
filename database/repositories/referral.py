"""
Referral repository.
CRUD операции для реферальной программы.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import Referral, User


class ReferralRepository:
    """Репозиторий для работы с рефералами."""
    
    async def create_code(
        self,
        user_id: int,
        code: str,
    ) -> Referral:
        """Создать реферальный код."""
        async with get_session_context() as session:
            referral = Referral(
                referrer_id=user_id,
                code=code,
                status="pending",
            )
            session.add(referral)
            await session.commit()
            await session.refresh(referral)
            
            return referral
    
    async def get_by_code(self, code: str) -> Optional[Referral]:
        """Получить реферал по коду."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Referral).where(Referral.code == code)
            )
            return result.scalar_one_or_none()
    
    async def get_code_by_user(self, user_id: int) -> Optional[Referral]:
        """Получить реферальный код пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Referral).where(
                    and_(
                        Referral.referrer_id == user_id,
                        Referral.referred_id.is_(None)  # Код, который ещё не использован
                    )
                ).order_by(Referral.created_at.desc()).limit(1)
            )
            return result.scalar_one_or_none()
    
    async def get_by_referred(self, referred_id: int) -> Optional[Referral]:
        """Получить реферал по приглашённому пользователю."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Referral).where(Referral.referred_id == referred_id)
            )
            return result.scalar_one_or_none()
    
    async def activate(
        self,
        referral_id: int,
        referred_id: int,
    ) -> Optional[Referral]:
        """Активировать реферал."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Referral).where(Referral.id == referral_id)
            )
            referral = result.scalar_one_or_none()
            
            if not referral:
                return None
            
            referral.referred_id = referred_id
            referral.status = "activated"
            referral.activated_at = datetime.now()
            
            await session.commit()
            await session.refresh(referral)
            
            return referral
    
    async def mark_rewarded(
        self,
        referral_id: int,
        referrer: bool = False,
        referred: bool = False,
    ) -> Optional[Referral]:
        """Отметить выдачу награды."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Referral).where(Referral.id == referral_id)
            )
            referral = result.scalar_one_or_none()
            
            if not referral:
                return None
            
            if referrer:
                referral.reward_given_referrer = True
            if referred:
                referral.reward_given_referred = True
            
            if referral.reward_given_referrer and referral.reward_given_referred:
                referral.status = "rewarded"
            
            await session.commit()
            await session.refresh(referral)
            
            return referral
    
    async def count_by_referrer(self, referrer_id: int) -> int:
        """Количество активированных рефералов у пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(Referral.id)).where(
                    and_(
                        Referral.referrer_id == referrer_id,
                        Referral.status.in_(["activated", "rewarded"])
                    )
                )
            )
            return result.scalar() or 0
    
    async def get_referrals_by_user(
        self,
        referrer_id: int,
        limit: int = 50,
    ) -> List[Referral]:
        """Получить список рефералов пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Referral).where(
                    and_(
                        Referral.referrer_id == referrer_id,
                        Referral.status.in_(["activated", "rewarded"])
                    )
                ).order_by(Referral.activated_at.desc()).limit(limit)
            )
            return list(result.scalars().all())
    
    async def get_total_count(self) -> int:
        """Общее количество активированных рефералов."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(Referral.id)).where(
                    Referral.status.in_(["activated", "rewarded"])
                )
            )
            return result.scalar() or 0
    
    async def get_count_since(self, since: datetime) -> int:
        """Количество рефералов с определённой даты."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(Referral.id)).where(
                    and_(
                        Referral.status.in_(["activated", "rewarded"]),
                        Referral.activated_at >= since
                    )
                )
            )
            return result.scalar() or 0
    
    async def get_top_referrers(self, limit: int = 20) -> List[dict]:
        """Топ пользователей по количеству рефералов."""
        async with get_session_context() as session:
            result = await session.execute(
                """
                SELECT 
                    r.referrer_id,
                    u.display_name,
                    u.username,
                    COUNT(*) as referral_count
                FROM referrals r
                JOIN users u ON r.referrer_id = u.id
                WHERE r.status IN ('activated', 'rewarded')
                GROUP BY r.referrer_id, u.display_name, u.username
                ORDER BY referral_count DESC
                LIMIT :limit
                """,
                {"limit": limit}
            )
            
            return [
                {
                    "user_id": row[0],
                    "display_name": row[1],
                    "username": row[2],
                    "referral_count": row[3],
                }
                for row in result.fetchall()
            ]
