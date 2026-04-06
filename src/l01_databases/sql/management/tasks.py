from typing import Sequence, Optional
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select
from src.l01_databases.sql.models import Task


class TaskCRUD:
    def __init__(self, table: Task, session_factory: async_sessionmaker[AsyncSession]):
        self.table = table
        self._session_factory = session_factory

    # ==========================================
    # 🟢 CREATE
    # ==========================================

    async def create_task(
        self,
        task_description: str,
        status: str = "pending",
        term: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Task:
        """Создает новую задачу для агента"""
        async with self._session_factory() as session:
            task = self.table(
                task_description=task_description, status=status, term=term, context=context
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return task

    # ==========================================
    # 🔵 READ
    # ==========================================

    async def get_task_by_id(self, task_id: int) -> Task | None:
        """Получает задачу по ID"""
        async with self._session_factory() as session:
            return await session.get(self.table, task_id)

    async def get_all_tasks(self, limit: int = 100, offset: int = 0) -> Sequence[Task]:
        """Получает список всех задач (от новых к старым)"""
        async with self._session_factory() as session:
            stmt = (
                select(self.table)
                .order_by(self.table.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_tasks_by_status(
        self, status: str, limit: int = 100, offset: int = 0
    ) -> Sequence[Task]:
        """Получает список задач по определенному статусу (например: 'pending', 'completed')"""
        async with self._session_factory() as session:
            stmt = (
                select(self.table)
                .where(self.table.status == status)
                .order_by(self.table.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    # ==========================================
    # 🟡 UPDATE
    # ==========================================

    async def update_task(self, task_id: int, **kwargs) -> Task | None:
        """
        Обновляет поля задачи по ID.
        Например: update_task(1, status="completed", context="Выполнено успешно")
        """
        async with self._session_factory() as session:
            task = await session.get(self.table, task_id)
            if not task:
                return None

            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)

            await session.commit()
            await session.refresh(task)
            return task

    # ==========================================
    # 🔴 DELETE
    # ==========================================

    async def delete_task(self, task_id: int) -> bool:
        """Удаляет задачу по ID."""
        async with self._session_factory() as session:
            task = await session.get(self.table, task_id)
            if not task:
                return False

            await session.delete(task)
            await session.commit()
            return True

    # ==========================================
    # MARKDOWN
    # ==========================================

    async def get_tasks_markdown(self, status: Optional[str] = None, limit: int = 50) -> str:
        """
        Возвращает список задач в формате Markdown.
        Если передан status, фильтрует по нему.
        """
        if status:
            tasks = await self.get_tasks_by_status(status, limit)
        else:
            tasks = await self.get_all_tasks(limit)

        if not tasks:
            return "Список задач пуст."

        lines = []
        for t in tasks:
            term_str = f" (Срок: {t.term})" if t.term else ""
            ctx_str = f"\n  Контекст/Прогресс: {t.context}" if t.context else ""
            lines.append(f"- [ID: {t.id}] [Статус: {t.status}]{term_str} {t.task_description}{ctx_str}")

        return "\n".join(lines)