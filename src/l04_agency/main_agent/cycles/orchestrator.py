import asyncio

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.event.models import EventEnvelope
from src.l01_databases.sql.management.agent_ticks import AgentTickCRUD
from src.l02_state.manager import GlobalState
from src.l04_agency.react.loop import ReActLoop
from src.l04_agency.main_agent.prompt.builder import PromptBuilder
from src.l04_agency.main_agent.context.builder import ContextBuilder

# Универсальная схема для всех циклов
from src.l04_agency.skills.schema import ACTION_SCHEMA


class Orchestrator:
    def __init__(
        self,
        global_state: GlobalState,
        tick_crud: AgentTickCRUD,
        react_loop: ReActLoop,
        prompt_builder: PromptBuilder,
        context_builder: ContextBuilder,
    ):
        self.state = global_state
        self.tick_crud = tick_crud
        self.react_loop = react_loop

        self.prompt_builder = prompt_builder
        self.context_builder = context_builder

        self.mind_lock = asyncio.Lock()

    def is_busy(self) -> bool:
        """Позволяет Диспетчеру узнать, спит ли сейчас агент."""
        return self.mind_lock.locked()

    async def wake_up_neo(self, envelope: EventEnvelope, cycle_type: str) -> bool:
        """
        Wake Up, Agent.
        Запускает цикл мышления агента в зависимости от типа цикла.
        Event-Driven, Proactivity или Consolidation.
        """
        temperature = self.state.settings_state.get_state()["llm"]["temperature"]

        async with self.mind_lock:
            self.state.agency_state.update_main_agent("thinking", cycle_type)

            tick = await self.tick_crud.create_tick(trigger_event_id=envelope.event_id)
            system_logger.info(
                f"[Orchestrator] Запуск цикла {cycle_type.upper()}. Тик #{tick.id}."
            )

            try:
                prompt = await self.prompt_builder.build_prompt(cycle_type)
                context = await self.context_builder.build_context(envelope, cycle_type)

                # Запускаем агента в ReAct-цикл (передаем схему вызова из файла schema.py)
                result = await self.react_loop.run(
                    cycle_type=cycle_type,
                    system_prompt=prompt,
                    user_context=context,
                    tools=ACTION_SCHEMA,
                    temperature=temperature,
                    tick_id=tick.id,
                )

                # Сохраняем мысли и действия в БД для краткосрочной памяти агента
                await self.tick_crud.update_tick(
                    tick.id, 
                    status="success",
                    thoughts=result.get("thoughts", ""),
                    called_functions=result.get("called_functions", []),
                    function_results=result.get("function_results", []),
                )
                return True

            except Exception as e:
                system_logger.error(f"[Orchestrator] Ошибка цикла: {e}")
                await self.tick_crud.update_tick(
                    tick.id, status="failed", error_message=str(e)
                )
                raise e

            finally:
                self.state.agency_state.update_main_agent(
                    status="sleeping", current_cycle="none"
                )
