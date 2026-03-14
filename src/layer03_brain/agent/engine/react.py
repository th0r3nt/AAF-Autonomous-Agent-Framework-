import os
import json
import asyncio
import openai
from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer01_datastate.sql_db.management.agent_actions import create_agent_action
from src.layer01_datastate.sql_db.management.dialogue import create_dialogue_entry
from src.layer03_brain.agent.skills.skills_configuration import skills_registry
from src.layer03_brain.llm.client import client_openai, key_manager
from src.layer03_brain.agent.engine.state import brain_state

LLM_MODEL = config.llm.model_name
MAX_REACT_STEPS = config.llm.max_react_steps

def _dump_context_to_file(messages: list):
    """Служебная функция для отладки: сохраняет финальный промпт в Markdown-файл"""
    if not config.system.flags.dump_llm_context:
        return # Если флаг False, просто выходим
    try:
        import datetime
        os.makedirs("logs", exist_ok=True)
        
        with open("src/logs/latest_llm_context.md", "w", encoding="utf-8") as f:
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
    """Изолированная функция для выполнения одного инструмента. Позволяет запускать их параллельно."""
    func_name = tool_call.function.name
    
    try:
        # Пробуем распарсить стандартным способом
        func_args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as original_error:
        # Если упало - зовем спасателя
        try:
            func_args = _rescue_json(tool_call.function.arguments)
            system_logger.info(f"[Agent Action] Успешно восстановлен кривой JSON для инструмента {func_name}.")
        except Exception:
            # Если спасатель тоже не справился, возвращаем ошибку агенту
            error_msg = f"JSONDecodeError: Неверный формат аргументов. Исправь синтаксис JSON. Ошибка парсера: {original_error}"
            system_logger.warning(f"[Agent Action] {func_name} провален (кривой JSON): {error_msg}")
            
            # Логируем сам кривой JSON в дебаг, чтобы потом можно было понять, почему он сломался
            system_logger.debug(f"[Agent Action] Сломанный JSON от LLM: {tool_call.function.arguments}")
            
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": func_name,
                "content": error_msg
            }

    result = None
    
    if func_name in skills_registry:
        limit = 800

        args_str = str(func_args)
        if len(args_str) > limit:
            args_str = args_str[:limit] + "... [Обрезано]"

        system_logger.info(f"[Agent Action] {func_name} с аргументами {args_str}.")

        try:
            # Если функция асинхронная
            if asyncio.iscoroutinefunction(skills_registry[func_name]):
                result = await skills_registry[func_name](**func_args)

            # Если функция синхронная (например, ChromaDB)
            else:
                # Запускаем синхронный код в фоне, не блокируя асинхронный мозг
                result = await asyncio.to_thread(skills_registry[func_name], **func_args)

            result_str = str(result)
            system_logger.info(f"[Agent Action Result] {result_str[:limit] + ('... [Обрезано]' if len(result_str) > limit else '')}")

        except Exception as e:
            system_logger.error(f"Ошибка при выполнении {func_name}: {e}")
            result_str = f"Error executing function: {e}"

        # Сохраняем действие в БД
        await create_agent_action(action_type=func_name, details=func_args)

    else:
        result_str = f"Error: Function {func_name} not found in registry."

    # Обычный возврат текста
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
                        await asyncio.sleep(2)
                    else:
                        # Если мы перебрали все ключи, и все отбили нас 429-й ошибкой (жесткий спам запросами)
                        # Возвращаем текст, чтобы ReAct цикл корректно завершился, а не упал
                        return "Система перегружена (превышен минутный лимит запросов API). Подожди немного."

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
            tasks = [_execute_single_tool(tool_call) for tool_call in response_message.tool_calls]
            tool_results = await asyncio.gather(*tasks)

            # Добавляем результаты в историю сообщений
            for res in tool_results:
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