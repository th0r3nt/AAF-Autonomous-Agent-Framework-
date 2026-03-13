import json
import asyncio
from config.config_manager import config
from src.layer03_brain.llm.client import client_openai, key_manager
from src.layer03_brain.agent.skills.skills_configuration import skills_registry, openai_tools
from src.layer04_swarm.tools.system_tools import system_tools_registry, system_tools_schemas

MINION_MODEL = config.swarm.minion_model
MAX_MINION_STEPS = config.swarm.max_minion_steps

async def _execute_tool(subagent, tool_call):
    func_name = tool_call.function.name
    try:
        func_args = json.loads(tool_call.function.arguments)
    except Exception as e:
        return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": f"JSON Error: {e}"}

    subagent.add_log(f"Вызов инструмента: {func_name}")

    # 1. Системные инструменты (им нужен объект subagent)
    if func_name in system_tools_registry:
        try:
            result = await system_tools_registry[func_name](subagent, **func_args)
            return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": str(result)}
        except Exception as e:
            subagent.add_log(f"Ошибка в {func_name}: {e}")
            return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": f"Error: {e}"}

    # 2. Обычные инструменты 
    if func_name in skills_registry and func_name in subagent.allowed_tools:
        try:
            if asyncio.iscoroutinefunction(skills_registry[func_name]):
                result = await skills_registry[func_name](**func_args)
            else:
                result = await asyncio.to_thread(skills_registry[func_name], **func_args)
            
            result_str = str(result)
            if len(result_str) > 80000:
                result_str = result_str[:80000] + "... [ОБРЕЗАНО]"
            return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": result_str}
        except Exception as e:
            subagent.add_log(f"Ошибка в {func_name}: {e}")
            return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": f"Error: {e}"}

    return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": "Function not found or access denied."}

async def run_subagent_react(subagent, task_query: str) -> str:
    """ReAct цикл для субагентов"""
    # Собираем схемы инструментов
    allowed_schemas = [t for t in openai_tools if t["function"]["name"] in subagent.allowed_tools]
    allowed_schemas.extend(system_tools_schemas)

    messages = [
        {"role": "system", "content": subagent.system_prompt},
        {"role": "user", "content": task_query}
    ]

    steps = 0
    while steps < MAX_MINION_STEPS:
        steps += 1
        client_openai.api_key = await key_manager.get_next_key()

        try:
            response = await client_openai.chat.completions.create(
                model=MINION_MODEL,
                messages=messages,
                tools=allowed_schemas if allowed_schemas else None,
                tool_choice="auto" if allowed_schemas else "none"
            )

            msg = response.choices[0].message

            if not msg.tool_calls:
                return msg.content or "Пустой ответ от субагента."

            messages.append(msg)

            tasks = [_execute_tool(subagent, tc) for tc in msg.tool_calls]
            results = await asyncio.gather(*tasks)
            messages.extend(results)

            # Прерывание цикла при эстафете или панике
            if getattr(subagent, 'is_delegated', False) or getattr(subagent, 'is_escalated', False):
                return "Цикл прерван системно (эстафета или эскалация)."

        except Exception as e:
            subagent.add_log(f"Критическая ошибка API: {e}")
            return f"Субагент упал с ошибкой API: {e}"

    return "Превышен лимит шагов ReAct. Субагент принудительно остановлен."