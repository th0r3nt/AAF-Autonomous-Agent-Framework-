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
        system_logger.debug(f"[ContextBuilder] Начат сбор данных для цикла: {cycle_type}")
        search_query = envelope.data.get("text", envelope.source)

        settings_dict = self.state.settings_state.get_state()
        try:
            ticks_limit = settings_dict["llm"]["context_depth"][cycle_type]["number_of_ticks"]
        except KeyError:
            ticks_limit = 30

        # Параллельные запросы к базам данных
        fetch_tasks = [
            self.traits.get_all_traits_markdown(),
            self.mental_state.get_entities_markdown(10),
            self.event.get_pending_events_markdown(limit=10),
            self.task.get_tasks_markdown("pending", limit=5),
            self.tick.get_ticks_markdown(limit=ticks_limit),
            self.memory.recall_memory(search_query),
        ]
        results = await asyncio.gather(*fetch_tasks)

        personality = results[0]
        mental_state = results[1]
        calendar = results[2]
        tasks = results[3]
        recent_ticks = results[4]
        vector_graph = results[5]

        # Форматируем системную информацию и интерфейсы
        system_info = self._format_system_info()
        interfaces = self._format_interfaces()
        skills_library = self._format_skills_library(self.tools_registry.get_all_tools())
        incoming_event = self._format_incoming_event(envelope)

        system_logger.debug("[ContextBuilder] Сбор данных завершен. Формируем Markdown.")

        return f"""
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
""".strip()

    # ==========================================================================
    # ВНУТРЕННИЕ ФОРМАТТЕРЫ
    # ==========================================================================

    def _format_system_info(self) -> str:
        """Собирает лаконичную сводку о состоянии агента."""
        agency = self.state.get_state("agency")
        main_agent = agency["main_agent"]
        subagents = agency["subagents"]

        status = main_agent.get("status", "unknown")
        cycle = main_agent.get("current_cycle", "unknown")

        def format_subs(group):
            if not group:
                return "Нет активных"
            return ", ".join([f"{name} ({info['status']})" for name, info in group.items()])

        d_str = format_subs(subagents.get("daemons"))
        w_str = format_subs(subagents.get("workers"))

        return f"Status: {status} | Cycle: {cycle}\nDaemons: {d_str} | Workers: {w_str}"

    def _format_interfaces(self) -> str:
        """Собирает единый красивый блок со статусами и логами интерфейсов."""
        config = self.state.get_state("interfaces")
        lines = []

        # Маппинг активных клиентов по их атрибуту name
        active_map = {
            getattr(c, "name", type(c).__name__.lower()): c for c in self.active_clients
        }

        # Красивые имена для вывода в консоль LLM
        display_names = {
            "telegram bot": "Telegram Bot",
            "telegram userbot": "Telegram Userbot",
            "github": "GitHub",
            "habr": "Habr",
            "reddit": "Reddit",
            "email": "Email",
            "browser": "Web Browser",
            "http": "Web HTTP",
            "web search": "Web Search",
            "calendar": "Local Calendar",
            "system": "System",
            "vfs": "VFS",
        }

        for key, data in sorted(config.items()):
            d_name = display_names.get(key, key.upper())
            is_enabled = data.get("enabled", False)

            if not is_enabled:
                lines.append(f"#### [{d_name}] ⚪️ DISABLED\n")
                continue

            client = active_map.get(key)

            if not client:
                # Включен в конфиге, но класс не инициализировался (ошибка или нет ключей)
                lines.append(f"#### [{d_name}] 🔴 OFFLINE / NO KEYS\n")
                continue

            ctx = client.get_passive_context()
            status = ctx.get("status", "🟢 ONLINE")
            lines.append(f"#### [{d_name}] {status}")

            recent = ctx.get("recent_activity", [])
            if recent:
                for act in recent:
                    lines.append(f"- {act}")
            else:
                lines.append("- Нет недавней активности.")
            lines.append("")  # Пустая строка для разделения

        return "\n".join(lines).strip()

    def _format_skills_library(self, skills: list) -> str:
        if not skills:
            return "Функции не зарегистрированы."
        return "\n".join(
            [f"- `{s['id']}{s.get('signature', '()')}` - {s['description']}" for s in skills]
        )

    def _format_incoming_event(self, envelope: EventEnvelope) -> str:
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
