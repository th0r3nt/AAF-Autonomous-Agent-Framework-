from typing import Sequence, Any
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select
from src.l01_databases.sql.models import MentalStateEntity
from src.l00_utils.managers.logger import system_logger


class MentalStateEntityCRUD:
    def __init__(
        self,
        table: MentalStateEntity,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self.table = table
        self._session_factory = session_factory

    # ==========================================
    # 🟢 CREATE
    # ==========================================

    async def create_entity(
        self,
        name: str,
        description: str,
        category: str = "subject",
        tier: str = "medium",
        status: str = "Неизвестно",
        context: str = "[Нет]",
        related_information: dict[str, Any] = None,
    ) -> MentalStateEntity:
        """Создает новую сущность в памяти (ментальном состоянии) агента"""
        async with self._session_factory() as session:
            entity = self.table(
                name=name,
                description=description,
                category=category,
                tier=tier,
                status=status,
                context=context,
                related_information=related_information or {},
            )
            session.add(entity)
            await session.commit()
            await session.refresh(entity)
            return entity

    # ==========================================
    # 🔵 READ
    # ==========================================

    async def get_entity_by_id(self, entity_id: int) -> MentalStateEntity | None:
        """Получает сущность по ID"""
        async with self._session_factory() as session:
            return await session.get(self.table, entity_id)

    async def get_entity_by_name(self, name: str) -> MentalStateEntity | None:
        """Получает сущность по уникальному имени"""
        async with self._session_factory() as session:
            stmt = select(self.table).where(self.table.name == name)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all_entities(
        self, limit: int = 100, offset: int = 0
    ) -> Sequence[MentalStateEntity]:
        """Получает список всех сущностей с пагинацией"""
        async with self._session_factory() as session:
            stmt = select(self.table).order_by(self.table.id).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return result.scalars().all()

    # ==========================================
    # 🟡 UPDATE
    # ==========================================

    async def update_entity(self, entity_id: int, **kwargs) -> MentalStateEntity | None:
        """
        Обновляет базовые текстовые поля сущности по ID.
        """
        async with self._session_factory() as session:
            entity = await session.get(self.table, entity_id)
            if not entity:
                return None

            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)

            await session.commit()
            await session.refresh(entity)
            return entity

    async def update_related_info(
        self, entity_id: int, new_data: dict[str, Any]
    ) -> MentalStateEntity | None:
        """
        Безопасно объединяет новые данные со старым JSON-досье.
        Если ключ уже существует, он будет перезаписан. Старые ключи не удаляются.
        """
        async with self._session_factory() as session:
            entity = await session.get(self.table, entity_id)
            if not entity:
                return None

            # В SQLAlchemy для обновления JSON-колонок лучше пересоздавать словарь,
            # чтобы ORM точно заметила изменения
            current_info = entity.related_information or {}
            merged_info = {**current_info, **new_data}

            entity.related_information = merged_info

            await session.commit()
            await session.refresh(entity)
            system_logger.debug(f"[MentalState] Обновлено досье для сущности '{entity.name}'")
            return entity

    # ==========================================
    # 🔴 DELETE
    # ==========================================

    async def delete_entity(self, entity_id: int) -> bool:
        """Удаляет сущность по ID."""
        async with self._session_factory() as session:
            entity = await session.get(self.table, entity_id)
            if not entity:
                return False

            await session.delete(entity)
            await session.commit()
            return True

    # ==========================================
    # MARKDOWN
    # ==========================================

    async def get_entities_markdown(self, limit: int = 50, offset: int = 0) -> str:
        """
        Возвращает сущности в Markdown-формате.
        """
        entities = await self.get_all_entities(limit, offset)
        if not entities:
            return "Память о сущностях пуста."

        lines = []
        for e in entities:
            # Форматируем JSON досье в красивую строку
            if e.related_information:
                rel_info = "; ".join([f"{k}: {v}" for k, v in e.related_information.items()])
            else:
                rel_info = "Нет"

            lines.append(
                f"**{e.name}** (tier: {e.tier}, category: {e.category})\n"
                f"- status: {e.status}\n"
                f"- description: {e.description}\n"
                f"- context: {e.context}\n"
                f"- related_information: {rel_info}"
            )
        
        return "\n\n".join(lines)