"""
Mood repository.
CRUD операции для записей настроения.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import MoodEntry


class MoodRepository:
    """Репозиторий для работы с записями настроения."""

    async def create(
        self,
        user_id: int,
        mood_score: int,
        primary_emotion: str,
        message_id: Optional[int] = None,
        energy_level: Optional[int] = None,
        anxiety_level: Optional[int] = None,
        secondary_emotions: Optional[List[str]] = None,
        triggers: Optional[List[str]] = None,
        context_tags: Optional[List[str]] = None,
    ) -> MoodEntry:
        """Создать запись настроения."""
        async with get_session_context() as session:
            entry = MoodEntry(
                user_id=user_id,
                message_id=message_id,
                mood_score=mood_score,
                primary_emotion=primary_emotion,
                energy_level=energy_level,
                anxiety_level=anxiety_level,
                secondary_emotions=secondary_emotions or [],
                triggers=triggers or [],
                context_tags=context_tags or [],
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)

            return entry

    async def get(self, entry_id: int) -> Optional[MoodEntry]:
        """Получить запись по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(MoodEntry).where(MoodEntry.id == entry_id)
            )
            return result.scalar_one_or_none()

    async def get_recent(
        self,
        user_id: int,
        limit: int = 10,
        days: Optional[int] = None,
    ) -> List[MoodEntry]:
        """Получить недавние записи настроения."""
        async with get_session_context() as session:
            query = select(MoodEntry).where(MoodEntry.user_id == user_id)

            if days:
                cutoff = datetime.now() - timedelta(days=days)
                query = query.where(MoodEntry.created_at >= cutoff)

            query = query.order_by(desc(MoodEntry.created_at)).limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_by_date_range(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> List[MoodEntry]:
        """Получить записи за период."""
        async with get_session_context() as session:
            result = await session.execute(
                select(MoodEntry)
                .where(
                    and_(
                        MoodEntry.user_id == user_id,
                        MoodEntry.created_at >= start_date,
                        MoodEntry.created_at <= end_date,
                    )
                )
                .order_by(desc(MoodEntry.created_at))
            )
            return list(result.scalars().all())

    async def get_average_mood(
        self,
        user_id: int,
        days: int = 7,
    ) -> Optional[float]:
        """Получить средний mood_score за период."""
        async with get_session_context() as session:
            cutoff = datetime.now() - timedelta(days=days)
            result = await session.execute(
                select(func.avg(MoodEntry.mood_score)).where(
                    and_(
                        MoodEntry.user_id == user_id,
                        MoodEntry.created_at >= cutoff,
                    )
                )
            )
            return result.scalar()

    async def get_mood_distribution(
        self,
        user_id: int,
        days: int = 30,
    ) -> Dict[str, int]:
        """Получить распределение эмоций за период."""
        async with get_session_context() as session:
            cutoff = datetime.now() - timedelta(days=days)
            result = await session.execute(
                select(
                    MoodEntry.primary_emotion,
                    func.count(MoodEntry.id).label("count")
                )
                .where(
                    and_(
                        MoodEntry.user_id == user_id,
                        MoodEntry.created_at >= cutoff,
                    )
                )
                .group_by(MoodEntry.primary_emotion)
            )

            distribution = {}
            for row in result:
                distribution[row[0]] = row[1]

            return distribution

    async def get_trigger_stats(
        self,
        user_id: int,
        days: int = 30,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Получить статистику по триггерам.
        Возвращает {trigger: {count, avg_mood}}.
        """
        entries = await self.get_recent(user_id, limit=100, days=days)

        trigger_stats = {}
        for entry in entries:
            for trigger in entry.triggers or []:
                if trigger not in trigger_stats:
                    trigger_stats[trigger] = {"count": 0, "mood_sum": 0}
                trigger_stats[trigger]["count"] += 1
                trigger_stats[trigger]["mood_sum"] += entry.mood_score

        # Вычисляем средний mood для каждого триггера
        for trigger, stats in trigger_stats.items():
            stats["avg_mood"] = round(stats["mood_sum"] / stats["count"], 1)
            del stats["mood_sum"]

        return trigger_stats

    async def get_latest(self, user_id: int) -> Optional[MoodEntry]:
        """Получить последнюю запись настроения."""
        entries = await self.get_recent(user_id, limit=1)
        return entries[0] if entries else None

    async def get_mood_summary(
        self,
        user_id: int,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Получить сводку по настроению за период.
        Используется для контекста в промптах.
        """
        entries = await self.get_recent(user_id, limit=50, days=days)

        if not entries:
            return {
                "has_data": False,
                "period_days": days,
            }

        scores = [e.mood_score for e in entries]
        emotions = [e.primary_emotion for e in entries]

        # Средний score
        avg_score = sum(scores) / len(scores)

        # Тренд
        if len(scores) >= 4:
            mid = len(scores) // 2
            first_half_avg = sum(scores[:mid]) / mid
            second_half_avg = sum(scores[mid:]) / len(scores[mid:])

            if second_half_avg > first_half_avg + 0.5:
                trend = "improving"
            elif second_half_avg < first_half_avg - 0.5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # Доминирующая эмоция
        emotion_counts = {}
        for e in emotions:
            emotion_counts[e] = emotion_counts.get(e, 0) + 1
        dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0]

        # Тревожность (если есть данные)
        anxiety_values = [e.anxiety_level for e in entries if e.anxiety_level]
        avg_anxiety = sum(anxiety_values) / len(anxiety_values) if anxiety_values else None

        # Последнее настроение
        latest = entries[0]

        return {
            "has_data": True,
            "period_days": days,
            "entries_count": len(entries),
            "average_score": round(avg_score, 1),
            "trend": trend,
            "dominant_emotion": dominant_emotion,
            "avg_anxiety": round(avg_anxiety, 1) if avg_anxiety else None,
            "latest_mood": {
                "score": latest.mood_score,
                "emotion": latest.primary_emotion,
                "when": latest.created_at,
            },
        }

    async def count_by_user(self, user_id: int) -> int:
        """Количество записей у пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(func.count(MoodEntry.id)).where(
                    MoodEntry.user_id == user_id
                )
            )
            return result.scalar() or 0

    async def delete_old(self, days: int = 90) -> int:
        """Удалить старые записи. Возвращает количество удалённых."""
        async with get_session_context() as session:
            cutoff = datetime.now() - timedelta(days=days)
            result = await session.execute(
                MoodEntry.__table__.delete().where(
                    MoodEntry.created_at < cutoff
                )
            )
            await session.commit()
            return result.rowcount
