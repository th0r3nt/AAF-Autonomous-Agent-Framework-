import json
import asyncio
from typing import List

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.event.models import EventEnvelope

from src.l02_state.manager import GlobalState
from src.l03_interfaces.type.base import BaseClient
from src.l01_databases.managers.memory import VectorGraphMemory
from src.l01_databases.sql.management.tasks import TaskCRUD
from src.l01_databases.sql.management.scheduled_events import ScheduledEventCRUD
from src.l01_databases.sql.management.agent_ticks import AgentTickCRUD
from src.l01_databases.sql.management.mental_states import MentalStateEntityCRUD
from src.l01_databases.sql.management.personality_traits import PersonalityTraitCRUD
from src.l04_agency.skills.registry import ToolRegistry


class ContextBuilder:
    """
    Асинхронный класс. Собирает данные из баз и интерфейсов, 
    затем компилирует их в финальный Markdown для системного промпта LLM.
    """

    def __init__(
        self,
        global_state: GlobalState,
        active_clients: List[BaseClient],
        memory_manager: VectorGraphMemory,
        task_crud: TaskCRUD,
        event_crud: ScheduledEventCRUD,
        tick_crud: AgentTickCRUD,
        mental_crud: MentalStateEntityCRUD,
        traits_crud: PersonalityTraitCRUD,
        tools_registry: ToolRegistry,
    ):
        self.state = global_state
        self.active_clients = active_clients
        self.memory = memory_manager
        self.task = task_crud
        self.event = event_crud
        self.tick = tick_crud
        self.mental_state = mental_crud
        self.traits = traits_crud
        self.tools_registry = tools_registry

    async def build_context(self, envelope: EventEnvelope, cycle_type: str) -> str:
        """Главная точка входа для сбора контекста."""
        system_logger.debug(f"[ContextBuilder] Начат сбор данных для цикла: {cycle_type}")
        search_query = envelope.data.get("text", envelope.source)

        # Вытаскиваем нужную глубину контекста для текущего цикла из настроек
        settings_dict = self.state.settings_state.get_state()
        try:
            ticks_limit = settings_dict["llm"]["context_depth"][cycle_type]["number_of_ticks"]
        except KeyError:
            ticks_limit = 30  # Фолбэк на случай, если что-то пойдет не так

        # ==========================================================================
        # Параллельные запросы к базам данных
        # ==========================================================================
        fetch_tasks = [
            self.traits.get_all_traits_markdown(),              # [0] personality_traits
            self.mental_state.get_entities_markdown(10),        # [1] mental_state
            self.event.get_pending_events_markdown(limit=10),   # [2] calendar
            self.task.get_tasks_markdown("pending", limit=5),   # [3] tasks
            self.tick.get_ticks_markdown(limit=ticks_limit),    # [4] recent_ticks
            self.memory.recall_memory(search_query),            # [5] vector_graph
        ]
        results = await asyncio.gather(*fetch_tasks)

        personality = results[0]
        mental_state = results[1]
        calendar = results[2]
        tasks = results[3]
        recent_ticks = results[4]
        vector_graph = results[5]

        # ==========================================================================
        # Форматирование данных из оперативной памяти
        # ==========================================================================

        system_info = self.state.get_markdown(settings=False)
        interfaces = self._format_interfaces(self._get_interfaces_data())
        skills_library = self._format_skills_library(self.tools_registry.get_all_tools())
        incoming_event = self._format_incoming_event(envelope)

        system_logger.debug("[ContextBuilder] Сбор данных завершен. Формируем Markdown.")

        # ==========================================================================
        # Итоговая сборка
        # ==========================================================================
        result = f"""
## PERSONALITY TRAITS
{personality}

## SYSTEM INFO & STATUS
{system_info}

## INTERFACES
{interfaces}

## SKILLS LIBRARY
{skills_library}

## MENTAL STATE
{mental_state}

## CALENDAR
{calendar}

## TASKS
{tasks}

## RECENT TICKS
{recent_ticks}

## INCOMING EVENT
{incoming_event}

## VECTOR-GRAPH
{vector_graph}
"""
        return result.strip()

    # ==========================================================================
    # ВНУТРЕННИЕ ФОРМАТТЕРЫ
    # ==========================================================================

    def _format_interfaces(self, interfaces_data: dict) -> str:
        if not interfaces_data:
            return "Нет активных интерфейсов."
            
        lines = []
        for name, data in interfaces_data.items():
            status = data.get("status", "UNKNOWN")
            lines.append(f"#### [{name.upper()}] {status}")
            
            recent = data.get("recent_activity", [])
            if recent:
                for act in recent:
                    lines.append(f"- {act}")
            else:
                lines.append("- Нет недавней активности.")
                
        return "\n".join(lines)

    def _format_skills_library(self, skills: list) -> str:
        if not skills:
            return "Функции не зарегистрированы."
        return "\n".join([f"- `{s['id']}` - {s['description']}" for s in skills])

    def _format_incoming_event(self, envelope: EventEnvelope) -> str:
        # Безопасный дамп полезной нагрузки
        try:
            data_str = json.dumps(envelope.data, ensure_ascii=False, indent=2)
        except Exception:
            data_str = str(envelope.data)
            
        return (
            f"Источник: {envelope.source}\n"
            f"Событие: {envelope.routing_key}\n"
            f"Время (UTC): {envelope.timestamp_utc.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Содержание:\n```json\n{data_str}\n```"
        )

    # ==========================================================================
    # СЛУЖЕБНЫЕ МЕТОДЫ
    # ==========================================================================

    def _get_interfaces_data(self) -> dict:
        """Опрашивает локальные кэши всех живых клиентов."""
        interfaces_data = {}
        for client in self.active_clients:
            client_name = getattr(client, "name", type(client).__name__.lower())
            if hasattr(client, "get_passive_context"):
                interfaces_data[client_name] = client.get_passive_context()
        return interfaces_data