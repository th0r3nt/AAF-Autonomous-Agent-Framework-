from typing import Sequence
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select
from src.l01_databases.sql.models import PersonalityTrait


class PersonalityTraitCRUD:
    def __init__(
        self, table: PersonalityTrait, session_factory: async_sessionmaker[AsyncSession]
    ):
        self.table = table
        self._session_factory = session_factory

    # ==========================================
    # 🟢 CREATE
    # ==========================================

    async def create_trait(self, trait: str, reason: str) -> PersonalityTrait:
        """Создает новую черту характера / правило для агента"""
        async with self._session_factory() as session:
            personality_trait = self.table(trait=trait, reason=reason)
            session.add(personality_trait)
            await session.commit()
            await session.refresh(personality_trait)
            return personality_trait

    # ==========================================
    # 🔵 READ
    # ==========================================

    async def get_trait_by_id(self, trait_id: int) -> PersonalityTrait | None:
        """Получает черту характера по ID"""
        async with self._session_factory() as session:
            return await session.get(self.table, trait_id)

    async def get_all_traits(
        self, limit: int = 100, offset: int = 0
    ) -> Sequence[PersonalityTrait]:
        """Получает список всех черт характера (отсортированных от новых к старым)"""
        async with self._session_factory() as session:
            stmt = (
                select(self.table)
                .order_by(self.table.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    # ==========================================
    # 🟡 UPDATE
    # ==========================================

    async def update_trait(self, trait_id: int, **kwargs) -> PersonalityTrait | None:
        """
        Обновляет поля черты характера по ID.
        Например: update_trait(1, trait="Новое правило", reason="Новая причина")
        """
        async with self._session_factory() as session:
            trait = await session.get(self.table, trait_id)
            if not trait:
                return None

            for key, value in kwargs.items():
                if hasattr(trait, key):
                    setattr(trait, key, value)

            await session.commit()
            await session.refresh(trait)
            return trait

    # ==========================================
    # 🔴 DELETE
    # ==========================================

    async def delete_trait(self, trait_id: int) -> bool:
        """Удаляет черту характера по ID."""
        async with self._session_factory() as session:
            trait = await session.get(self.table, trait_id)
            if not trait:
                return False

            await session.delete(trait)
            await session.commit()
            return True

    # ==========================================
    # MARKDOWN
    # ==========================================

    async def get_all_traits_markdown(self, limit: int = 100, offset: int = 0) -> str:
        """
        Получает все черты характера и возвращает их в виде отформатированного Markdown-текста.
        """
        traits = await self.get_all_traits(limit, offset)
        if not traits:
            return "Приобретенных черт характера пока нет."

        lines = []
        for t in traits:
            # Делаем список маркированным, чтобы LLM было проще парсить
            lines.append(f"- Черта: {t.trait}\n  Причина: {t.reason}")
        
        return "\n\n".join(lines)