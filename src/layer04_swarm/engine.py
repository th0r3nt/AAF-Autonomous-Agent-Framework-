import inspect 
import openai
import json
import asyncio
from src.layer00_utils.config_manager import config
from src.layer03_brain.llm.client import client_openai, key_manager

from src.layer03_brain.agent.engine.react import _rescue_json 

# Импортируем НОВЫЕ глобальные переменные
from src.layer03_brain.agent.skills.registry import skills_registry, openai_tools, l0_manifest
from src.layer04_swarm.tools.system_tools import system_tools_registry, system_tools_l0_manifest

SYBAGENT_MODEL = config.swarm.sybagent_model
MAX_SYBAGENT_STEPS = config.swarm.max_sybagent_steps

async def _execute_tool(subagent, tool_call):
    """Изолированная функция для выполнения навыка через единый роутер (execute_skill) для субагентов."""
    func_name = tool_call.function.name
    
    if func_name != "execute_skill":
        subagent.add_log(f"Перехвачена галлюцинация LLM: попытка прямого вызова {func_name}.")
        return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": "System Error: Прямой вызов запрещен. Необходимо использовать 'execute_skill'."}

    # 1. Читаем и СПАСАЕМ кривой JSON от Flash-Lite
    try:
        raw_args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as original_error:
        try:
            raw_args = _rescue_json(tool_call.function.arguments)
        except Exception:
            return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": f"JSONDecodeError: Ошибка парсера: {original_error}"}

    # 2. ПРАВИЛЬНАЯ РАСПАКОВКА по новой L2-схеме
    skill_uri = raw_args.get("skill_uri")
    args = raw_args.get("kwargs", {})

    # 1. Если модель сделала двойное вложение {"kwargs": {"kwargs": {"query": "..."}}}
    if isinstance(args, dict) and "kwargs" in args and isinstance(args["kwargs"], dict):
        args = args["kwargs"]
        
    # 2. Если модель засунула аргументы в корень JSON, проигнорировав объект 'kwargs'
    elif not args and len(raw_args) > 1:
        args = {k: v for k, v in raw_args.items() if k not in ["skill_uri", "kwargs"]}

    if not skill_uri:
        return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": "System Error: Отсутствует 'skill_uri'."}

    subagent.add_log(f"Вызов L2 инструмента: {skill_uri}")


    # ==============================================================
    # 3. Системные инструменты субагента (им нужен объект subagent)

    if skill_uri in system_tools_registry:
        target_func = system_tools_registry[skill_uri]
        
        # МАГИЯ АВТО-КАСТА ТИПОВ
        try:
            sig = inspect.signature(target_func)
            for param_name, param in sig.parameters.items():
                if param_name in args:
                    val = args[param_name]
                    if param.annotation is int and isinstance(val, str) and val.strip().lstrip('-').isdigit():
                        args[param_name] = int(val)
                    elif param.annotation is bool and isinstance(val, str):
                        args[param_name] = val.lower() in ['true', '1', 'yes']
        except Exception:
            pass

        try:
            result = await target_func(subagent, **args) # Передаем починенные **args
            return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": str(result)}
        except Exception as e:
            subagent.add_log(f"Ошибка в {skill_uri}: {e}")
            return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": f"TypeError: {e}"}


    # ==============================================================
    # 4. Обычные инструменты (из глобального реестра)

    if skill_uri in skills_registry:
        short_name = skill_uri.split("/")[-1]
        if short_name not in subagent.allowed_tools:
             return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": f"System Error: Навык '{skill_uri}' запрещен для твоей роли."}
             
        target_func = skills_registry[skill_uri]

        # МАГИЯ АВТО-КАСТА ТИПОВ
        try:
            sig = inspect.signature(target_func)
            for param_name, param in sig.parameters.items():
                if param_name in args:
                    val = args[param_name]
                    if param.annotation is int and isinstance(val, str) and val.strip().lstrip('-').isdigit():
                        args[param_name] = int(val)
                    elif param.annotation is bool and isinstance(val, str):
                        args[param_name] = val.lower() in['true', '1', 'yes']
        except Exception:
            pass

        try:
            if asyncio.iscoroutinefunction(target_func):
                result = await target_func(**args)
            else:
                result = await asyncio.to_thread(target_func, **args)
            
            result_str = str(result)
            if len(result_str) > 80000:
                result_str = result_str[:80000] + "... [ОБРЕЗАНО]"
            return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": result_str}
            
        except TypeError as e:
            subagent.add_log(f"Ошибка типов в {skill_uri}: {e}")
            return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": f"TypeError (Неверные параметры): {e}"}
        except Exception as e:
            subagent.add_log(f"Критическая ошибка в {skill_uri}: {e}")
            return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": f"Error: {e}"}

    return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": f"System Error: Навык '{skill_uri}' не найден."}

def _build_subagent_l0_manifest(allowed_tools: list) -> str:
    """Динамически собирает L0 справочник только из РАЗРЕШЕННЫХ субагенту инструментов"""
    lines =[
        "## L0 SKILL LIBRARY (Доступные инструменты)",
        "ЕДИНСТВЕННЫЙ способ взаимодействия с системой — вызов инструмента `execute_skill(skill_uri, **kwargs)`.",
        "ВАЖНО: Когда ты выполнил свою задачу (например, сохранил отчет в файл), просто верни финальный текстовый ответ без вызова инструментов. Это завершит твою работу.",
        ""
    ]
    
    # 1. Добавляем системные тулзы (Делегирование, Эскалация, Тревога)
    lines.append("[SYSTEM (Swarm)]")
    for sig in system_tools_l0_manifest:
        lines.append(sig)
    lines.append("")
    
    # 2. Добавляем разрешенные глобальные тулзы
    for category, skills in l0_manifest.items():
        category_skills = []
        for skill in skills:
            # Ищем, разрешен ли этот скилл (по короткому имени)
            for allowed in allowed_tools:
                # В сигнатуре навык записан как `aaf://category/allowed_name(...)`
                if f"/{allowed}(" in skill:
                    category_skills.append(skill)
                    break
        
        if category_skills:
            lines.append(f"[{category.upper()}]")
            for skill in category_skills:
                lines.append(skill)
            lines.append("")
            
    return "\n".join(lines).strip()

async def run_subagent_react(subagent, task_query: str) -> str:
    """ReAct цикл для субагентов"""
    
    # Собираем микро-манифест
    subagent_l0_manifest = _build_subagent_l0_manifest(subagent.allowed_tools)
    
    # Вшиваем манифест прямо в конец system_prompt субагента
    full_system_prompt = f"{subagent.system_prompt}\n\n{subagent_l0_manifest}"

    messages = [
        {"role": "system", "content": full_system_prompt},
        {"role": "user", "content": task_query}
    ]

    steps = 0
    while steps < MAX_SYBAGENT_STEPS:
        steps += 1
        
        response = None
        # Даем субагенту 3 попытки пробить лимиты API
        for attempt in range(3):
            client_openai.api_key = await key_manager.get_next_key()
            try:
                response = await client_openai.chat.completions.create(
                    model=SYBAGENT_MODEL,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto"
                )
                break # Запрос прошел успешно!
                
            except openai.RateLimitError:
                wait_time = 5 + (attempt * 5) # 5s, 10s, 15s...
                subagent.add_log(f"Пойман 429 Rate Limit. (Попытка {attempt+1}/3)...")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                subagent.add_log(f"Критическая ошибка API: {e}")
                return f"Субагент упал с ошибкой API: {e}"

        if not response:
            return "Субагент умер: превышен лимит попыток достучаться до API (Rate Limit 429)."

        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or "Пустой ответ от субагента."

        messages.append(msg)

        tasks = [_execute_tool(subagent, tc) for tc in msg.tool_calls]
        results = await asyncio.gather(*tasks)
        messages.extend(results)

        if getattr(subagent, 'is_delegated', False) or getattr(subagent, 'is_escalated', False):
            return "Цикл прерван системно (эстафета или эскалация)."

    return "Превышен лимит шагов ReAct. Субагент принудительно остановлен."