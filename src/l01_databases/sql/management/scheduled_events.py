from typing import Sequence, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select

from src.l01_databases.sql.models import ScheduledEvent


class ScheduledEventCRUD:
    def __init__(
        self, table: ScheduledEvent, session_factory: async_sessionmaker[AsyncSession]
    ):
        self.table = table
        self._session_factory = session_factory

    # ==========================================
    # 🟢 CREATE
    # ==========================================

    async def create_event(
        self,
        task_type: str,
        execution_time: datetime,
        note: str,
        cron_expression: Optional[str] = None,
    ) -> ScheduledEvent:
        async with self._session_factory() as session:
            # Убеждаемся, что время в UTC
            if execution_time.tzinfo is None:
                execution_time = execution_time.replace(tzinfo=timezone.utc)

            event = self.table(
                task_type=task_type,
                execution_time=execution_time,
                note=note,
                cron_expression=cron_expression,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            return event

    # ==========================================
    # 🔵 READ
    # ==========================================

    async def get_due_events(self, current_time: datetime) -> Sequence[ScheduledEvent]:
        """Получает все 'pending' задачи, время которых уже наступило."""
        async with self._session_factory() as session:
            stmt = select(self.table).where(
                self.table.status == "pending",
                self.table.execution_time <= current_time,
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_pending_events(self, limit: int = 20) -> Sequence[ScheduledEvent]:
        """Получает список всех запланированных задач."""
        async with self._session_factory() as session:
            stmt = (
                select(self.table)
                .where(self.table.status == "pending")
                .order_by(self.table.execution_time.asc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    # ==========================================
    # 🟡 UPDATE
    # ==========================================

    async def update_event(self, event_id: int, **kwargs) -> Optional[ScheduledEvent]:
        """Обновляет статус или время следующего выполнения."""
        async with self._session_factory() as session:
            event = await session.get(self.table, event_id)
            if not event:
                return None
            for key, value in kwargs.items():
                if hasattr(event, key):
                    setattr(event, key, value)
            await session.commit()
            await session.refresh(event)
            return event

    # ==========================================
    # 🔴 DELETE
    # ==========================================

    async def delete_event(self, event_id: int) -> bool:
        """Удаляет задачу по ID."""
        async with self._session_factory() as session:
            event = await session.get(self.table, event_id)
            if not event:
                return False

            await session.delete(event)
            await session.commit()
            return True

    # ==========================================
    # MARKDOWN
    # ==========================================

    async def get_pending_events_markdown(self, limit: int = 20) -> str:
        """
        Получает список ожидающих выполнения задач и форматирует их в Markdown.
        """
        events = await self.get_pending_events(limit)
        if not events:
            return "Календарь пуст. Таймеров и регулярных задач нет."

        lines = []
        for e in events:
            time_str = e.execution_time.strftime("%Y-%m-%d %H:%M UTC")
            cron_str = f" (Cron: {e.cron_expression})" if e.task_type == "cron" else " (Одноразовый таймер)"
            lines.append(f"- [ID: {e.id}] {time_str}{cron_str} | Примечание: {e.note}")

        return "\n".join(lines)