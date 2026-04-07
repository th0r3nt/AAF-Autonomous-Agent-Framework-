import asyncio
from typing import Literal

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.base import BaseInstrument
from src.l03_interfaces.models import ToolResult
from src.l04_agency.skills.registry import skill

# Импорты графовой базы
from src.l01_databases.graph.db import GraphDB
from src.l01_databases.graph.management.crud import GraphCRUD


class GraphManager(BaseInstrument):
    """
    Фасад для работы с графовой памятью агента (KuzuDB).
    Предоставляет инструменты для сохранения строгих логических фактов,
    концептов и связей между ними.
    """

    def __init__(self, db: GraphDB):
        super().__init__()  # Регистрирует @skill в ToolRegistry

        self.graph_db = db
        self.crud = GraphCRUD(self.graph_db)

        system_logger.debug("[Graph Manager] Фасад графовой памяти успешно инициализирован.")

    # ====================================================================
    # УПРАВЛЕНИЕ КОНЦЕПТАМИ (УЗЛАМИ)
    # ====================================================================

    @skill()
    async def add_graph_concept(
        self, concept_name: str, concept_type: str, description: str = ""
    ) -> ToolResult:
        """
        Создает или обновляет узел в графовой базе данных.
        Использовать для сохранения четких фактов, личностей, технологий или объектов.
        """
        try:
            result_msg = await asyncio.to_thread(
                self.crud.add_concept, concept_name, concept_type, description
            )

            if "Ошибка" in result_msg:
                return ToolResult.fail(msg=result_msg)

            return ToolResult.ok(
                msg=f"Узел '{concept_name}' успешно сохранен в графовую память."
            )

        except Exception as e:
            system_logger.error(f"[Graph Manager] Ошибка создания концепта: {e}")
            return ToolResult.fail(msg=f"Критическая ошибка базы данных: {e}", error=str(e))

    @skill()
    async def update_graph_concept(self, concept_name: str, description: str) -> ToolResult:
        """
        Обновляет текстовое описание существующего узла в графе.
        """
        try:
            result_msg = await asyncio.to_thread(
                self.crud.update_concept_description, concept_name, description
            )

            if "Ошибка" in result_msg:
                return ToolResult.fail(msg=result_msg)

            return ToolResult.ok(msg=f"Описание узла '{concept_name}' успешно обновлено.")

        except Exception as e:
            system_logger.error(f"[Graph Manager] Ошибка обновления концепта: {e}")
            return ToolResult.fail(msg=f"Критическая ошибка базы данных: {e}", error=str(e))

    @skill()
    async def delete_graph_concept(self, concept_name: str) -> ToolResult:
        """
        Полностью удаляет узел из графа, а также все входящие и исходящие из него связи.
        """
        try:
            result_msg = await asyncio.to_thread(self.crud.delete_concept, concept_name)

            if "Ошибка" in result_msg:
                return ToolResult.fail(msg=result_msg)

            return ToolResult.ok(msg=f"Узел '{concept_name}' и все его связи удалены из памяти.")

        except Exception as e:
            system_logger.error(f"[Graph Manager] Ошибка удаления концепта: {e}")
            return ToolResult.fail(msg=f"Критическая ошибка базы данных: {e}", error=str(e))

    # ====================================================================
    # УПРАВЛЕНИЕ СВЯЗЯМИ (РЁБРАМИ)
    # ====================================================================

    @skill()
    async def add_graph_relationship(
        self, 
        source_name: str, 
        target_name: str, 
        rel_type: Literal["IS_A", "HAS_PROPERTY", "CAUSES", "REQUIRES", "RELATED_TO"], 
        context: str = ""
    ) -> ToolResult:
        """
        Создает связь между двумя существующими концептами в графе.
        """
        valid_rels = ["IS_A", "HAS_PROPERTY", "CAUSES", "REQUIRES", "RELATED_TO"]
        if rel_type not in valid_rels:
            return ToolResult.fail(
                msg=f"Ошибка: Недопустимый тип связи '{rel_type}'. Используйте только: {', '.join(valid_rels)}"
            )

        try:
            result_msg = await asyncio.to_thread(
                self.crud.add_relationship, source_name, target_name, rel_type, context
            )

            if "Ошибка" in result_msg:
                return ToolResult.fail(msg=result_msg)

            return ToolResult.ok(
                msg=f"Связь '{source_name}' -[{rel_type}]-> '{target_name}' успешно создана."
            )

        except Exception as e:
            system_logger.error(f"[Graph Manager] Ошибка создания связи: {e}")
            return ToolResult.fail(msg=f"Критическая ошибка базы данных: {e}", error=str(e))

    # ====================================================================
    # ЧТЕНИЕ
    # ====================================================================

    @skill()
    async def inspect_graph_concept(self, concept_id: str) -> ToolResult:
        """
        Позволяет прочитать информацию о конкретном узле в графе и получить все его прямые связи.
        """
        try:
            # 1. Получаем сам концепт
            concept = await asyncio.to_thread(self.crud.get_concept, concept_id)
            if not concept:
                return ToolResult.fail(msg=f"Концепт '{concept_id}' не найден в графе.")

            # 2. Получаем его связи
            neighbors = await asyncio.to_thread(self.crud.get_neighbors, concept_id, limit=20)

            concept_info = f"Концепт: {concept['id']} (Тип: {concept['type']})\nОписание: {concept['description']}"

            if neighbors:
                neighbors_str = "\nСвязи:\n" + "\n".join([f"- {n}" for n in neighbors])
            else:
                neighbors_str = "\nСвязей нет."

            return ToolResult.ok(msg=concept_info + neighbors_str, data=concept)

        except Exception as e:
            system_logger.error(f"[Graph Manager] Ошибка инспекции концепта {concept_id}: {e}")
            return ToolResult.fail(msg=f"Критическая ошибка базы данных: {e}", error=str(e))
