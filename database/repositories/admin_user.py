"""
Admin user repository.
CRUD операции для администраторов.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import AdminUser, AdminLog


class AdminUserRepository:
    """Репозиторий для работы с администраторами."""
    
    async def create(
        self,
        email: str,
        password_hash: str,
        name: Optional[str] = None,
        role: str = "admin",
    ) -> AdminUser:
        """Создать администратора."""
        async with get_session_context() as session:
            admin = AdminUser(
                email=email,
                password_hash=password_hash,
                name=name,
                role=role,
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)
            
            return admin
    
    async def get(self, admin_id: int) -> Optional[AdminUser]:
        """Получить админа по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[AdminUser]:
        """Получить админа по email."""
        async with get_session_context() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.email == email)
            )
            return result.scalar_one_or_none()
    
    async def get_all(self) -> List[AdminUser]:
        """Получить всех админов."""
        async with get_session_context() as session:
            result = await session.execute(
                select(AdminUser).order_by(AdminUser.created_at.desc())
            )
            return list(result.scalars().all())
    
    async def update(self, admin_id: int, **kwargs) -> Optional[AdminUser]:
        """Обновить админа."""
        async with get_session_context() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            admin = result.scalar_one_or_none()
            
            if not admin:
                return None
            
            for key, value in kwargs.items():
                if hasattr(admin, key):
                    setattr(admin, key, value)
            
            await session.commit()
            await session.refresh(admin)
            
            return admin
    
    async def update_last_login(self, admin_id: int) -> None:
        """Обновить время последнего входа."""
        await self.update(admin_id, last_login_at=datetime.now())
    
    async def delete(self, admin_id: int) -> bool:
        """Удалить админа."""
        async with get_session_context() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
            admin = result.scalar_one_or_none()
            
            if admin:
                await session.delete(admin)
                await session.commit()
                return True
            
            return False
    
    async def log_action(
        self,
        admin_id: int,
        action: str,
        target_user_id: Optional[int] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AdminLog:
        """Записать действие админа в лог."""
        async with get_session_context() as session:
            log = AdminLog(
                admin_id=admin_id,
                action=action,
                target_user_id=target_user_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(log)
            await session.commit()
            await session.refresh(log)
            
            return log
    
    async def get_logs(
        self,
        admin_id: Optional[int] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[AdminLog]:
        """Получить логи действий."""
        async with get_session_context() as session:
            query = select(AdminLog)
            
            if admin_id:
                query = query.where(AdminLog.admin_id == admin_id)
            if action:
                query = query.where(AdminLog.action == action)
            
            query = query.order_by(AdminLog.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
