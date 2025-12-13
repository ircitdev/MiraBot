"""
YooKassa Payment Service.
Интеграция с платёжной системой ЮKassa.
"""

import uuid
from typing import Optional
from datetime import datetime, timedelta
from loguru import logger

from config.settings import settings
from database.repositories.payment import PaymentRepository
from database.repositories.subscription import SubscriptionRepository
from database.repositories.user import UserRepository


class YooKassaService:
    """Сервис для работы с ЮKassa."""
    
    PLANS = {
        "monthly": {
            "amount": settings.PRICE_MONTHLY,
            "description": "Подписка Mira Premium — 1 месяц",
            "duration_days": 30,
        },
        "quarterly": {
            "amount": settings.PRICE_QUARTERLY,
            "description": "Подписка Mira Premium — 3 месяца",
            "duration_days": 90,
        },
        "yearly": {
            "amount": settings.PRICE_YEARLY,
            "description": "Подписка Mira Premium — 1 год",
            "duration_days": 365,
        },
    }
    
    def __init__(self):
        self.payment_repo = PaymentRepository()
        self.subscription_repo = SubscriptionRepository()
        self.user_repo = UserRepository()
        
        # Инициализируем SDK только если есть ключи
        if settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY:
            try:
                from yookassa import Configuration
                Configuration.account_id = settings.YOOKASSA_SHOP_ID
                Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
                self._configured = True
            except ImportError:
                logger.warning("yookassa package not installed")
                self._configured = False
        else:
            self._configured = False
            logger.warning("YooKassa not configured - missing credentials")
    
    async def create_payment(
        self,
        user_id: int,
        plan: str,
        save_payment_method: bool = False,
        return_url: Optional[str] = None,
    ) -> dict:
        """
        Создаёт платёж в ЮKassa.
        
        Args:
            user_id: ID пользователя
            plan: Код плана (monthly, quarterly, yearly)
            save_payment_method: Сохранять ли метод для автоплатежей
            return_url: URL возврата после оплаты
        
        Returns:
            {
                "payment_id": int,
                "yookassa_id": str,
                "confirmation_url": str,
                "status": str
            }
        """
        if not self._configured:
            # Для тестирования без ЮKassa
            return await self._create_test_payment(user_id, plan)
        
        if plan not in self.PLANS:
            raise ValueError(f"Неизвестный план: {plan}")
        
        plan_info = self.PLANS[plan]
        user = await self.user_repo.get(user_id)
        
        from yookassa import Payment as YooPayment
        from yookassa.domain.common import ConfirmationType
        
        idempotence_key = str(uuid.uuid4())
        
        payment_data = {
            "amount": {
                "value": str(plan_info["amount"]),
                "currency": "RUB"
            },
            "confirmation": {
                "type": ConfirmationType.REDIRECT,
                "return_url": return_url or settings.YOOKASSA_RETURN_URL,
            },
            "capture": True,
            "description": plan_info["description"],
            "metadata": {
                "user_id": user_id,
                "telegram_id": user.telegram_id,
                "plan": plan,
            },
        }
        
        if save_payment_method:
            payment_data["save_payment_method"] = True
        
        # Создаём платёж в ЮKassa
        yoo_payment = YooPayment.create(payment_data, idempotence_key)
        
        # Сохраняем в БД
        db_payment = await self.payment_repo.create(
            user_id=user_id,
            yookassa_payment_id=yoo_payment.id,
            yookassa_status=yoo_payment.status,
            amount=int(plan_info["amount"] * 100),  # в копейках
            plan=plan,
            description=plan_info["description"],
            is_recurring=save_payment_method,
        )
        
        logger.info(f"Created payment {yoo_payment.id} for user {user_id}, plan={plan}")
        
        return {
            "payment_id": db_payment.id,
            "yookassa_id": yoo_payment.id,
            "confirmation_url": yoo_payment.confirmation.confirmation_url,
            "status": yoo_payment.status,
        }
    
    async def _create_test_payment(self, user_id: int, plan: str) -> dict:
        """Создаёт тестовый платёж (без реальной ЮKassa)."""
        
        plan_info = self.PLANS[plan]
        
        # Сохраняем в БД
        db_payment = await self.payment_repo.create(
            user_id=user_id,
            yookassa_payment_id=f"test_{uuid.uuid4().hex[:8]}",
            yookassa_status="pending",
            amount=int(plan_info["amount"] * 100),
            plan=plan,
            description=plan_info["description"],
            is_recurring=False,
        )
        
        # Сразу "подтверждаем" тестовый платёж
        await self._handle_successful_payment_internal(user_id, db_payment.id, plan)
        
        logger.info(f"Created TEST payment for user {user_id}, plan={plan}")
        
        return {
            "payment_id": db_payment.id,
            "yookassa_id": db_payment.yookassa_payment_id,
            "confirmation_url": settings.YOOKASSA_RETURN_URL,  # Просто вернём в бота
            "status": "succeeded",
        }
    
    async def process_webhook(self, body: dict) -> dict:
        """Обрабатывает webhook от ЮKassa."""
        
        if not self._configured:
            return {"status": "ok", "note": "test mode"}
        
        from yookassa.domain.notification import WebhookNotification
        
        notification = WebhookNotification(body)
        payment = notification.object
        
        # Получаем наш платёж
        db_payment = await self.payment_repo.get_by_yookassa_id(payment.id)
        
        if not db_payment:
            logger.warning(f"Payment not found: {payment.id}")
            return {"error": "Payment not found"}
        
        # Обновляем статус
        await self.payment_repo.update(
            db_payment.id,
            yookassa_status=payment.status,
            payment_method_type=payment.payment_method.type if payment.payment_method else None,
            payment_method_id=payment.payment_method.id if payment.payment_method and payment.payment_method.saved else None,
        )
        
        # Обрабатываем успешный платёж
        if payment.status == "succeeded":
            await self._handle_successful_payment(db_payment, payment)
        
        elif payment.status == "canceled":
            await self._handle_canceled_payment(db_payment)
        
        return {"status": "ok"}
    
    async def _handle_successful_payment(self, db_payment, yoo_payment) -> None:
        """Обрабатывает успешный платёж."""
        
        plan_info = self.PLANS[db_payment.plan]
        
        await self._handle_successful_payment_internal(
            db_payment.user_id,
            db_payment.id,
            db_payment.plan,
            payment_method_id=yoo_payment.payment_method.id if yoo_payment.payment_method and yoo_payment.payment_method.saved else None,
        )
    
    async def _handle_successful_payment_internal(
        self,
        user_id: int,
        payment_id: int,
        plan: str,
        payment_method_id: Optional[str] = None,
    ) -> None:
        """Внутренняя обработка успешного платежа."""
        
        plan_info = self.PLANS[plan]
        
        # Активируем/продлеваем подписку
        subscription = await self.subscription_repo.get_active(user_id)
        
        if subscription and subscription.plan in ["premium", "trial"]:
            # Продлеваем существующую
            await self.subscription_repo.extend_days(
                subscription.id,
                plan_info["duration_days"],
            )
        else:
            # Создаём новую
            subscription = await self.subscription_repo.create(
                user_id=user_id,
                plan="premium",
                duration_days=plan_info["duration_days"],
            )
        
        # Сохраняем метод оплаты для автоплатежей
        if payment_method_id:
            await self.subscription_repo.update(
                subscription.id,
                auto_renew=True,
                payment_method_id=payment_method_id,
            )
        
        # Обновляем платёж
        await self.payment_repo.update(
            payment_id,
            status="completed",
            subscription_id=subscription.id,
        )
        
        # Отправляем уведомление
        await self._notify_user_success(user_id, plan)
        
        logger.info(f"Payment completed for user {user_id}, plan={plan}")
    
    async def _handle_canceled_payment(self, db_payment) -> None:
        """Обрабатывает отменённый платёж."""
        
        await self.payment_repo.update(
            db_payment.id,
            status="failed",
        )
        
        await self._notify_user_failed(db_payment.user_id)
        
        logger.info(f"Payment canceled for user {db_payment.user_id}")
    
    async def _notify_user_success(self, user_id: int, plan: str) -> None:
        """Уведомляет пользователя об успешной оплате."""
        
        # Импортируем здесь, чтобы избежать циклических импортов
        from bot.main import application
        
        if not application:
            return
        
        user = await self.user_repo.get(user_id)
        plan_info = self.PLANS[plan]
        
        text = f"""🎉 Оплата прошла успешно!

Твоя подписка Premium активирована на {plan_info['duration_days']} дней.

Теперь тебе доступно:
• Безлимитное общение
• Полная память о наших разговорах
• Все ритуалы и проактивные сообщения
• Еженедельные рефлексии

Я рада, что ты решила остаться 💛"""
        
        try:
            await application.bot.send_message(chat_id=user.telegram_id, text=text)
        except Exception as e:
            logger.error(f"Failed to notify user {user_id} about payment: {e}")
    
    async def _notify_user_failed(self, user_id: int) -> None:
        """Уведомляет пользователя о неудачной оплате."""
        
        from bot.main import application
        
        if not application:
            return
        
        user = await self.user_repo.get(user_id)
        
        text = """К сожалению, оплата не прошла 😔

Попробуй ещё раз или выбери другой способ оплаты.
Если проблема повторяется — напиши в поддержку."""
        
        try:
            await application.bot.send_message(chat_id=user.telegram_id, text=text)
        except Exception as e:
            logger.error(f"Failed to notify user {user_id} about failed payment: {e}")
    
    async def cancel_subscription(self, user_id: int) -> bool:
        """Отменяет автоплатёж."""
        
        subscription = await self.subscription_repo.get_active(user_id)
        
        if not subscription:
            return False
        
        await self.subscription_repo.update(
            subscription.id,
            auto_renew=False,
        )
        
        logger.info(f"Auto-renew disabled for user {user_id}")
        
        return True
    
    async def get_payment_status(self, yookassa_id: str) -> Optional[dict]:
        """Получает статус платежа из ЮKassa."""
        
        if not self._configured:
            return None
        
        from yookassa import Payment as YooPayment
        
        payment = YooPayment.find_one(yookassa_id)
        
        return {
            "id": payment.id,
            "status": payment.status,
            "amount": payment.amount.value,
            "created_at": payment.created_at,
            "paid": payment.paid,
        }
