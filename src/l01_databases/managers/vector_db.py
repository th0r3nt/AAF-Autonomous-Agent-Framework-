import asyncio

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings

from src.l03_interfaces.type.base import BaseInstrument
from src.l03_interfaces.models import ToolResult
from src.l04_agency.skills.registry import skill

# Импорты векторной базы
from src.l01_databases.vector.db import VectorDB
from src.l01_databases.vector.collections import VectorCollection
from src.l01_databases.vector.management.crud import VectorCollectionCRUD


class VectorManager(BaseInstrument):
    """
    Фасад для работы с векторной памятью агента (ChromaDB).
    Предоставляет инструменты (skills) для сохранения больших текстов, статей,
    документации и логов для их последующего семантического поиска.
    """

    def __init__(
        self,
        db: VectorDB,
        knowledge_collection: VectorCollection,
        thoughts_collection: VectorCollection,
    ):
        super().__init__()  # Регистрирует @skill в ToolRegistry

        self.vector_db = db

        self.knowledge_collection = knowledge_collection
        self.thoughts_collection = thoughts_collection

        # CRUD-операции
        similarity_threshold = settings.memory.similarity_threshold

        self.knowledge_crud = VectorCollectionCRUD(
            self.knowledge_collection, similarity_threshold
        )
        self.thoughts_crud = VectorCollectionCRUD(
            self.thoughts_collection, similarity_threshold
        )

        system_logger.debug("[Vector Manager] Фасад векторной памяти успешно инициализирован.")

    # ====================================================================
    # KNOWLEDGE (База знаний - факты, документация, внешняя инфа)
    # ====================================================================

    @skill()
    async def save_to_knowledge(self, text: str) -> ToolResult:
        """
        Сохраняет информацию в векторную базу знаний.
        Полезно для сохранения документации, статей, прочитанных новостей или больших массивов фактов.
        """
        # ChromaDB работает синхронно, поэтому выносим в отдельный поток
        try:
            result_msg = await asyncio.to_thread(self.knowledge_crud.add_new_entry, text)

            # Проверяем, вернул ли CRUD ошибку (в твоем crud.py ошибки возвращаются строкой)
            if "Ошибка" in result_msg:
                return ToolResult.fail(msg=result_msg)

            return ToolResult.ok(msg="Знание успешно интегрировано в векторную память.")

        except Exception as e:
            system_logger.error(f"[Vector Manager] Ошибка сохранения вектора знаний: {e}")
            return ToolResult.fail(msg=f"Критическая ошибка базы данных: {e}", error=str(e))

    @skill()
    async def delete_from_knowledge(self, ids: list) -> ToolResult:
        """
        Удаляет записи из векторной базы знаний по их ID.
        """
        if not ids or not isinstance(ids, list):
            return ToolResult.fail(
                msg="Ошибка: необходимо передать список (массив) ID записей для удаления."
            )

        try:
            result_msg = await asyncio.to_thread(self.knowledge_crud.delete_entries, ids)

            if "Ошибка" in result_msg:
                return ToolResult.fail(msg=result_msg)

            return ToolResult.ok(
                msg=f"Успешно удалено из базы знаний: {len(ids)} записей.",
                data={"deleted_ids": ids},
            )

        except Exception as e:
            system_logger.error(f"[Vector Manager] Ошибка удаления вектора знаний: {e}")
            return ToolResult.fail(msg=f"Критическая ошибка базы данных: {e}", error=str(e))

    # ====================================================================
    # THOUGHTS (База мыслей - выводы агента, рефлексия, опыт)
    # ====================================================================

    @skill()
    async def save_to_thoughts(self, text: str) -> ToolResult:
        """
        Сохраняет важные размышления, логические выводы или промежуточные итоги работы в векторную базу мыслей.
        В отличие от сухих фактов (knowledge), здесь хранится рефлексия и уникальный опыт.
        """
        try:
            result_msg = await asyncio.to_thread(self.thoughts_crud.add_new_entry, text)

            if "Ошибка" in result_msg:
                return ToolResult.fail(msg=result_msg)

            return ToolResult.ok(msg="Мысль/вывод успешно сохранены в векторную память.")

        except Exception as e:
            system_logger.error(f"[Vector Manager] Ошибка сохранения мысли: {e}")
            return ToolResult.fail(msg=f"Критическая ошибка базы данных: {e}", error=str(e))

    @skill()
    async def delete_from_thoughts(self, ids: list) -> ToolResult:
        """
        Удаляет записи из векторной базы мыслей по их ID.
        """
        if not ids or not isinstance(ids, list):
            return ToolResult.fail(
                msg="Ошибка: необходимо передать список (массив) ID записей для удаления."
            )

        try:
            result_msg = await asyncio.to_thread(self.thoughts_crud.delete_entries, ids)

            if "Ошибка" in result_msg:
                return ToolResult.fail(msg=result_msg)

            return ToolResult.ok(
                msg=f"Успешно удалено из базы мыслей: {len(ids)} записей.",
                data={"deleted_ids": ids},
            )

        except Exception as e:
            system_logger.error(f"[Vector Manager] Ошибка удаления мысли: {e}")
            return ToolResult.fail(msg=f"Критическая ошибка базы данных: {e}", error=str(e))
