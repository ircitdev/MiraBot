"""
Referral Service.
Бизнес-логика реферальной программы.
"""

import secrets
from datetime import datetime, timedelta
from loguru import logger

from config.settings import settings
from database.repositories.referral import ReferralRepository
from database.repositories.subscription import SubscriptionRepository
from database.repositories.user import UserRepository


class ReferralService:
    """Сервис реферальной программы."""
    
    def __init__(self):
        self.referral_repo = ReferralRepository()
        self.subscription_repo = SubscriptionRepository()
        self.user_repo = UserRepository()
    
    async def get_or_create_code(self, user_id: int) -> str:
        """Получает или создаёт реферальный код."""
        existing = await self.referral_repo.get_code_by_user(user_id)
        
        if existing:
            return existing.code
        
        # Генерируем уникальный код
        code = secrets.token_urlsafe(6).upper()[:8]
        
        await self.referral_repo.create_code(
            user_id=user_id,
            code=code,
        )
        
        logger.info(f"Created referral code {code} for user {user_id}")
        
        return code
    
    async def apply_referral(self, new_user_id: int, code: str) -> dict:
        """Применяет реферальный код для нового пользователя."""

        referral = await self.referral_repo.get_by_code(code)

        if not referral:
            return {"success": False, "error": "Код не найден"}

        if referral.referrer_id == new_user_id:
            return {"success": False, "error": "Нельзя использовать свой код"}

        # Проверяем, не использовался ли уже
        existing = await self.referral_repo.get_by_referred(new_user_id)
        if existing:
            return {"success": False, "error": "Ты уже использовала реферальный код"}

        # Применяем бонусы
        await self._give_bonus(new_user_id, settings.REFERRAL_BONUS_DAYS)
        await self._give_bonus(referral.referrer_id, settings.REFERRAL_BONUS_DAYS)

        # Записываем реферал
        await self.referral_repo.activate(
            referral_id=referral.id,
            referred_id=new_user_id,
        )

        # Проверяем milestone
        referral_count = await self.referral_repo.count_by_referrer(referral.referrer_id)

        if referral_count == 3:
            await self._give_bonus(referral.referrer_id, settings.REFERRAL_MILESTONE_3)
            await self.user_repo.update(referral.referrer_id, special_status="guardian")
            logger.info(f"User {referral.referrer_id} reached 3 referrals milestone")

        referrer = await self.user_repo.get(referral.referrer_id)

        logger.info(f"Referral {code} activated: {referral.referrer_id} -> {new_user_id}")

        return {
            "success": True,
            "bonus_days": settings.REFERRAL_BONUS_DAYS,
            "referrer_name": referrer.display_name if referrer else None,
            "referrer_id": referral.referrer_id,  # Добавляем ID реферера для отправки уведомления
        }

    async def notify_referrer_about_friend(self, referrer_id: int, friend_name: str) -> None:
        """Отправляет уведомление рефереру о том, что его подруга начала общение."""
        try:
            from telegram import Bot
            from config.settings import settings

            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

            message = f"Я познакомилась с твоей подругой {friend_name}! Спасибо! 💛"

            # Получаем telegram_id реферера
            referrer = await self.user_repo.get(referrer_id)
            if referrer and referrer.telegram_id:
                await bot.send_message(
                    chat_id=referrer.telegram_id,
                    text=message
                )
                logger.info(f"Sent referral notification to user {referrer_id} about {friend_name}")
        except Exception as e:
            logger.error(f"Failed to send referral notification: {e}")
    
    async def _give_bonus(self, user_id: int, days: int) -> None:
        """Добавляет бонусные дни к подписке."""
        subscription = await self.subscription_repo.get_active(user_id)
        
        if subscription and subscription.plan in ["premium", "trial"]:
            # Продлеваем существующую
            await self.subscription_repo.extend_days(subscription.id, days)
        else:
            # Создаём trial
            await self.subscription_repo.create_trial(
                user_id=user_id,
                days=days,
            )
        
        logger.info(f"Gave {days} bonus days to user {user_id}")
    
    async def get_stats(self, user_id: int) -> dict:
        """Статистика рефералов пользователя."""
        code = await self.get_or_create_code(user_id)
        count = await self.referral_repo.count_by_referrer(user_id)
        
        return {
            "code": code,
            "invited_count": count,
            "bonus_earned_days": count * settings.REFERRAL_BONUS_DAYS,
            "next_milestone": 3 - count if count < 3 else None,
        }
