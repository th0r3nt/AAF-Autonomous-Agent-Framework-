import json

from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog import event_driven_module, proactivity_module, thoughts_module
from src.layer00_utils._tools import token_tracker, count_tokens

from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events
from src.layer01_datastate.sql_db.management.personality_parameters import get_formatted_personality

from src.layer03_brain.llm.prompt.prompt_manager import prompt_manager
from src.layer03_brain.llm.context.builder import build_event_driven_context, build_proactivity_context, build_thoughts_context
from src.layer03_brain.agent.skills.registry import openai_tools
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

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": current_context}
        ]

        # 1. Считаем, сколько весит текстовый L0-манифест
        l0_text = prompt_manager._get_l0_manifest_text()
        tokens_l0 = count_tokens(l0_text)

        # 2. Промпт: вычитаем L0-манифест, чтобы получить чистый вес личности и системных инструкций
        tokens_system = count_tokens(system_instruction) - tokens_l0
        
        # 3. Контекст: считаем как обычно
        tokens_context = count_tokens(current_context)
        
        # 4. Инструменты: JSON-схема (213 токенов) + текстовый L0-манифест
        tools_str = json.dumps(openai_tools, ensure_ascii=False)
        tokens_tools = count_tokens(tools_str) + tokens_l0

        # Передаем обновленные переменные в трекер
        token_stats = token_tracker.add_record(cycle_name, tokens_system, tokens_context, tokens_tools)

        system_logger.info(f"[{cycle_name}] Промпт: ~{tokens_system} | Контекст: ~{tokens_context} | Инструменты: ~{tokens_tools}")
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