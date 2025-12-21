"""
Promo Code Repository.
CRUD операции для промокодов.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, func, and_
from loguru import logger

from database.models import PromoCode, PromoCodeUsage, User, Subscription
from database.session import get_session_context


class PromoRepository:
    """Репозиторий для работы с промокодами."""

    # ==================== CREATE ====================

    async def create(
        self,
        code: str,
        promo_type: str,
        value: int,
        description: Optional[str] = None,
        max_uses: Optional[int] = None,
        max_uses_per_user: int = 1,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        applicable_plans: Optional[List[str]] = None,
        only_new_users: bool = False,
        only_for_user_ids: Optional[List[int]] = None,
        created_by_admin_id: Optional[int] = None,
    ) -> PromoCode:
        """
        Создаёт новый промокод.

        Args:
            code: Код (уникальный)
            promo_type: Тип ('discount_percent', 'discount_amount', 'free_days', 'free_trial')
            value: Значение (зависит от типа)
            description: Описание
            max_uses: Максимальное количество активаций
            max_uses_per_user: Макс. на одного пользователя
            valid_from: Начало действия
            valid_until: Окончание действия
            applicable_plans: К каким планам применим
            only_new_users: Только для новых пользователей
            only_for_user_ids: Только для конкретных пользователей
            created_by_admin_id: ID админа-создателя

        Returns:
            Созданный промокод
        """
        async with get_session_context() as session:
            promo = PromoCode(
                code=code.upper().strip(),
                promo_type=promo_type,
                value=value,
                description=description,
                max_uses=max_uses,
                max_uses_per_user=max_uses_per_user,
                valid_from=valid_from,
                valid_until=valid_until,
                applicable_plans=applicable_plans or [],
                only_new_users=only_new_users,
                only_for_user_ids=only_for_user_ids,
                created_by_admin_id=created_by_admin_id,
            )
            session.add(promo)
            await session.commit()
            await session.refresh(promo)
            logger.info(f"Created promo code: {promo.code} ({promo.promo_type}={promo.value})")
            return promo

    # ==================== READ ====================

    async def get_by_code(self, code: str) -> Optional[PromoCode]:
        """Получает промокод по коду."""
        async with get_session_context() as session:
            result = await session.execute(
                select(PromoCode).where(PromoCode.code == code.upper().strip())
            )
            return result.scalar_one_or_none()

    async def get_by_id(self, promo_id: int) -> Optional[PromoCode]:
        """Получает промокод по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(PromoCode).where(PromoCode.id == promo_id)
            )
            return result.scalar_one_or_none()

    async def get(self, promo_id: int):
        """Алиас для get_by_id."""
        return await self.get_by_id(promo_id)

    async def get_all(
        self,
        active_only: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[List[PromoCode], int]:
        """
        Получает список промокодов с пагинацией.

        Returns:
            (список промокодов, общее количество)
        """
        async with get_session_context() as session:
            query = select(PromoCode)
            count_query = select(func.count(PromoCode.id))

            if active_only:
                query = query.where(PromoCode.is_active == True)
                count_query = count_query.where(PromoCode.is_active == True)

            # Подсчёт
            total = (await session.execute(count_query)).scalar() or 0

            # Пагинация
            query = query.order_by(PromoCode.created_at.desc())
            query = query.offset((page - 1) * per_page).limit(per_page)

            result = await session.execute(query)
            promos = result.scalars().all()

            return list(promos), total

    async def get_user_usage_count(self, promo_code_id: int, user_id: int) -> int:
        """Считает сколько раз пользователь использовал этот промокод."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(PromoCodeUsage.id))
                .where(
                    and_(
                        PromoCodeUsage.promo_code_id == promo_code_id,
                        PromoCodeUsage.user_id == user_id,
                    )
                )
            )
            return result.scalar() or 0

    async def get_usage_stats(self, promo_code_id: int) -> Dict[str, Any]:
        """Получает статистику использования промокода."""
        async with get_session_context() as session:
            # Общее количество использований
            total_uses = (await session.execute(
                select(func.count(PromoCodeUsage.id))
                .where(PromoCodeUsage.promo_code_id == promo_code_id)
            )).scalar() or 0

            # Уникальных пользователей
            unique_users = (await session.execute(
                select(func.count(func.distinct(PromoCodeUsage.user_id)))
                .where(PromoCodeUsage.promo_code_id == promo_code_id)
            )).scalar() or 0

            # Сумма скидок
            total_discount = (await session.execute(
                select(func.sum(PromoCodeUsage.discount_amount))
                .where(PromoCodeUsage.promo_code_id == promo_code_id)
            )).scalar() or 0

            # Выданных бесплатных дней
            total_free_days = (await session.execute(
                select(func.sum(PromoCodeUsage.free_days_granted))
                .where(PromoCodeUsage.promo_code_id == promo_code_id)
            )).scalar() or 0

            return {
                "total_uses": total_uses,
                "unique_users": unique_users,
                "total_discount": total_discount,
                "total_free_days": total_free_days,
            }

    async def get_usage_history(
        self,
        promo_code_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Получает историю использования промокодов.

        Args:
            promo_code_id: ID промокода (None = все)
            page: Страница
            per_page: Записей на страницу

        Returns:
            (список использований, общее количество)
        """
        async with get_session_context() as session:
            query = (
                select(PromoCodeUsage, User, PromoCode)
                .join(User, PromoCodeUsage.user_id == User.id)
                .join(PromoCode, PromoCodeUsage.promo_code_id == PromoCode.id)
            )
            count_query = select(func.count(PromoCodeUsage.id))

            if promo_code_id:
                query = query.where(PromoCodeUsage.promo_code_id == promo_code_id)
                count_query = count_query.where(PromoCodeUsage.promo_code_id == promo_code_id)

            # Подсчёт
            total = (await session.execute(count_query)).scalar() or 0

            # Пагинация
            query = query.order_by(PromoCodeUsage.created_at.desc())
            query = query.offset((page - 1) * per_page).limit(per_page)

            result = await session.execute(query)
            rows = result.all()

            usages = []
            for usage, user, promo in rows:
                usages.append({
                    "id": usage.id,
                    "promo_code": promo.code,
                    "promo_type": promo.promo_type,
                    "user_id": user.id,
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "display_name": user.display_name or user.first_name,
                    "discount_amount": usage.discount_amount,
                    "free_days_granted": usage.free_days_granted,
                    "created_at": usage.created_at.isoformat() if usage.created_at else None,
                })

            return usages, total

    # ==================== VALIDATE ====================

    async def validate(
        self,
        code: str,
        user_id: int,
        plan: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Проверяет возможность применения промокода.

        Args:
            code: Код промокода
            user_id: ID пользователя
            plan: План подписки (для проверки применимости)

        Returns:
            {
                "valid": True/False,
                "error": "Ошибка" или None,
                "promo": PromoCode или None
            }
        """
        promo = await self.get_by_code(code)

        if not promo:
            return {"valid": False, "error": "Промокод не найден", "promo": None}

        if not promo.is_active:
            return {"valid": False, "error": "Промокод неактивен", "promo": None}

        now = datetime.now()

        # Проверка срока действия
        if promo.valid_from and now < promo.valid_from:
            return {"valid": False, "error": "Промокод ещё не активен", "promo": None}

        if promo.valid_until and now > promo.valid_until:
            return {"valid": False, "error": "Срок действия промокода истёк", "promo": None}

        # Проверка лимита использований
        if promo.max_uses and promo.current_uses >= promo.max_uses:
            return {"valid": False, "error": "Промокод исчерпан", "promo": None}

        # Проверка лимита на пользователя
        user_uses = await self.get_user_usage_count(promo.id, user_id)
        if user_uses >= promo.max_uses_per_user:
            return {"valid": False, "error": "Вы уже использовали этот промокод", "promo": None}

        # Проверка применимости к плану
        if plan and promo.applicable_plans and plan not in promo.applicable_plans:
            return {"valid": False, "error": "Промокод не применим к этому плану", "promo": None}

        # Проверка на новых пользователей
        if promo.only_new_users:
            async with get_session_context() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    # Считаем "новым" пользователя зарегистрированного менее 7 дней назад
                    days_since_registration = (now - user.created_at).days
                    if days_since_registration > 7:
                        return {
                            "valid": False,
                            "error": "Промокод только для новых пользователей",
                            "promo": None,
                        }

        # Проверка на конкретных пользователей
        if promo.only_for_user_ids and user_id not in promo.only_for_user_ids:
            return {"valid": False, "error": "Промокод не предназначен для вас", "promo": None}

        return {"valid": True, "error": None, "promo": promo}

    # ==================== APPLY ====================

    async def apply(
        self,
        code: str,
        user_id: int,
        payment_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Применяет промокод.

        Args:
            code: Код промокода
            user_id: ID пользователя
            payment_id: ID платежа (для скидок)

        Returns:
            {
                "success": True/False,
                "error": "Ошибка" или None,
                "result": {
                    "type": "discount_percent" | "discount_amount" | "free_days" | "free_trial",
                    "value": число,
                    "discount_amount": сумма скидки (для discount_*),
                    "free_days": количество дней (для free_days/free_trial),
                }
            }
        """
        # Валидация
        validation = await self.validate(code, user_id)
        if not validation["valid"]:
            return {"success": False, "error": validation["error"], "result": None}

        promo = validation["promo"]
        result = {
            "type": promo.promo_type,
            "value": promo.value,
            "discount_amount": None,
            "free_days": None,
        }

        async with get_session_context() as session:
            # Создаём запись об использовании
            usage = PromoCodeUsage(
                promo_code_id=promo.id,
                user_id=user_id,
                applied_to_payment_id=payment_id,
            )

            # Обрабатываем в зависимости от типа
            if promo.promo_type == "free_days":
                # Добавляем бесплатные дни к подписке
                result["free_days"] = promo.value
                usage.free_days_granted = promo.value

                # Активируем/продлеваем Premium
                await self._grant_premium_days(session, user_id, promo.value)

            elif promo.promo_type == "free_trial":
                # Активируем trial
                result["free_days"] = promo.value
                usage.free_days_granted = promo.value

                await self._grant_trial(session, user_id, promo.value)

            elif promo.promo_type in ("discount_percent", "discount_amount"):
                # Для скидок просто записываем — применение при оплате
                result["discount_amount"] = promo.value if promo.promo_type == "discount_amount" else None

            session.add(usage)

            # Увеличиваем счётчик использований
            await session.execute(
                update(PromoCode)
                .where(PromoCode.id == promo.id)
                .values(current_uses=PromoCode.current_uses + 1)
            )

            await session.commit()

        logger.info(
            f"Applied promo code {code} for user {user_id}: "
            f"type={promo.promo_type}, value={promo.value}"
        )

        return {"success": True, "error": None, "result": result}

    async def _grant_premium_days(self, session, user_id: int, days: int) -> None:
        """Выдаёт бесплатные дни Premium."""
        result = await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        subscription = result.scalar_one_or_none()

        now = datetime.now()

        if subscription:
            # Продлеваем существующую
            if subscription.expires_at and subscription.expires_at > now:
                # Активная подписка — добавляем дни
                new_expires = subscription.expires_at + timedelta(days=days)
            else:
                # Истекшая — от текущего момента
                new_expires = now + timedelta(days=days)

            subscription.plan = "premium"
            subscription.status = "active"
            subscription.expires_at = new_expires
        else:
            # Создаём новую
            new_subscription = Subscription(
                user_id=user_id,
                plan="premium",
                status="active",
                expires_at=now + timedelta(days=days),
            )
            session.add(new_subscription)

    async def _grant_trial(self, session, user_id: int, days: int) -> None:
        """Активирует trial подписку."""
        result = await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        subscription = result.scalar_one_or_none()

        now = datetime.now()

        if subscription:
            # Если уже есть premium — не даём trial
            if subscription.plan == "premium" and subscription.status == "active":
                if subscription.expires_at and subscription.expires_at > now:
                    return  # Уже есть активный premium

            subscription.plan = "trial"
            subscription.status = "active"
            subscription.expires_at = now + timedelta(days=days)
        else:
            new_subscription = Subscription(
                user_id=user_id,
                plan="trial",
                status="active",
                expires_at=now + timedelta(days=days),
            )
            session.add(new_subscription)

    # ==================== UPDATE ====================

    async def update(
        self,
        promo_id: int,
        **kwargs,
    ) -> Optional[PromoCode]:
        """Обновляет промокод."""
        async with get_session_context() as session:
            result = await session.execute(
                select(PromoCode).where(PromoCode.id == promo_id)
            )
            promo = result.scalar_one_or_none()

            if not promo:
                return None

            for key, value in kwargs.items():
                if hasattr(promo, key):
                    setattr(promo, key, value)

            await session.commit()
            await session.refresh(promo)
            return promo

    async def deactivate(self, promo_id: int) -> bool:
        """Деактивирует промокод."""
        async with get_session_context() as session:
            result = await session.execute(
                update(PromoCode)
                .where(PromoCode.id == promo_id)
                .values(is_active=False)
            )
            await session.commit()
            return result.rowcount > 0

    async def activate(self, promo_id: int) -> bool:
        """Активирует промокод."""
        async with get_session_context() as session:
            result = await session.execute(
                update(PromoCode)
                .where(PromoCode.id == promo_id)
                .values(is_active=True)
            )
            await session.commit()
            return result.rowcount > 0

    # ==================== DELETE ====================

    async def delete(self, promo_id: int) -> bool:
        """Удаляет промокод (только если не использовался)."""
        async with get_session_context() as session:
            # Проверяем, использовался ли
            uses = (await session.execute(
                select(func.count(PromoCodeUsage.id))
                .where(PromoCodeUsage.promo_code_id == promo_id)
            )).scalar() or 0

            if uses > 0:
                logger.warning(f"Cannot delete promo {promo_id}: has {uses} usages")
                return False

            result = await session.execute(
                select(PromoCode).where(PromoCode.id == promo_id)
            )
            promo = result.scalar_one_or_none()

            if promo:
                await session.delete(promo)
                await session.commit()
                return True

            return False


# Глобальный экземпляр
promo_repo = PromoRepository()
