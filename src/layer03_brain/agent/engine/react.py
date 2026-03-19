import inspect
import json
import asyncio
import openai
import textwrap

from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer00_utils.image_tools import compress_and_encode_image
from src.layer00_utils.env_manager import AGENT_NAME

from src.layer01_datastate.sql_db.management.agent_actions import create_agent_action
from src.layer01_datastate.sql_db.management.dialogue import create_dialogue_entry

from src.layer03_brain.agent.skills.registry import skills_registry
from src.layer03_brain.llm.client import client_openai, key_manager
from src.layer03_brain.agent.engine.state import brain_state

LLM_MODEL = config.llm.model_name
MAX_REACT_STEPS = config.llm.max_react_steps

def _dump_context_to_file(messages: list):
    """Служебная функция для отладки: сохраняет финальный промпт в Markdown-файл"""
    if not config.system.flags.dump_llm_context:
        return 
    try:
        import datetime
        from pathlib import Path
        
        current_dir = Path(__file__).resolve()
        src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
        project_root = src_dir.parent if src_dir else current_dir.parents[4]
        
        # Динамический путь: Agents/{AGENT_NAME}/logs/
        log_dir = project_root / "Agents" / AGENT_NAME / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = log_dir / "latest_llm_context.md"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# ОТЛАДКА КОНТЕКСТА {config.identity.agent_name} (Обновлено: {datetime.datetime.now().strftime('%H:%M:%S')})\n\n")
            
            for msg in messages:
                if isinstance(msg, dict):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    f.write(f"### Role: {role.upper()}\n{content}\n\n---\n\n")
            
    except Exception as e:
        system_logger.error(f"Не удалось сохранить контекст для отладки: {e}")

def _rescue_json(broken_json_str: str) -> dict:
    """
    Пытается эвристически починить типичные ошибки LLM при генерации JSON.
    Если починить не удалось, пробрасывает оригинальный JSONDecodeError.
    """
    s = broken_json_str.strip()
    
    # Ошибка 1: Модель забыла закрыть финальную скобку
    if s.startswith("{") and not s.endswith("}"):
        s += "}"
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass # Не помогло, идем дальше
            
    # Ошибка 2: Модель забыла закрыть кавычку у последнего значения и скобку
    if s.startswith("{") and not s.endswith('"') and not s.endswith("}"):
        s += '"}'
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass

    # Ошибка 3: Модель засунула внутрь строки неэкранированные переносы строк (очень частая беда при генерации кода)
    try:
        # Пытаемся заменить буквальные переносы строк на экранированные \n
        # Но только если это не сломает весь JSON. Используем strict=False.
        # Для надежности используем ast.literal_eval как фоллбэк (он лучше переваривает кривые строки)
        import ast
        
        # Если JSON упал из-за переносов, literal_eval часто его спасает, 
        # если заменить true/false/null на питоновские аналоги
        py_str = broken_json_str.replace("true", "True").replace("false", "False").replace("null", "None")
        result = ast.literal_eval(py_str)
        if isinstance(result, dict):
            return result
    except Exception:
        pass

    # Если ничего не помогло, вызываем оригинальный метод, чтобы он выкинул честную ошибку
    return json.loads(broken_json_str)

async def _execute_single_tool(tool_call) -> dict:
    """Изолированная функция для выполнения навыка через единый роутер (execute_skill)."""
    func_name = tool_call.function.name
    
    if func_name != "execute_skill":
        error_msg = f"System Error: Прямой вызов функции '{func_name}' запрещен. Используй 'execute_skill'."
        return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": error_msg}

    try:
        raw_args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as original_error:
        try:
            raw_args = _rescue_json(tool_call.function.arguments)
        except Exception:
            error_msg = f"JSONDecodeError: Ошибка парсера: {original_error}"
            return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": error_msg}

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

    if skill_uri not in skills_registry:
        return {"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": f"System Error: Навык '{skill_uri}' не существует."}

    target_func = skills_registry[skill_uri]

    # АВТО КАСТ ТИПОВ
    try:
        import ast
        sig = inspect.signature(target_func)
        for param_name, param in sig.parameters.items():
            if param_name in args:
                val = args[param_name]
                
                # ЗАЩИТА ОТ ДУРАКА 4: Агент передал dict/list как строку
                if param.annotation in [dict, list] and isinstance(val, str):
                    try:
                        # Пробуем безопасно распарсить строку в объект
                        args[param_name] = ast.literal_eval(val)
                    except Exception:
                        pass # Оставляем как есть, если не вышло
                        
                # Каст для int
                elif param.annotation is int and isinstance(val, (str, float)):
                    args[param_name] = int(float(val))
                # Каст для float
                elif param.annotation is float and isinstance(val, str):
                    args[param_name] = float(val)
                # Каст для bool
                elif param.annotation is bool and isinstance(val, str):
                    args[param_name] = val.lower() in ['true', '1', 'yes']
    except Exception:
        pass

    result = None
    limit = 400

    args_str = str(args).replace('\n', '\\n')
    if len(args_str) > limit:
        args_str = args_str[:limit] + "... [Обрезано]"

    system_logger.info(f"[Agent Action] Вызов L2: {skill_uri} с аргументами {args_str}.")

    try:
        if asyncio.iscoroutinefunction(target_func):
            result = await target_func(**args)
        else:
            result = await asyncio.to_thread(target_func, **args)

        result_str = str(result).replace('\n', '\\n')
        system_logger.info(f"[Agent Action Result] {result_str[:limit] + ('...[Обрезано]' if len(result_str) > limit else '')}")

        await create_agent_action(action_type=skill_uri, details=args)

    except TypeError as e:
        error_msg = f"TypeError (Неверные параметры): {e}. Вызови 'aaf://core/get_skill_docs' (передав target_uri='{skill_uri}')."
        system_logger.warning(f"[Agent Action] Ошибка типизации в {skill_uri}: {e}")
        result = error_msg
        
    except Exception as e:
        system_logger.error(f"Системная ошибка при выполнении {skill_uri}: {e}")
        result = f"System Error executing function: {e}"

    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "name": func_name,
        "content": str(result)
    }

async def run_react_loop(messages: list, tools: list, temperature: float) -> str:
    """Вызывает ReAct цикл вызова OpenAI-совместимой модели (с параллелизмом)"""

    _dump_context_to_file(messages)

    try:
        current_steps = 0
        used_tools_history = []
        while True:
            current_steps += 1
            brain_state["step"] = current_steps
            if current_steps >= MAX_REACT_STEPS:
                answer = f"Превышен максимальный лимит ({MAX_REACT_STEPS}) по вызовам модели."
                break

            # Проверка буфера прерываний
            if brain_state["interrupt_buffer"]:
                interrupts = "\n\n".join(brain_state["interrupt_buffer"])
                brain_state["interrupt_buffer"].clear() # Очищаем буфер
                
                injection_msg = {
                    "role": "user",
                    "content": textwrap.dedent(f"""
                        [SYSTEM INTERRUPT: Входящее событие в реальном времени]
                        Во время текущего ReAct цикла в систему поступили новые данные:
                        
                        {interrupts}
                        
                        Интегрируй полученную информацию в текущий контекст. 
                        Ты имеешь право отреагировать на событие без прерывания основной цепочки действий. 
                        Скорректируй или продолжи выполнение текущего плана с учетом новых вводных.
                    """)
                }
                messages.append(injection_msg)
                system_logger.info("[BrainEngine] Контекст обновлен. В ReAct передано новое событие.")

            system_logger.info(f"[BrainEngine] Инициализирован запрос к модели {LLM_MODEL} (Шаг {current_steps}).")

            history_text = ""
            if used_tools_history:
                # Жесткая семантическая защита от повторных вызовов
                history_text = (
                    "\n\n[System: В этом цикле был проведен вызов следующих инструментов:\n" +
                    "\n".join(f"- {item}" for item in used_tools_history) +
                    "\nЕсли необходимые данные от инструментов получены - анализируй и двигайся дальше]"
                )

            step_warning = {
                "role": "user",
                "content": f"[System: Текущий шаг ReAct цикла: {current_steps}. Заверши цикл текстовым ответом 'OK', если все необходимые действия выполнены]{history_text}" 
            }
            messages.append(step_warning)
            
            # Делаем вызов к API с защитой от 429 (Rate Limit)
            response = None
            max_attempts = key_manager.total_active if key_manager.total_active > 0 else 1 
            
            for attempt in range(max_attempts):
                current_key = await key_manager.get_next_key()
                
                if current_key == "ALL_KEYS_EXHAUSTED":
                    return "Все API ключи исчерпали квоту. Ждем 12:00 МСК."

                client_openai.api_key = current_key

                try:
                    response = await client_openai.chat.completions.create(
                        model=LLM_MODEL,
                        messages=messages,
                        tools=tools,
                        reasoning_effort="high", 
                        # temperature=temperature,
                        tool_choice="auto" if tools else "none"
                    )
                    break # Успех! Выходим из цикла попыток
                    
                except openai.RateLimitError as e:
                    error_msg = str(e).lower()
                    
                    # Проверяем, дневной ли это лимит (Quota)
                    if "quota" in error_msg:
                        error_msg_log = "[CRITICAL ERROR: API ключ исчерпал дневной лимит]"
                        await create_dialogue_entry(actor="System", message=error_msg_log, source="brain_engine")
                        system_logger.error(f"[BrainEngine] Ключ исчерпал дневную квоту: {e}")
                        await key_manager.mark_key_exhausted(current_key)
                    else:
                        # Иначе это просто минутный лимит (RPM)
                        system_logger.warning("[BrainEngine] Ключ поймал минутный лимит (429 RPM).")
                    
                    # Если это была не последняя попытка и есть живые ключи
                    if attempt < max_attempts - 1 and key_manager.total_active > 0:
                        system_logger.warning(f"[BrainEngine] Переключение API-ключа. (Попытка {attempt + 2} из {max_attempts})")
                        await asyncio.sleep(5)
                    else:
                        # Если мы перебрали все ключи, и все отбили нас 429-й ошибкой (жесткий спам запросами)
                        # Возвращаем текст, чтобы ReAct цикл корректно завершился, а не упал
                        return "Система перегружена (превышен минутный лимит запросов API)."

            # Защита от падения: если цикл завершился, а ответа так и нет
            if not response:
                return "Внутренняя ошибка: Не удалось получить ответ от LLM."

            # Удаляем временное системное сообщение (о текущем шаге ReAct цикла)
            messages.pop() 

            # Получаем ответ
            response_message = response.choices[0].message

            # Если модель не вызвала никаких инструментов -> это финальный ответ
            if not response_message.tool_calls:
                answer = response_message.content if response_message.content else "Пустой ответ."
                system_logger.info(f"[BrainEngine] Нейросеть {LLM_MODEL} ответила за {current_steps} шагов. Установленный лимит: {MAX_REACT_STEPS}.")
                break

            for tc in response_message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                    # Убираем limit и offset из лога, чтобы она не думала, что с другим лимитом это "другой" запрос
                    safe_args = {k: v for k, v in args.items() if k not in ['limit', 'offset']}
                    used_tools_history.append(f"{tc.function.name} (args: {safe_args})")
                except Exception:
                    used_tools_history.append(tc.function.name)

            # Если есть вызовы функций, добавляем ответ модели в историю сообщений
            messages.append(response_message)

            # Защита от бесконечного цикла моделей Gemini
            # Если модель упорно пытается вывести "OK" через терминал вместо текстового ответа бесконечно
            if len(response_message.tool_calls) == 1:
                tc = response_message.tool_calls[0]
                if tc.function.name == "print_to_terminal":
                    try:
                        args = json.loads(tc.function.arguments)
                        text_arg = args.get("text", "").strip().upper()
                        if text_arg in ["OK", "'OK'", '"OK"', f"[{config.identity.agent_name}] OK"]:
                            answer = "OK"
                            system_logger.info("[BrainEngine] Перехват 'OK' в терминал. Принудительное завершение цикла для защиты от зацикливания.")
                            break
                    except Exception:
                        pass
            
            system_logger.info(f"[BrainEngine] Модель {LLM_MODEL} запросила вызов {len(response_message.tool_calls)} функций. Запущено параллельное выполнение.")

            action_names = [tc.function.name for tc in response_message.tool_calls]
            brain_state["action"] = ", ".join(action_names)

            # Параллельное выполнение инструментов
            tasks =[_execute_single_tool(tool_call) for tool_call in response_message.tool_calls]
            tool_results = await asyncio.gather(*tasks)

            # Добавляем результаты в историю сообщений (с перехватом медиа-инъекций)
            for res in tool_results:
                content = res.get("content", "")
                
                # Ловим магический тег от read_local_media
                if isinstance(content, str) and content.startswith("__MEDIA_INJECTION_REQUEST__:"):
                    filepath = content.split(":", 1)[1]
                    
                    try:
                        # Получаем base64 картинки
                        b64_string = await asyncio.to_thread(compress_and_encode_image, filepath)
                        
                        # Удовлетворяем API: отдаем инструменту текстовый ответ
                        res["content"] = f"Медиафайл '{filepath}' успешно передан."
                        messages.append(res)
                        
                        # Хак: мгновенно вбрасываем системное user-сообщение с самой картинкой, чтобы мультимодальный мозг понял
                        messages.append({
                            "role": "user",
                            "content":[
                                {"type": "text", "text": f"[Содержимое файла {filepath}]"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_string}"}}
                            ]
                        })
                        continue # Идем к следующему инструменту, этот обработан
                        
                    except Exception as e:
                        res["content"] = f"Ошибка при попытке получения медиафайла '{filepath}': {e}"
                        messages.append(res)
                        continue

                # Обычные текстовые ответы инструментов
                messages.append(res)

    except openai.APITimeoutError:
        error_msg = "[CRITICAL ERROR: ReAct цикл прерван. Серверы API недоступны]"
        await create_dialogue_entry(actor="System", message=error_msg, source="brain_engine")
        system_logger.error(f"[BrainEngine] Таймаут API: модель {LLM_MODEL} не ответила вовремя.")
        return "API нейросети отвалилось по таймауту."
    
    except openai.APIConnectionError as e:
        error_msg = "[CRITICAL ERROR: ReAct цикл прерван. Ошибка сетевого подключения к API LLM]"
        await create_dialogue_entry(actor="System", message=error_msg, source="brain_engine")
        system_logger.error(f"[BrainEngine] Ошибка подключения к API. Причина: {e.__cause__}")
        return "Ошибка подключения к API нейросети."
    
    except openai.APIError as e:
        error_msg = f"[CRITICAL ERROR: ReAct цикл прерван. API LLM вернуло ошибку сервера. Текст ошибки: {e}.]"
        await create_dialogue_entry(actor="System", message=error_msg, source="brain_engine")
        system_logger.error(f"[BrainEngine] Ошибка API {LLM_MODEL}: {e}")
        return f"Произошла ошибка API: {e}"
    
    except asyncio.TimeoutError:
        error_msg = "[CRITICAL ERROR: ReAct цикл прерван. Локальный асинхронный таймаут цикла мышления]"
        await create_dialogue_entry(actor="System", message=error_msg, source="brain_engine")
        system_logger.error(f"[BrainEngine] Таймаут API: модель {LLM_MODEL} не ответила вовремя.")
        return "API нейросети отвалилось по таймауту."
    
    except openai.RateLimitError as e:
        error_msg = "[CRITICAL ERROR: ReAct цикл прерван. API ключи исчерпали лимит запросов (ошибка 429)]"
        await create_dialogue_entry(actor="System", message=error_msg, source="brain_engine")
        system_logger.error(f"[BrainEngine] Все ключи ушли в лимит: {e}")
        return "API ключи исчерпали лимит запросов (ошибка 429)"
    
    except Exception as e:
        error_msg = "[CRITICAL ERROR: ReAct цикл прерван. Непредвиденная ошибка]"
        await create_dialogue_entry(actor="System", message=error_msg, source="brain_engine")
        system_logger.error(f"[BrainEngine] Непредвиденная ошибка при вызове {LLM_MODEL}: {e}")
        return f"Непредвиденная ошибка при обработке запроса к модели {LLM_MODEL}."

    return answer