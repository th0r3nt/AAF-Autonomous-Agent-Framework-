import json
import datetime
from typing import Dict, Any
import openai
import asyncio
from typing import TYPE_CHECKING

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings
from src.l00_utils.managers.config import LOGS_DIR

if TYPE_CHECKING:
    from src.l01_databases.sql.management.agent_ticks import AgentTickCRUD
from src.l04_agency.llm.client import LLMClient
from src.l04_agency.llm.api_keys.rotator import APIKeyRotator
from src.l04_agency.skills.router import SkillRouter


class ReActLoop:
    def __init__(
        self,
        max_react_ticks: int,
        llm_model: str,
        openai_client: LLMClient,
        key_rotator: APIKeyRotator,
        skills_router: SkillRouter,
    ):
        self.max_react_ticks = max_react_ticks
        self.llm_model = llm_model
        self.client = openai_client
        self.key_rotator = key_rotator
        self.skills_router = skills_router

    def _dump_context_to_file(self, cycle_type: str, messages: list):
        """
        Сохраняет финальный промпт в Markdown-файл для отладки.
        Безопасно парсит как обычные dict, так и объекты OpenAI Pydantic.
        """
        if not settings.system.flags.dump_llm_context:
            return

        try:
            log_dir = LOGS_DIR
            log_dir.mkdir(parents=True, exist_ok=True)

            filename = f"last_{cycle_type}_context.md"
            file_path = log_dir / filename
            current_time = datetime.datetime.now().strftime("%H:%M:%S")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(
                    f"# ОТЛАДКА КОНТЕКСТА \nТип цикла: {cycle_type.upper()} Обновлено: {current_time}\n\n"
                )

                for msg in messages:
                    # Поддержка объектов OpenAI (ChatCompletionMessage)
                    if hasattr(msg, "model_dump"):
                        msg = msg.model_dump(exclude_none=True)

                    role = msg.get("role", "unknown")
                    content = msg.get("content") or ""

                    if role == "assistant" and msg.get("tool_calls"):
                        tool_calls = msg["tool_calls"]
                        content += f"\n[TOOL CALLS]: {json.dumps(tool_calls, ensure_ascii=False, indent=2)}"

                    f.write(f"### Role: {role.upper()}\n{content}\n\n---\n\n")

        except Exception as e:
            system_logger.error(f"[ReAct Loop] Не удалось сохранить контекст для отладки: {e}")

    async def run(
        self,
        cycle_type: str,
        system_prompt: str,
        user_context: str,
        tools: list,
        temperature: float,
        transaction_id: str,  # Получаем ID транзакции
        tick_crud: 'AgentTickCRUD'  # Принимаем CRUD базу для работы с тиками
    ) -> Dict[str, Any]:
        """
        Вызывает ReAct цикл OpenAI-совместимой модели.
        """
        current_ticks = 0

        system_logger.info(
            f"[{cycle_type.upper()}] Инициализация ReAct-цикла (LLM: {self.llm_model}; Шаг: {current_ticks} Макс. шагов: {self.max_react_ticks})."
        )

        # 1. Склеиваем сообщения для LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_context},
        ]

        # Вычисляем "статичный" вес в символах (для математики токенов)
        prompt_len = len(system_prompt)
        tools_len = len(json.dumps(tools, ensure_ascii=False))

        self._dump_context_to_file(cycle_type, messages)

        while current_ticks < self.max_react_ticks:
            current_ticks += 1
            system_logger.debug(
                f"[{cycle_type.upper()}] Итерация мышления {current_ticks}/{self.max_react_ticks}."
            )

            # 2. НОВОЕ: Создаем тик в БД ДО запроса к LLM
            current_tick = await tick_crud.create_tick(
                trigger_event_id=transaction_id, status="processing"
            )

            try:
                # Получаем живую сессию (APIKeyRotator внутри сам подставит ключ)
                session = await self.client.get_session()

                # Вызов LLM
                try:
                    response = await asyncio.wait_for(
                        session.chat.completions.create(
                            model=self.llm_model,
                            messages=messages,
                            tools=tools,
                            tool_choice={
                                "type": "function",
                                "function": {"name": "execute_skill"},
                            },
                            temperature=temperature,
                        ),
                        timeout=60.0,  # <--- Ждем ровно минуту
                    )
                except asyncio.TimeoutError:
                    system_logger.warning(
                        f"[{cycle_type.upper()}] LLM не ответила за 60 секунд. Попытка ретрая с новым ключом."
                    )
                    # Фиксируем ошибку в БД, чтобы тик не стал "зомби"
                    await tick_crud.update_tick(
                        current_tick.id, status="failed", error_message="LLM API Timeout (60s)"
                    )
                    current_ticks -= 1
                    continue

                # Трекинг токенов
                if response.usage:
                    total_input_tokens = response.usage.prompt_tokens

                    safe_messages = []
                    for m in messages[1:]:
                        if hasattr(m, "model_dump"):
                            safe_messages.append(m.model_dump(exclude_none=True))
                        else:
                            safe_messages.append(m)

                    current_context_len = len(json.dumps(safe_messages, ensure_ascii=False))
                    total_chars = prompt_len + tools_len + current_context_len

                    # Разбиваем реальные токены пропорционально
                    calc_prompt = int(total_input_tokens * (prompt_len / total_chars))
                    calc_tools = int(total_input_tokens * (tools_len / total_chars))
                    calc_context = total_input_tokens - calc_prompt - calc_tools

                    self.client.token_tracker.add_input_record(
                        cycle_type=cycle_type,
                        prompt_tokens=calc_prompt,
                        context_tokens=calc_context,
                        tools_tokens=calc_tools,
                    )
                    self.client.token_tracker.add_output_record(
                        cycle_type=cycle_type, tokens=response.usage.completion_tokens
                    )

                response_message = response.choices[0].message
                messages.append(response_message)

                # Анализ ответа
                if not response_message.tool_calls:
                    system_logger.info(
                        f"[{cycle_type.upper()}] Модель {self.llm_model} не вызвала ни одного инструмента. Принудительная остановка."
                    )
                    await tick_crud.update_tick(
                        current_tick.id,
                        status="failed",
                        error_message="No tool calls generated.",
                    )
                    break

                tool_call = response_message.tool_calls[0]
                args_str = tool_call.function.arguments

                # Парсинг JSON с защитой от галлюцинаций
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError as e:
                    system_logger.error(
                        f"[{cycle_type.upper()}] LLM {self.llm_model} сгенерировала невалидный JSON. Запрошено исправление."
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": json.dumps(
                                {
                                    "status": "error",
                                    "error": f"Invalid JSON syntax: {e}.",
                                }
                            ),
                        }
                    )
                    await tick_crud.update_tick(
                        current_tick.id,
                        status="failed",
                        error_message=f"JSON Decode Error: {e}",
                    )
                    continue

                thoughts = args.get("thoughts", "")
                actions = args.get("actions", [])

                # Логируем мысли агента
                if thoughts:
                    system_logger.info(f"[Thoughts] {thoughts}")

                # Проверка на выход из цикла
                if not actions:
                    system_logger.info(
                        f"[{cycle_type.upper()}] Агент передал пустой массив действий. ReAct-цикл завершен."
                    )
                    await tick_crud.update_tick(
                        current_tick.id, status="success", thoughts=thoughts
                    )
                    break

                # Исполнение инструментов
                system_logger.debug(
                    f"[{cycle_type.upper()}] Роутинг {len(actions)} действий на исполнение."
                )

                results = await self.skills_router.execute_parallel(actions)

                # Инжектим результаты обратно в контекст для следующего тика
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": json.dumps(results, ensure_ascii=False),
                    }
                )

                # 3. НОВОЕ: Обновляем тик в БД как УСПЕШНЫЙ (записываем мысли и результаты)
                await tick_crud.update_tick(
                    current_tick.id,
                    status="success",
                    thoughts=thoughts,
                    called_functions=actions,
                    function_results=results,
                )

                # Опционально: обновляем дамп контекста с новыми сообщениями
                self._dump_context_to_file(cycle_type, messages)

            except openai.RateLimitError:
                system_logger.warning(
                    f"[{cycle_type.upper()}] Ключ улетел в Rate Limit (429). Ротация ключа и повторная попытка."
                )
                await tick_crud.update_tick(
                    current_tick.id, status="failed", error_message="Rate Limit (429)"
                )
                await self.key_rotator.mark_key_exhausted(session.api_key)
                current_ticks -= 1
                continue

            except Exception as e:
                system_logger.error(f"[ReAct Loop] Ошибка при вызове {self.llm_model}: {e}")
                # Спасаем тик от превращения в зомби при любом краше кода
                await tick_crud.update_tick(
                    current_tick.id, status="failed", error_message=str(e)
                )
                raise e

        if current_ticks >= self.max_react_ticks:
            system_logger.warning(
                f"[{cycle_type.upper()}] Превышен лимит итераций ({self.max_react_ticks}). Цикл принудительно прерван."
            )

        # Оркестратор теперь просто получает сигнал, что всё завершилось нормально,
        # так как БД уже обновлена внутри цикла.
        return {"success": True}
