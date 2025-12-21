"""
Program Repository.
Работа с программами пользователей.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, and_, update
from sqlalchemy.orm import selectinload
from loguru import logger

from database.session import get_session_context
from database.models import UserProgram


class ProgramRepository:
    """Репозиторий для работы с программами пользователей."""

    async def create(
        self,
        user_id: int,
        program_id: str,
        program_name: str,
        total_days: int,
        reminder_time: Optional[str] = None,
    ) -> UserProgram:
        """
        Создаёт новое участие в программе.

        Args:
            user_id: ID пользователя
            program_id: ID программы (например, "7_days_self_care")
            program_name: Название программы
            total_days: Общее количество дней
            reminder_time: Время напоминания (например, "09:00")

        Returns:
            Созданный объект UserProgram
        """
        async with get_session_context() as session:
            # Проверяем нет ли уже активной программы такого типа
            existing = await self.get_active_by_program(user_id, program_id)
            if existing:
                logger.warning(f"User {user_id} already has active program {program_id}")
                return existing

            # Вычисляем время следующего задания
            now = datetime.now()
            if reminder_time:
                hour, minute = map(int, reminder_time.split(":"))
                next_task = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_task <= now:
                    next_task += timedelta(days=1)
            else:
                # По умолчанию - завтра в 9:00
                next_task = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)

            program = UserProgram(
                user_id=user_id,
                program_id=program_id,
                program_name=program_name,
                current_day=1,
                total_days=total_days,
                status="active",
                completed_days=[],
                reminder_time=reminder_time or "09:00",
                reminder_enabled=True,
                next_task_at=next_task,
                started_at=now,
            )

            session.add(program)
            await session.commit()
            await session.refresh(program)

            logger.info(f"Created program {program_id} for user {user_id}")
            return program

    async def get(self, program_entry_id: int) -> Optional[UserProgram]:
        """Получает участие в программе по ID."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProgram).where(UserProgram.id == program_entry_id)
            )
            return result.scalar_one_or_none()

    async def get_active_by_program(self, user_id: int, program_id: str) -> Optional[UserProgram]:
        """Получает активное участие пользователя в конкретной программе."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProgram).where(
                    and_(
                        UserProgram.user_id == user_id,
                        UserProgram.program_id == program_id,
                        UserProgram.status == "active",
                    )
                )
            )
            return result.scalar_one_or_none()

    async def get_active_programs(self, user_id: int) -> List[UserProgram]:
        """Получает все активные программы пользователя."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProgram).where(
                    and_(
                        UserProgram.user_id == user_id,
                        UserProgram.status == "active",
                    )
                ).order_by(UserProgram.started_at.desc())
            )
            return list(result.scalars().all())

    async def get_all_programs(self, user_id: int) -> List[UserProgram]:
        """Получает все программы пользователя (включая завершённые)."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProgram).where(
                    UserProgram.user_id == user_id
                ).order_by(UserProgram.started_at.desc())
            )
            return list(result.scalars().all())

    async def get_programs_needing_task(self, limit: int = 50) -> List[UserProgram]:
        """
        Получает программы, которым пора отправить задание.

        Returns:
            Список программ с наступившим временем следующего задания
        """
        async with get_session_context() as session:
            now = datetime.now()
            result = await session.execute(
                select(UserProgram).where(
                    and_(
                        UserProgram.status == "active",
                        UserProgram.reminder_enabled == True,
                        UserProgram.next_task_at <= now,
                    )
                ).limit(limit)
            )
            return list(result.scalars().all())

    async def complete_day(
        self,
        program_entry_id: int,
        feedback: Optional[str] = None,
    ) -> Optional[UserProgram]:
        """
        Отмечает текущий день как выполненный.

        Args:
            program_entry_id: ID записи программы
            feedback: Отзыв пользователя о задании

        Returns:
            Обновлённый объект UserProgram или None
        """
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProgram).where(UserProgram.id == program_entry_id)
            )
            program = result.scalar_one_or_none()

            if not program:
                return None

            # Добавляем запись о выполненном дне
            completed_days = program.completed_days or []
            completed_days.append({
                "day": program.current_day,
                "completed_at": datetime.now().isoformat(),
                "feedback": feedback,
            })
            program.completed_days = completed_days

            # Проверяем завершена ли программа
            if program.current_day >= program.total_days:
                program.status = "completed"
                program.completed_at = datetime.now()
                program.next_task_at = None
                logger.info(f"Program {program.program_id} completed for user {program.user_id}")
            else:
                # Переходим к следующему дню
                program.current_day += 1

                # Планируем следующее задание
                if program.reminder_time:
                    hour, minute = map(int, program.reminder_time.split(":"))
                    next_task = datetime.now().replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    ) + timedelta(days=1)
                else:
                    next_task = datetime.now() + timedelta(days=1)

                program.next_task_at = next_task
                program.last_task_sent_at = datetime.now()

            await session.commit()
            await session.refresh(program)

            return program

    async def pause_program(self, program_entry_id: int) -> Optional[UserProgram]:
        """Приостанавливает программу."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProgram).where(UserProgram.id == program_entry_id)
            )
            program = result.scalar_one_or_none()

            if not program:
                return None

            program.status = "paused"
            program.paused_at = datetime.now()
            program.next_task_at = None

            await session.commit()
            await session.refresh(program)

            logger.info(f"Program {program.program_id} paused for user {program.user_id}")
            return program

    async def resume_program(self, program_entry_id: int) -> Optional[UserProgram]:
        """Возобновляет программу."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProgram).where(UserProgram.id == program_entry_id)
            )
            program = result.scalar_one_or_none()

            if not program or program.status != "paused":
                return None

            program.status = "active"
            program.paused_at = None

            # Планируем следующее задание
            if program.reminder_time:
                hour, minute = map(int, program.reminder_time.split(":"))
                next_task = datetime.now().replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                if next_task <= datetime.now():
                    next_task += timedelta(days=1)
            else:
                next_task = datetime.now() + timedelta(days=1)

            program.next_task_at = next_task

            await session.commit()
            await session.refresh(program)

            logger.info(f"Program {program.program_id} resumed for user {program.user_id}")
            return program

    async def abandon_program(self, program_entry_id: int) -> Optional[UserProgram]:
        """Прекращает программу досрочно."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProgram).where(UserProgram.id == program_entry_id)
            )
            program = result.scalar_one_or_none()

            if not program:
                return None

            program.status = "abandoned"
            program.next_task_at = None

            await session.commit()
            await session.refresh(program)

            logger.info(f"Program {program.program_id} abandoned by user {program.user_id}")
            return program

    async def update_reminder_time(
        self,
        program_entry_id: int,
        reminder_time: str,
    ) -> Optional[UserProgram]:
        """Обновляет время напоминания."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProgram).where(UserProgram.id == program_entry_id)
            )
            program = result.scalar_one_or_none()

            if not program:
                return None

            program.reminder_time = reminder_time

            # Пересчитываем следующее задание
            if program.status == "active":
                hour, minute = map(int, reminder_time.split(":"))
                next_task = datetime.now().replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                if next_task <= datetime.now():
                    next_task += timedelta(days=1)
                program.next_task_at = next_task

            await session.commit()
            await session.refresh(program)

            return program

    async def toggle_reminders(
        self,
        program_entry_id: int,
        enabled: bool,
    ) -> Optional[UserProgram]:
        """Включает/отключает напоминания."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProgram).where(UserProgram.id == program_entry_id)
            )
            program = result.scalar_one_or_none()

            if not program:
                return None

            program.reminder_enabled = enabled

            if not enabled:
                program.next_task_at = None

            await session.commit()
            await session.refresh(program)

            return program

    async def mark_task_sent(self, program_entry_id: int) -> None:
        """Отмечает что задание отправлено."""
        async with get_session_context() as session:
            result = await session.execute(
                select(UserProgram).where(UserProgram.id == program_entry_id)
            )
            program = result.scalar_one_or_none()

            if program:
                program.last_task_sent_at = datetime.now()
                # Следующее задание — завтра в то же время
                if program.reminder_time:
                    hour, minute = map(int, program.reminder_time.split(":"))
                    next_task = datetime.now().replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    ) + timedelta(days=1)
                else:
                    next_task = datetime.now() + timedelta(days=1)
                program.next_task_at = next_task

                await session.commit()
