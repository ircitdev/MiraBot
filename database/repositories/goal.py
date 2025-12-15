"""
Goal repository.
CRUD операции для целей пользователя.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session_context
from database.models import UserGoal


class GoalRepository:
    """Репозиторий для работы с целями пользователя."""

    async def create(
        self,
        user_id: int,
        original_goal: str,
        smart_goal: Optional[str] = None,
        specific: Optional[str] = None,
        measurable: Optional[str] = None,
        achievable: Optional[str] = None,
        relevant: Optional[str] = None,
        time_bound: Optional[datetime] = None,
        category: Optional[str] = None,
        reminder_frequency: Optional[str] = None,
    ) -> UserGoal:
        """Создать новую цель."""
        async with get_session_context() as session:
            goal = UserGoal(
                user_id=user_id,
                original_goal=original_goal,
                smart_goal=smart_goal,
                specific=specific,
                measurable=measurable,
                achievable=achievable,
                relevant=relevant,
                time_bound=time_bound,
                category=category,
                reminder_frequency=reminder_frequency,
            )

            # Автоматически устанавливаем next_check_in на основе reminder_frequency
            if reminder_frequency:
                goal.next_check_in = self._calculate_next_checkin(reminder_frequency)

            session.add(goal)
            await session.commit()
            await session.refresh(goal)

            return goal

    async def get(self, goal_id: int) -> Optional[UserGoal]:
        """Получить цель по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserGoal).where(UserGoal.id == goal_id)
            )
            return result.scalar_one_or_none()

    async def get_active_goals(self, user_id: int) -> List[UserGoal]:
        """Получить все активные цели пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserGoal)
                .where(
                    and_(
                        UserGoal.user_id == user_id,
                        UserGoal.status == "active"
                    )
                )
                .order_by(desc(UserGoal.created_at))
            )
            return list(result.scalars().all())

    async def get_all_goals(
        self,
        user_id: int,
        include_completed: bool = True,
        include_abandoned: bool = False,
    ) -> List[UserGoal]:
        """Получить все цели пользователя с фильтрацией."""
        async with get_session_context() as session:
            conditions = [UserGoal.user_id == user_id]

            # Фильтр по статусу
            statuses = ["active"]
            if include_completed:
                statuses.append("completed")
            if include_abandoned:
                statuses.append("abandoned")

            conditions.append(UserGoal.status.in_(statuses))

            result = await session.execute(
                select(UserGoal)
                .where(and_(*conditions))
                .order_by(desc(UserGoal.created_at))
            )
            return list(result.scalars().all())

    async def get_goals_needing_checkin(
        self,
        limit: Optional[int] = None,
    ) -> List[UserGoal]:
        """Получить цели, которым нужен check-in."""
        async with get_session_context() as session:
            query = select(UserGoal).where(
                and_(
                    UserGoal.status == "active",
                    UserGoal.next_check_in <= datetime.utcnow(),
                    UserGoal.next_check_in.isnot(None)
                )
            ).order_by(UserGoal.next_check_in)

            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_progress(
        self,
        goal_id: int,
        progress: int,
        notes: Optional[str] = None,
    ) -> Optional[UserGoal]:
        """Обновить прогресс цели."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserGoal).where(UserGoal.id == goal_id)
            )
            goal = result.scalar_one_or_none()

            if not goal:
                return None

            goal.progress = max(0, min(100, progress))  # Ограничиваем 0-100

            if notes:
                # Добавляем заметки (с timestamp)
                timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                new_note = f"[{timestamp}] {notes}"
                if goal.notes:
                    goal.notes = f"{goal.notes}\n{new_note}"
                else:
                    goal.notes = new_note

            # Если прогресс 100%, помечаем как завершенную
            if progress >= 100:
                goal.status = "completed"
                goal.completed_at = datetime.utcnow()

            goal.last_check_in = datetime.utcnow()

            # Обновляем next_check_in
            if goal.reminder_frequency and goal.status == "active":
                goal.next_check_in = self._calculate_next_checkin(goal.reminder_frequency)

            await session.commit()
            await session.refresh(goal)

            return goal

    async def update_milestone(
        self,
        goal_id: int,
        milestone_index: int,
        completed: bool,
    ) -> Optional[UserGoal]:
        """Обновить статус milestone."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserGoal).where(UserGoal.id == goal_id)
            )
            goal = result.scalar_one_or_none()

            if not goal or not goal.milestones:
                return None

            if 0 <= milestone_index < len(goal.milestones):
                goal.milestones[milestone_index]["completed"] = completed
                if completed:
                    goal.milestones[milestone_index]["completed_at"] = datetime.utcnow().isoformat()
                else:
                    goal.milestones[milestone_index]["completed_at"] = None

                # Пересчитываем прогресс на основе milestone'ов
                total = len(goal.milestones)
                completed_count = sum(1 for m in goal.milestones if m.get("completed"))
                goal.progress = int((completed_count / total) * 100)

                goal.last_check_in = datetime.utcnow()

                # Обновляем метку updated_at вручную (SQLAlchemy может не заметить изменения в JSON)
                goal.updated_at = datetime.utcnow()

                await session.commit()
                await session.refresh(goal)

            return goal

    async def mark_as_completed(self, goal_id: int) -> Optional[UserGoal]:
        """Пометить цель как завершенную."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserGoal).where(UserGoal.id == goal_id)
            )
            goal = result.scalar_one_or_none()

            if not goal:
                return None

            goal.status = "completed"
            goal.progress = 100
            goal.completed_at = datetime.utcnow()

            await session.commit()
            await session.refresh(goal)

            return goal

    async def mark_as_abandoned(
        self,
        goal_id: int,
        reason: Optional[str] = None,
    ) -> Optional[UserGoal]:
        """Пометить цель как заброшенную."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserGoal).where(UserGoal.id == goal_id)
            )
            goal = result.scalar_one_or_none()

            if not goal:
                return None

            goal.status = "abandoned"
            goal.abandoned_at = datetime.utcnow()

            if reason:
                timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                abandon_note = f"[{timestamp}] ЗАБРОШЕНА: {reason}"
                if goal.notes:
                    goal.notes = f"{goal.notes}\n{abandon_note}"
                else:
                    goal.notes = abandon_note

            await session.commit()
            await session.refresh(goal)

            return goal

    async def delete(self, goal_id: int) -> bool:
        """Удалить цель."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserGoal).where(UserGoal.id == goal_id)
            )
            goal = result.scalar_one_or_none()

            if not goal:
                return False

            await session.delete(goal)
            await session.commit()

            return True

    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику по целям пользователя."""
        async with get_session_context() as session:
            # Все цели
            all_goals = await session.execute(
                select(UserGoal).where(UserGoal.user_id == user_id)
            )
            all_goals = list(all_goals.scalars().all())

            active = [g for g in all_goals if g.status == "active"]
            completed = [g for g in all_goals if g.status == "completed"]
            abandoned = [g for g in all_goals if g.status == "abandoned"]

            # Средний прогресс активных целей
            avg_progress = (
                sum(g.progress for g in active) / len(active)
                if active else 0
            )

            # Категории
            categories = {}
            for goal in all_goals:
                if goal.category:
                    categories[goal.category] = categories.get(goal.category, 0) + 1

            return {
                "total_goals": len(all_goals),
                "active_goals": len(active),
                "completed_goals": len(completed),
                "abandoned_goals": len(abandoned),
                "average_progress": round(avg_progress, 1),
                "completion_rate": round(len(completed) / len(all_goals) * 100, 1) if all_goals else 0,
                "categories": categories,
            }

    def _calculate_next_checkin(self, frequency: str) -> datetime:
        """Вычисляет следующую дату check-in на основе частоты."""
        now = datetime.utcnow()

        if frequency == "daily":
            return now + timedelta(days=1)
        elif frequency == "weekly":
            return now + timedelta(days=7)
        elif frequency == "biweekly":
            return now + timedelta(days=14)
        else:
            # По умолчанию - раз в неделю
            return now + timedelta(days=7)
