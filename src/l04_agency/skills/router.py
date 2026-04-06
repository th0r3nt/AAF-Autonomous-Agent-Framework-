import asyncio
import traceback
import inspect
import json
from typing import Dict, Any, List, Callable

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.models import ToolResult
from src.l04_agency.skills.registry import ToolRegistry


class SkillRouter:
    """
    Роутер навыков. Принимает список запрошенных LLM действий,
    параллельно их выполняет и возвращает результаты.
    Оснащен умным парсером типов (Smart Auto-Cast) для защиты от галлюцинаций LLM.
    """

    async def execute_parallel(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Выполняет список действий (actions) параллельно с жесткой защитой от зависаний.
        Формат action: {"tool_name": "github.get_issue", "parameters": {"repo": "...", "id": 1}}
        """
        tasks = []
        for action in actions:
            tool_name = action.get("tool_name", "unknown_tool")
            params = action.get("parameters", {})

            # Защита от глупости LLM (если она передала параметры строкой)
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except json.JSONDecodeError:
                    params = {}

            # Оборачиваем вызов в Task и даем ему имя
            # Это нужно, чтобы опознать "труп", если таска зависнет и отвалится по таймауту
            task = asyncio.create_task(self._execute_single(tool_name, params))
            task.set_name(tool_name)
            tasks.append(task)

        if not tasks:
            return []

        # Предохранитель: отдельные тулзы (Docker/HTTP) должны падать раньше,
        # но если всё пошло к чертям - через 60 секунд мы убиваем процесс
        MAX_TIMEOUT = 60.0

        # Запускаем всё одновременно и ждем
        done, pending = await asyncio.wait(tasks, timeout=MAX_TIMEOUT)

        results = []

        # Собираем результаты того, что отработало нормально (или упало с понятной ошибкой внутри _execute_single)
        for task in done:
            try:
                results.append(task.result())
            except Exception as e:
                # На случай системных сбоев самого asyncio
                tool_name = task.get_name()
                system_logger.error(
                    f"[SkillRouter] Критическое падение внутри Task ({tool_name}): {e}"
                )
                results.append(
                    {
                        "tool_name": tool_name,
                        "status": "critical_error",
                        "result": f"Системная ошибка Task: {e}",
                    }
                )

        # Безжалостно убиваем всё, что зависло
        if pending:
            for task in pending:
                tool_name = task.get_name()
                system_logger.error(
                    f"[SkillRouter] Инструмент '{tool_name}' завис и убит по таймауту ({MAX_TIMEOUT}с)."
                )

                task.cancel()  # Отменяем корутину

                # Формируем ответ для LLM, чтобы агент понял, что его инструмент "умер"
                results.append(
                    {
                        "tool_name": tool_name,
                        "status": "critical_error",
                        "result": f"Критическая ошибка: Инструмент завис. Время ожидания вышло ({MAX_TIMEOUT} сек). Процесс принудительно убит системой.",
                    }
                )

        return results

    def _cast_arguments(self, func: Callable, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Читает сигнатуру функции и конвертирует аргументы от LLM в нужные типы.
        Полезно, если LLM передала '123' вместо 123.
        """
        sig = inspect.signature(func)
        casted_params = {}

        # Проверяем, принимает ли функция **kwargs (чтобы знать, можно ли пробрасывать лишнее)
        has_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )

        for key, value in params.items():
            # Защита от выдуманных аргументов
            if key not in sig.parameters:
                if has_kwargs:
                    casted_params[key] = value
                else:
                    system_logger.warning(
                        f"[SkillRouter] LLM модель выдумала аргумент '{key}'."
                    )
                continue

            param = sig.parameters[key]
            expected_type = param.annotation

            # Если тайп-хинт не указан в функции, оставляем как есть
            if expected_type == inspect.Parameter.empty:
                casted_params[key] = value
                continue

            expected_type_str = str(expected_type).lower()
            casted_value = value

            try:
                # Умное приведение типов
                if "bool" in expected_type_str:
                    if isinstance(value, str):
                        # Защита от бага bool("False") == True
                        casted_value = value.lower() in ("true", "1", "yes", "y")
                    else:
                        casted_value = bool(value)

                elif "int" in expected_type_str:
                    casted_value = int(value)

                elif "float" in expected_type_str:
                    casted_value = float(value)

                elif "list" in expected_type_str or "dict" in expected_type_str:
                    # Иногда LLM пакует списки/словари в строку "[1, 2, 3]"
                    if isinstance(value, str):
                        try:
                            casted_value = json.loads(value)
                        except json.JSONDecodeError:
                            pass  # Оставляем строкой, вдруг так и надо

                elif "str" in expected_type_str:
                    # Если LLM передала словарь туда, где ожидается строка
                    if isinstance(value, (list, dict)):
                        casted_value = json.dumps(value, ensure_ascii=False)
                    else:
                        casted_value = str(value)

            except (ValueError, TypeError):
                # Если конвертация провалилась (например, int("abc")) - оставляем оригинал
                # Дальше функция сама упадет и вернет ошибку в LLM
                casted_value = value

            casted_params[key] = casted_value

        return casted_params

    async def _execute_single(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Безопасное выполнение одного инструмента с перехватом любых падений."""
        system_logger.info(f"[Agent Action] Выполнение: {tool_name} {params}")

        func = ToolRegistry.get_tool(tool_name)

        if not func:
            error_msg = f"Инструмент '{tool_name}' не найден в SKILLS LIBRARY."
            system_logger.warning(f"[Agent Action Result] Провал {tool_name}: {error_msg}")
            return {"tool_name": tool_name, "status": "error", "result": error_msg}

        try:
            # АВТО-КАСТ
            casted_params = self._cast_arguments(func, params)
            system_logger.debug(f"[SkillRouter] Аргументы после каста: {casted_params}")

            # Вызываем функцию (если она асинхронная - await, если нет - просто вызываем)
            if asyncio.iscoroutinefunction(func):
                tool_result: ToolResult = await func(**casted_params)
            else:
                tool_result: ToolResult = func(**casted_params)

            # Проверяем результат (ToolResult)
            if tool_result.success:
                system_logger.debug(f"[Agent Action Result] Успех {tool_name}.")
                return {
                    "tool_name": tool_name,
                    "status": "success",
                    "result": tool_result.llm_message,
                }
            else:
                system_logger.warning(
                    f"[Agent Action Result] Ошибка внутри {tool_name}: {tool_result.error}"
                )
                return {
                    "tool_name": tool_name,
                    "status": "error",
                    "result": tool_result.llm_message,
                }

        except TypeError as e:
            # Теперь эта ошибка сработает ТОЛЬКО если агент забыл передать обязательный аргумент
            err = f"Ошибка аргументов для {tool_name}: {e}."
            system_logger.error(f"[Agent Action Result] {err}")
            return {"tool_name": tool_name, "status": "error", "result": err}

        except Exception as e:
            # Если упал сам код инструмента (баг)
            trace = traceback.format_exc()
            system_logger.error(f"[Agent Action Result] CRITICAL CRASH: {tool_name}:\n{trace}")
            return {
                "tool_name": tool_name,
                "status": "critical_error",
                "result": f"Критическая ошибка: {e}",
            }
