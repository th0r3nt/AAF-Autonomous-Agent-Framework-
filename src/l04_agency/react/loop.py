# Файл: src/l04_agency/react/loop.py

import json
import datetime
from typing import Dict, Any

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings
from src.l00_utils.managers.config import LOGS_DIR

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
        tick_id: int,
    ) -> Dict[str, Any]:
        """
        Вызывает ReAct цикл OpenAI-совместимой модели.
        """
        current_ticks = 0
        aggregated_thoughts = []
        aggregated_actions = []
        aggregated_results =[]

        system_logger.info(
            f"[{cycle_type.upper()}] Инициализация ReAct-цикла (LLM: {self.llm_model}; Текущий шаг: {current_ticks}/{self.max_react_ticks})."
        )

        # 1. Склеиваем сообщения для LLM
        messages =[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_context},
        ]

        # Вычисляем "статичный" вес в символах (для математики токенов)
        prompt_len = len(system_prompt)
        tools_len = len(json.dumps(tools, ensure_ascii=False))

        while current_ticks < self.max_react_ticks:
            current_ticks += 1
            system_logger.debug(
                f"[{cycle_type.upper()}] Итерация мышления {current_ticks}/{self.max_react_ticks}."
            )

            try:
                # Получаем живую сессию (APIKeyRotator внутри сам подставит ключ)
                session = await self.client.get_session()

                # Вызов LLM (заставляем использовать execute_skill через tool_choice)
                response = await session.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    tools=tools,
                    tool_choice={"type": "function", "function": {"name": "execute_skill"}},
                    temperature=temperature,
                )

                # Трекинг токенов
                if response.usage:
                    total_input_tokens = response.usage.prompt_tokens

                    # Динамически считаем вес контекста (включая накопившуюся историю этого ReAct-цикла)
                    # Берем всё, кроме system_prompt (то есть index 1 и далее)
                    current_context_len = len(json.dumps(messages[1:], ensure_ascii=False))
                    total_chars = prompt_len + tools_len + current_context_len

                    # Разбиваем реальные токены пропорционально
                    calc_prompt = int(total_input_tokens * (prompt_len / total_chars))
                    calc_tools = int(total_input_tokens * (tools_len / total_chars))
                    calc_context = total_input_tokens - calc_prompt - calc_tools # Остаток отдаем контексту

                    self.client.token_tracker.add_input_record(
                        cycle_type=cycle_type,
                        prompt_tokens=calc_prompt,
                        context_tokens=calc_context,
                        tools_tokens=calc_tools
                    )
                    self.client.token_tracker.add_output_record(
                        cycle_type=cycle_type,
                        tokens=response.usage.completion_tokens
                    )

                response_message = response.choices[0].message
                messages.append(response_message)

                # Анализ ответа
                if not response_message.tool_calls:
                    system_logger.info(
                        f"[{cycle_type.upper()}] Модель {self.llm_model} не вызвала ни одного инструмента. Принудительная остановка."
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
                    # Возвращаем ошибку модели, чтобы она сама себя поправила на следующей итерации
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
                    continue

                thoughts = args.get("thoughts", "")
                actions = args.get("actions", [])

                # Логируем мысли агента
                if thoughts:
                    aggregated_thoughts.append(thoughts)
                    system_logger.info(f"[Thoughts] {thoughts}")

                # Проверка на выход из цикла
                if not actions:
                    system_logger.info(
                        f"[{cycle_type.upper()}] Агент передал пустой массив действий. ReAct-цикл завершен."
                    )
                    break

                # Исполнение инструментов
                aggregated_actions.extend(actions)
                system_logger.debug(
                    f"[{cycle_type.upper()}] Роутинг {len(actions)} действий на исполнение."
                )

                results = await self.skills_router.execute_parallel(actions)
                aggregated_results.extend(results)

                # Инжектим результаты обратно в контекст для следующего тика
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": json.dumps(results, ensure_ascii=False),
                    }
                )

            except Exception as e:
                system_logger.error(f"[ReAct Loop] Ошибка при вызове {self.llm_model}: {e}")
                # Если 429 (Rate Limit) - можно было бы вызвать rotator.mark_key_exhausted(),
                # но так как мы прокидываем Exception, это стоит отлавливать выше
                raise e

        # Дампим контекст по завершению цикла
        self._dump_context_to_file(cycle_type, messages)

        if current_ticks >= self.max_react_ticks:
            system_logger.warning(
                f"[{cycle_type.upper()}] Превышен лимит итераций ({self.max_react_ticks}). Цикл принудительно прерван."
            )

        return {
            "success": True,
            "thoughts": "\n\n".join(aggregated_thoughts),
            "called_functions": aggregated_actions,
            "function_results": aggregated_results,
        }
