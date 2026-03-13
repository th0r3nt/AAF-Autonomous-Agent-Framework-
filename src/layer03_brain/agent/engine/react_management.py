from config.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog import event_driven_module, proactivity_module, thoughts_module
from src.layer00_utils._tools import token_tracker, count_tokens
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events
from src.layer01_datastate.sql_db.management.personality_parameters import get_formatted_personality
from src.layer03_brain.llm.prompt.prompt_manager import prompt_manager
from src.layer03_brain.llm.context.event_driven_context import build_event_driven_context
from src.layer03_brain.llm.context.proactivity_context import build_proactivity_context
from src.layer03_brain.llm.context.thoughts_context import build_thoughts_context
from src.layer03_brain.agent.skills.skills_configuration import openai_tools
from src.layer03_brain.agent.engine.react import run_react_loop

LLM_TEMPERATURE = config.llm.temperature

class ReActCycles:
    """Единый класс для управления всеми циклами мышления (входящие события, проактивность, интроспекция)"""

    async def _run_generic_cycle(self, cycle_name: str, module_name: str, prompt_func, context_func, *context_args, **context_kwargs):
        """Базовый метод, убирающий дублирование кода"""
        
        # Сигнал WatchDog
        await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=module_name, status="ON")

        dynamic_traits = await get_formatted_personality()

        # Сборка промпта и контекста
        system_instruction = prompt_func(dynamic_traits)
        current_context = await context_func(*context_args, **context_kwargs)
        # test_context = "None"

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": current_context}
        ]

        # Подсчет токенов для логгинга
        tokens_system = count_tokens(system_instruction)
        tokens_context = count_tokens(current_context)
        token_stats = token_tracker.add_record(cycle_name, tokens_system, tokens_context)

        system_logger.info(f"[{cycle_name}] Промпт: ~{tokens_system} токенов | Контекст: ~{tokens_context} токенов")
        system_logger.debug(f"[TokenTracker] {token_stats}")

        # Вызов ReAct цикла
        answer = await run_react_loop(messages=messages, tools=openai_tools, temperature=LLM_TEMPERATURE)
        system_logger.info(f"[{cycle_name}] Цикл завершен. Итог: {answer}")
        
        return answer

    async def respond_to_event(self, event, args, kwargs):
        """Реакция на входящее событие"""
        return await self._run_generic_cycle(
            "Event-Driven ReAct", event_driven_module, 
            prompt_manager.build_event_driven_prompt, build_event_driven_context, 
            event, args, kwargs
        )

    async def run_proactivity(self):
        """Проактивный цикл"""
        return await self._run_generic_cycle(
            "Proactivity ReAct", proactivity_module, 
            prompt_manager.build_proactivity_prompt, build_proactivity_context
        )

    async def run_thoughts(self):
        """Цикл интроспекции (мыслей)"""
        return await self._run_generic_cycle(
            "Thoughts ReAct", thoughts_module, 
            prompt_manager.build_thoughts_prompt, build_thoughts_context
        )

# Экземпляр-синглтон для импорта
react_cycles = ReActCycles()