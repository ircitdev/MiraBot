"""
Settings Repository.
Работа с системными настройками и акциями.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from database.session import get_session_context
from database.models import SystemSettings, Promotion, PaymentStats


class SettingsRepository:
    """Репозиторий для системных настроек."""

    # ==================== GET ====================

    async def get(self, key: str) -> Optional[Any]:
        """Получить значение настройки по ключу."""
        async with get_session_context() as session:
            result = await session.execute(
                select(SystemSettings).where(SystemSettings.key == key)
            )
            setting = result.scalar_one_or_none()

            if not setting:
                return None

            return self._parse_value(setting.value, setting.value_type)

    async def get_all(self, include_secrets: bool = False) -> Dict[str, Any]:
        """Получить все настройки."""
        async with get_session_context() as session:
            result = await session.execute(select(SystemSettings))
            settings = result.scalars().all()

            return {
                s.key: {
                    "value": "***" if s.is_secret and not include_secrets else self._parse_value(s.value, s.value_type),
                    "type": s.value_type,
                    "description": s.description,
                    "is_secret": s.is_secret,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in settings
            }

    async def get_raw(self, key: str) -> Optional[SystemSettings]:
        """Получить объект настройки."""
        async with get_session_context() as session:
            result = await session.execute(
                select(SystemSettings).where(SystemSettings.key == key)
            )
            return result.scalar_one_or_none()

    # ==================== SET ====================

    async def set(
        self,
        key: str,
        value: Any,
        value_type: str = "string",
        description: Optional[str] = None,
        is_secret: bool = False,
    ) -> SystemSettings:
        """Установить значение настройки."""
        async with get_session_context() as session:
            result = await session.execute(
                select(SystemSettings).where(SystemSettings.key == key)
            )
            setting = result.scalar_one_or_none()

            str_value = self._serialize_value(value, value_type)

            if setting:
                setting.value = str_value
                setting.value_type = value_type
                if description:
                    setting.description = description
                setting.is_secret = is_secret
            else:
                setting = SystemSettings(
                    key=key,
                    value=str_value,
                    value_type=value_type,
                    description=description,
                    is_secret=is_secret,
                )
                session.add(setting)

            await session.commit()
            await session.refresh(setting)
            return setting

    async def delete(self, key: str) -> bool:
        """Удалить настройку."""
        async with get_session_context() as session:
            result = await session.execute(
                select(SystemSettings).where(SystemSettings.key == key)
            )
            setting = result.scalar_one_or_none()

            if setting:
                await session.delete(setting)
                await session.commit()
                return True
            return False

    # ==================== HELPERS ====================

    def _parse_value(self, value: Optional[str], value_type: str) -> Any:
        """Парсит значение в нужный тип."""
        if value is None:
            return None

        if value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        elif value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        elif value_type == "json":
            return json.loads(value)
        else:
            return value

    def _serialize_value(self, value: Any, value_type: str) -> str:
        """Сериализует значение в строку."""
        if value_type == "json":
            return json.dumps(value)
        elif value_type == "bool":
            return "true" if value else "false"
        else:
            return str(value)


class PromotionRepository:
    """Репозиторий для акций и скидок."""

    # ==================== GET ====================

    async def get(self, promotion_id: int) -> Optional[Promotion]:
        """Получить акцию по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Promotion).where(Promotion.id == promotion_id)
            )
            return result.scalar_one_or_none()

    async def get_all(self, active_only: bool = False) -> List[Promotion]:
        """Получить все акции."""
        async with get_session_context() as session:
            query = select(Promotion).order_by(Promotion.created_at.desc())

            if active_only:
                now = datetime.now()
                query = query.where(
                    and_(
                        Promotion.is_active == True,
                        Promotion.start_date <= now,
                        Promotion.end_date >= now,
                    )
                )

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_active_for_plan(self, plan: str) -> Optional[Promotion]:
        """Получить активную акцию для плана."""
        async with get_session_context() as session:
            now = datetime.now()
            result = await session.execute(
                select(Promotion).where(
                    and_(
                        Promotion.is_active == True,
                        Promotion.start_date <= now,
                        Promotion.end_date >= now,
                    )
                ).order_by(Promotion.value.desc())
            )
            promotions = result.scalars().all()

            for promo in promotions:
                # Проверяем применимость к плану
                if not promo.applicable_plans or plan in promo.applicable_plans:
                    # Проверяем лимит использований
                    if promo.max_uses is None or promo.current_uses < promo.max_uses:
                        return promo

            return None

    # ==================== CREATE ====================

    async def create(
        self,
        name: str,
        promo_type: str,
        value: float,
        start_date: datetime,
        end_date: datetime,
        description: Optional[str] = None,
        applicable_plans: Optional[List[str]] = None,
        max_uses: Optional[int] = None,
        min_purchase_amount: Optional[int] = None,
        banner_text: Optional[str] = None,
        show_in_subscription: bool = True,
    ) -> Promotion:
        """Создать акцию."""
        async with get_session_context() as session:
            promotion = Promotion(
                name=name,
                description=description,
                promo_type=promo_type,
                value=value,
                applicable_plans=applicable_plans or [],
                start_date=start_date,
                end_date=end_date,
                max_uses=max_uses,
                min_purchase_amount=min_purchase_amount,
                banner_text=banner_text,
                show_in_subscription=show_in_subscription,
            )
            session.add(promotion)
            await session.commit()
            await session.refresh(promotion)
            return promotion

    # ==================== UPDATE ====================

    async def update(self, promotion_id: int, **kwargs) -> Optional[Promotion]:
        """Обновить акцию."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Promotion).where(Promotion.id == promotion_id)
            )
            promotion = result.scalar_one_or_none()

            if not promotion:
                return None

            for key, value in kwargs.items():
                if hasattr(promotion, key):
                    setattr(promotion, key, value)

            await session.commit()
            await session.refresh(promotion)
            return promotion

    async def increment_uses(self, promotion_id: int) -> None:
        """Увеличить счётчик использований."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Promotion).where(Promotion.id == promotion_id)
            )
            promotion = result.scalar_one_or_none()

            if promotion:
                promotion.current_uses += 1
                await session.commit()

    async def deactivate(self, promotion_id: int) -> bool:
        """Деактивировать акцию."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Promotion).where(Promotion.id == promotion_id)
            )
            promotion = result.scalar_one_or_none()

            if promotion:
                promotion.is_active = False
                await session.commit()
                return True
            return False

    async def delete(self, promotion_id: int) -> bool:
        """Удалить акцию."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Promotion).where(Promotion.id == promotion_id)
            )
            promotion = result.scalar_one_or_none()

            if promotion:
                await session.delete(promotion)
                await session.commit()
                return True
            return False


class PaymentStatsRepository:
    """Репозиторий для статистики платежей."""

    async def get_or_create_today(self) -> PaymentStats:
        """Получить или создать статистику за сегодня."""
        async with get_session_context() as session:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            result = await session.execute(
                select(PaymentStats).where(PaymentStats.date == today)
            )
            stats = result.scalar_one_or_none()

            if not stats:
                stats = PaymentStats(date=today)
                session.add(stats)
                await session.commit()
                await session.refresh(stats)

            return stats

    async def get_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[PaymentStats]:
        """Получить статистику за период."""
        async with get_session_context() as session:
            result = await session.execute(
                select(PaymentStats).where(
                    and_(
                        PaymentStats.date >= start_date,
                        PaymentStats.date <= end_date,
                    )
                ).order_by(PaymentStats.date.asc())
            )
            return list(result.scalars().all())

    async def get_summary(self, days: int = 30) -> Dict[str, Any]:
        """Получить сводку за период."""
        async with get_session_context() as session:
            cutoff = datetime.now() - timedelta(days=days)

            result = await session.execute(
                select(
                    func.sum(PaymentStats.yookassa_amount),
                    func.sum(PaymentStats.yookassa_successful),
                    func.sum(PaymentStats.crypto_amount),
                    func.sum(PaymentStats.crypto_successful),
                    func.sum(PaymentStats.stars_amount),
                    func.sum(PaymentStats.new_subscriptions),
                    func.sum(PaymentStats.renewals),
                    func.sum(PaymentStats.promo_uses),
                    func.sum(PaymentStats.promo_discount_total),
                ).where(PaymentStats.date >= cutoff)
            )

            row = result.one()

            return {
                "yookassa_total": (row[0] or 0) / 100,  # В рублях
                "yookassa_count": row[1] or 0,
                "crypto_total": (row[2] or 0) / 100,
                "crypto_count": row[3] or 0,
                "stars_total": row[4] or 0,
                "new_subscriptions": row[5] or 0,
                "renewals": row[6] or 0,
                "promo_uses": row[7] or 0,
                "promo_discount_total": (row[8] or 0) / 100,
            }

    async def increment(self, field: str, amount: int = 1) -> None:
        """Увеличить счётчик за сегодня."""
        stats = await self.get_or_create_today()

        async with get_session_context() as session:
            result = await session.execute(
                select(PaymentStats).where(PaymentStats.id == stats.id)
            )
            stats = result.scalar_one()

            if hasattr(stats, field):
                current = getattr(stats, field) or 0
                setattr(stats, field, current + amount)
                await session.commit()


# Глобальные экземпляры
settings_repo = SettingsRepository()
promotion_repo = PromotionRepository()
payment_stats_repo = PaymentStatsRepository()


# Импорт timedelta для PaymentStatsRepository
from datetime import timedelta
