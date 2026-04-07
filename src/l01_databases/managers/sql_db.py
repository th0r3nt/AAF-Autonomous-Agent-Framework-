from src.l00_utils.managers.logger import system_logger
from typing import Literal

# Импорты БД и CRUD
from src.l01_databases.sql.db import SQLDB
from src.l01_databases.sql.models import (
    Task,
    MentalStateEntity,
    PersonalityTrait,
    AgentTick,
    ScheduledEvent,
)
from src.l01_databases.sql.management.tasks import TaskCRUD
from src.l01_databases.sql.management.mental_states import MentalStateEntityCRUD
from src.l01_databases.sql.management.personality_traits import PersonalityTraitCRUD
from src.l01_databases.sql.management.agent_ticks import AgentTickCRUD
from src.l01_databases.sql.management.scheduled_events import ScheduledEventCRUD

# Для LLM-инструментов
from src.l03_interfaces.type.base import BaseInstrument
from src.l03_interfaces.models import ToolResult
from src.l04_agency.skills.registry import skill


class SQLManager(BaseInstrument):
    """
    Фасад для работы с SQL-памятью агента.
    Инициализирует все CRUD-операции и предоставляет LLM инструменты (skills)
    для управления задачами, чертами характера и досье (Mental State).
    """

    def __init__(self, db: SQLDB):
        # Инициализируем родителя, чтобы сработала регистрация @skill
        super().__init__()

        self.sql_db = db
        session_factory = self.sql_db.session_factory

        # Инициализируем все CRUD-объекты
        self.tasks = TaskCRUD(Task, session_factory)
        self.mental_states = MentalStateEntityCRUD(MentalStateEntity, session_factory)
        self.traits = PersonalityTraitCRUD(PersonalityTrait, session_factory)

        # Эти CRUD LLM не трогает напрямую, но они нужны для сборки контекста (ContextBuilder)
        self.ticks = AgentTickCRUD(AgentTick, session_factory)
        self.events = ScheduledEventCRUD(ScheduledEvent, session_factory)

        system_logger.debug("[SQL Manager] Фасад SQL-памяти успешно инициализирован.")

    # ====================================================================
    # TASKS
    # ====================================================================

    @skill()
    async def add_task(
        self, task_description: str, term: str = None, context: str = None
    ) -> ToolResult:
        """
        Добавляет новую долгосрочную задачу в список задач.
        Полезно для планирования шагов, которые нельзя выполнить за один цикл или присутствует сложная цепочка действий.
        """
        try:
            task = await self.tasks.create_task(
                task_description=task_description, term=term, context=context
            )
            system_logger.info(
                f"[SQL Manager] Добавлена новая задача (ID: {task.id}): {task_description[:50]}..."
            )
            return ToolResult.ok(
                msg=f"Задача успешно добавлена. ID: {task.id}", data={"task_id": task.id}
            )

        except Exception as e:
            system_logger.error(f"[SQL Manager] Ошибка добавления задачи: {e}")
            return ToolResult.fail(msg=f"Ошибка при создании задачи: {e}", error=str(e))

    @skill()
    async def update_task(
        self,
        task_id: int,
        status: Literal["pending", "in_progress", "completed", "cancelled", "failed"] = None,
        context: str = None,
        term: str = None,
    ) -> ToolResult:
        """
        Обновляет информацию по задаче (прогресс, статус, сроки).
        """
        kwargs = {}
        if status is not None:
            kwargs["status"] = status
        if context is not None:
            kwargs["context"] = context
        if term is not None:
            kwargs["term"] = term

        if not kwargs:
            return ToolResult.fail(msg="Не передано параметров для обновления.")

        try:
            task = await self.tasks.update_task(task_id, **kwargs)
            if task:
                system_logger.info(f"[SQL Manager] Задача {task_id} обновлена: {kwargs}")
                return ToolResult.ok(msg=f"Задача {task_id} успешно обновлена.")

            return ToolResult.fail(msg=f"Задача с ID {task_id} не найдена.")

        except Exception as e:
            system_logger.error(f"[SQL Manager] Ошибка обновления задачи {task_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при обновлении: {e}", error=str(e))

    @skill()
    async def delete_task(self, task_id: int) -> ToolResult:
        """
        Удаляет задачу из базы данных.
        """
        try:
            success = await self.tasks.delete_task(task_id)
            if success:
                system_logger.info(f"[SQL Manager] Задача {task_id} удалена.")
                return ToolResult.ok(msg=f"Задача {task_id} успешно удалена.")

            return ToolResult.fail(msg=f"Задача с ID {task_id} не найдена.")

        except Exception as e:
            system_logger.error(f"[SQL Manager] Ошибка удаления задачи {task_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при удалении: {e}", error=str(e))

    # ====================================================================
    # PERSONALITY TRAITS
    # ====================================================================

    @skill()
    async def add_personality_trait(self, trait: str, reason: str) -> ToolResult:
        """
        Добавляет новую устойчивую черту характера или правило поведения.
        Это правило будет добавлено в системный промпт навсегда.
        """
        try:
            new_trait = await self.traits.create_trait(trait=trait, reason=reason)
            system_logger.info(
                f"[SQL Manager] Добавлена новая черта характера (ID: {new_trait.id}): {trait[:50]}..."
            )
            return ToolResult.ok(
                msg=f"Успех. Новое правило '{trait[:30]}...' (ID: {new_trait.id}) успешно интегрировано в ядро.",
                data={"trait_id": new_trait.id},
            )

        except Exception as e:
            system_logger.error(f"[SQL Manager] Ошибка создания черты характера: {e}")
            return ToolResult.fail(msg=f"Ошибка при сохранении черты: {e}", error=str(e))

    @skill()
    async def delete_personality_trait(self, trait_id: int) -> ToolResult:
        """
        Удаляет черту характера или устаревшее правило поведения по ID.
        """
        try:
            success = await self.traits.delete_trait(trait_id)
            if success:
                system_logger.info(
                    f"[SQL Manager] Черта характера {trait_id} успешно удалена."
                )
                return ToolResult.ok(
                    msg=f"Черта характера с ID {trait_id} успешно удалена из системы."
                )

            return ToolResult.fail(msg=f"Черта характера с ID {trait_id} не найдена.")

        except Exception as e:
            system_logger.error(
                f"[SQL Manager] Ошибка удаления черты характера {trait_id}: {e}"
            )
            return ToolResult.fail(msg=f"Ошибка при удалении черты: {e}", error=str(e))

    # ====================================================================
    # MENTAL STATE
    # ====================================================================

    @skill()
    async def create_entity(
        self,
        name: str,
        description: str,
        category: Literal["subject", "object", "artifact", "system"] = "subject",
        tier: Literal["critical", "high", "medium", "low"] = "medium",
        status: str = "Неизвестно",
        context: str = "[Нет]",
    ) -> ToolResult:
        """
        Создает новую сущность в ментальном состоянии.
        Полезно для запоминания важных субъектов/объектов.
        """
        try:
            entity = await self.mental_states.create_entity(
                name=name,
                description=description,
                category=category,
                tier=tier,
                status=status,
                context=context,
            )
            system_logger.info(
                f"[SQL Manager] Создана сущность (ID: {entity.id}): {name} ({category})"
            )
            return ToolResult.ok(
                msg=f"Сущность '{name}' успешно создана (ID: {entity.id}).",
                data={"entity_id": entity.id},
            )

        except Exception as e:
            system_logger.error(f"[SQL Manager] Ошибка создания сущности {name}: {e}")
            return ToolResult.fail(
                msg=f"Ошибка при создании сущности (Возможно, имя не уникально): {e}",
                error=str(e),
            )

    @skill()
    async def update_entity_status(
        self,
        entity_id: int,
        status: str = None,
        context: str = None,
        tier: Literal["critical", "high", "medium", "low"] = None,
    ) -> ToolResult:
        """
        Обновляет текстовые поля сущности (status, context, tier).
        """
        kwargs = {}
        if status is not None:
            kwargs["status"] = status
        if context is not None:
            kwargs["context"] = context
        if tier is not None:
            kwargs["tier"] = tier

        if not kwargs:
            return ToolResult.fail(msg="Не передано параметров для обновления.")

        try:
            entity = await self.mental_states.update_entity(entity_id, **kwargs)
            if entity:
                system_logger.info(f"[SQL Manager] Сущность {entity_id} обновлена: {kwargs}")
                return ToolResult.ok(
                    msg=f"Статус/контекст сущности '{entity.name}' успешно обновлен."
                )

            return ToolResult.fail(msg=f"Сущность с ID {entity_id} не найдена.")

        except Exception as e:
            system_logger.error(f"[SQL Manager] Ошибка обновления сущности {entity_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при обновлении: {e}", error=str(e))

    @skill()
    async def update_entity_info(self, entity_id: int, new_data: dict) -> ToolResult:
        """
        Добавляет или обновляет информацию в гибком JSON-досье сущности (related_information).
        Словарь автоматически сольется со старым (ключи перезапишутся, новые добавятся).
        Полезно для хранения алиасов, никнеймов в разных соцсетях, предпочтений или ID.

        :param new_data: JSON-словарь (например: {"github": "octocat", "language": "python"}).
        """
        try:
            if not isinstance(new_data, dict):
                return ToolResult.fail(
                    msg="Ошибка: new_data должен быть словарем (JSON-объектом)."
                )

            entity = await self.mental_states.update_related_info(entity_id, new_data)
            if entity:
                system_logger.info(f"[SQL Manager] JSON-досье сущности {entity_id} обновлено.")
                return ToolResult.ok(
                    msg=f"Связанная информация для '{entity.name}' успешно обновлена.",
                    data={"new_data": new_data},
                )

            return ToolResult.fail(msg=f"Сущность с ID {entity_id} не найдена.")

        except Exception as e:
            system_logger.error(f"[SQL Manager] Ошибка обновления JSON-досье {entity_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при обновлении JSON-досье: {e}", error=str(e))

    @skill()
    async def delete_entity(self, entity_id: int) -> ToolResult:
        """
        Удаляет сущность из памяти.
        """
        try:
            success = await self.mental_states.delete_entity(entity_id)
            if success:
                system_logger.info(f"[SQL Manager] Сущность {entity_id} удалена.")
                return ToolResult.ok(msg=f"Сущность {entity_id} успешно удалена.")

            return ToolResult.fail(msg=f"Сущность с ID {entity_id} не найдена.")

        except Exception as e:
            system_logger.error(f"[SQL Manager] Ошибка удаления сущности {entity_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при удалении: {e}", error=str(e))
