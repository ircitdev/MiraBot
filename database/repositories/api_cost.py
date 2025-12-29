"""
Репозиторий для работы с расходами на API.
"""

from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, desc
from database.models import ApiCost, User
from database.connection import get_session_context


class ApiCostRepository:
    """Репозиторий для работы с расходами на API (Claude, Yandex, OpenAI)."""

    async def create(
        self,
        user_id: int,
        provider: str,
        operation: str,
        cost_usd: float,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        characters_count: Optional[int] = None,
        audio_seconds: Optional[int] = None,
        model: Optional[str] = None,
        message_id: Optional[int] = None,
        admin_user_id: Optional[int] = None,
    ) -> ApiCost:
        """
        Создать запись о расходе на API.

        Args:
            user_id: ID пользователя
            provider: Провайдер ('claude', 'yandex_tts', 'yandex_stt', 'openai')
            operation: Операция ('chat_completion', 'text_to_speech', etc.)
            cost_usd: Стоимость в USD
            input_tokens: Входящие токены (для LLM)
            output_tokens: Выходящие токены (для LLM)
            total_tokens: Общее количество токенов
            characters_count: Количество символов (для TTS)
            audio_seconds: Количество секунд аудио (для STT)
            model: Модель API
            message_id: ID сообщения (опционально)
            admin_user_id: ID админа (опционально)

        Returns:
            Созданная запись ApiCost
        """
        async with get_session_context() as session:
            api_cost = ApiCost(
                user_id=user_id,
                provider=provider,
                operation=operation,
                cost_usd=cost_usd,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                characters_count=characters_count,
                audio_seconds=audio_seconds,
                model=model,
                message_id=message_id,
                admin_user_id=admin_user_id,
            )
            session.add(api_cost)
            await session.commit()
            await session.refresh(api_cost)
            return api_cost

    async def get_total_cost_by_user(self, user_id: int) -> float:
        """
        Получить общие расходы на API для пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Сумма расходов в USD
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(func.sum(ApiCost.cost_usd))
                .where(ApiCost.user_id == user_id)
            )
            total = result.scalar()
            return float(total) if total else 0.0

    async def get_costs_by_provider(
        self,
        user_id: int,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Получить расходы по провайдерам для пользователя.

        Args:
            user_id: ID пользователя
            from_date: Начало периода (опционально)
            to_date: Конец периода (опционально)

        Returns:
            Словарь {provider: total_cost}
        """
        async with get_session_context() as session:
            query = select(
                ApiCost.provider,
                func.sum(ApiCost.cost_usd).label('total_cost')
            ).where(ApiCost.user_id == user_id)

            if from_date:
                query = query.where(ApiCost.created_at >= from_date)
            if to_date:
                query = query.where(ApiCost.created_at <= to_date)

            query = query.group_by(ApiCost.provider)

            result = await session.execute(query)
            return {row.provider: float(row.total_cost) for row in result}

    async def get_all_users_total_costs(self) -> List[Dict]:
        """
        Получить общие расходы на API для всех пользователей.

        Returns:
            Список [{user_id, telegram_id, display_name, total_cost}, ...]
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(
                    User.id,
                    User.telegram_id,
                    User.display_name,
                    func.sum(ApiCost.cost_usd).label('total_cost')
                )
                .join(ApiCost, User.id == ApiCost.user_id)
                .group_by(User.id, User.telegram_id, User.display_name)
                .order_by(desc(func.sum(ApiCost.cost_usd)))
            )

            return [
                {
                    'user_id': row.id,
                    'telegram_id': row.telegram_id,
                    'display_name': row.display_name,
                    'total_cost': float(row.total_cost)
                }
                for row in result
            ]

    async def get_costs_by_date(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        user_id: Optional[int] = None,
        provider: Optional[str] = None
    ) -> List[Dict]:
        """
        Получить расходы по датам (для графика).

        Args:
            from_date: Начало периода (опционально)
            to_date: Конец периода (опционально)
            user_id: Фильтр по пользователю (опционально)
            provider: Фильтр по провайдеру (опционально)

        Returns:
            Список [{date, provider, total_cost, total_tokens}, ...]
        """
        async with get_session_context() as session:
            query = select(
                func.date(ApiCost.created_at).label('date'),
                ApiCost.provider,
                func.sum(ApiCost.cost_usd).label('total_cost'),
                func.sum(ApiCost.total_tokens).label('total_tokens')
            )

            conditions = []
            if from_date:
                conditions.append(ApiCost.created_at >= from_date)
            if to_date:
                conditions.append(ApiCost.created_at <= to_date)
            if user_id:
                conditions.append(ApiCost.user_id == user_id)
            if provider:
                conditions.append(ApiCost.provider == provider)

            if conditions:
                query = query.where(and_(*conditions))

            query = query.group_by(
                func.date(ApiCost.created_at),
                ApiCost.provider
            ).order_by(func.date(ApiCost.created_at), ApiCost.provider)

            result = await session.execute(query)

            return [
                {
                    'date': row.date.isoformat() if row.date else None,
                    'provider': row.provider,
                    'total_cost': float(row.total_cost),
                    'total_tokens': int(row.total_tokens) if row.total_tokens else 0
                }
                for row in result
            ]

    async def get_recent_costs(
        self,
        user_id: int,
        limit: int = 50
    ) -> List[ApiCost]:
        """
        Получить последние записи расходов для пользователя.

        Args:
            user_id: ID пользователя
            limit: Количество записей

        Returns:
            Список записей ApiCost
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(ApiCost)
                .where(ApiCost.user_id == user_id)
                .order_by(desc(ApiCost.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_stats_summary(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict:
        """
        Получить общую статистику по расходам.

        Args:
            from_date: Начало периода (опционально)
            to_date: Конец периода (опционально)

        Returns:
            Словарь со статистикой:
            {
                'total_cost': float,
                'total_tokens': int,
                'by_provider': {provider: cost, ...},
                'unique_users': int
            }
        """
        async with get_session_context() as session:
            conditions = []
            if from_date:
                conditions.append(ApiCost.created_at >= from_date)
            if to_date:
                conditions.append(ApiCost.created_at <= to_date)

            # Общая стоимость и токены
            query = select(
                func.sum(ApiCost.cost_usd).label('total_cost'),
                func.sum(ApiCost.total_tokens).label('total_tokens'),
                func.count(func.distinct(ApiCost.user_id)).label('unique_users')
            )

            if conditions:
                query = query.where(and_(*conditions))

            result = await session.execute(query)
            row = result.first()

            # По провайдерам
            provider_query = select(
                ApiCost.provider,
                func.sum(ApiCost.cost_usd).label('total_cost')
            )

            if conditions:
                provider_query = provider_query.where(and_(*conditions))

            provider_query = provider_query.group_by(ApiCost.provider)

            provider_result = await session.execute(provider_query)
            by_provider = {r.provider: float(r.total_cost) for r in provider_result}

            return {
                'total_cost': float(row.total_cost) if row.total_cost else 0.0,
                'total_tokens': int(row.total_tokens) if row.total_tokens else 0,
                'by_provider': by_provider,
                'unique_users': int(row.unique_users) if row.unique_users else 0
            }

    async def get_top_users_by_cost(
        self,
        limit: int = 10,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Получить топ пользователей по расходам на API.

        Args:
            limit: Количество пользователей
            from_date: Начало периода (опционально)
            to_date: Конец периода (опционально)

        Returns:
            Список [{user_id, telegram_id, display_name, total_cost, total_tokens}, ...]
        """
        async with get_session_context() as session:
            query = select(
                User.id,
                User.telegram_id,
                User.display_name,
                func.sum(ApiCost.cost_usd).label('total_cost'),
                func.sum(ApiCost.total_tokens).label('total_tokens')
            ).join(ApiCost, User.id == ApiCost.user_id)

            conditions = []
            if from_date:
                conditions.append(ApiCost.created_at >= from_date)
            if to_date:
                conditions.append(ApiCost.created_at <= to_date)

            if conditions:
                query = query.where(and_(*conditions))

            query = query.group_by(
                User.id, User.telegram_id, User.display_name
            ).order_by(desc(func.sum(ApiCost.cost_usd))).limit(limit)

            result = await session.execute(query)

            return [
                {
                    'user_id': row.id,
                    'telegram_id': row.telegram_id,
                    'display_name': row.display_name,
                    'total_cost': float(row.total_cost),
                    'total_tokens': int(row.total_tokens) if row.total_tokens else 0
                }
                for row in result
            ]
