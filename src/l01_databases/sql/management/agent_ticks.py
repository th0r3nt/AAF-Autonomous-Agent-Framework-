import json
import re
from typing import Sequence, Any, Optional
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select
from src.l01_databases.sql.models import AgentTick


class AgentTickCRUD:
    def __init__(self, table: AgentTick, session_factory: async_sessionmaker[AsyncSession]):
        self.table = table
        self._session_factory = session_factory

    # ==========================================
    # 🟢 CREATE
    # ==========================================

    async def create_tick(
        self,
        trigger_event_id: Optional[str] = None,
        status: str = "processing",
        thoughts: str = "",
        called_functions: list[dict[str, Any]] = None,
        function_results: list[dict[str, Any]] = None,
    ) -> AgentTick:
        """
        Создает новый тик. Обычно вызывается ДО начала работы LLM со статусом 'processing'.
        """
        async with self._session_factory() as session:
            tick = self.table(
                trigger_event_id=trigger_event_id,
                status=status,
                thoughts=thoughts,
                called_functions=called_functions or [],
                function_results=function_results or [],
            )
            session.add(tick)
            await session.commit()
            await session.refresh(tick)
            return tick

    # ==========================================
    # 🔵 READ
    # ==========================================

    async def get_tick_by_event_id(self, event_id: str) -> AgentTick | None:
        """
        Ищет ПЕРВЫЙ тик по UUID из RabbitMQ.
        Используется для защиты от дублей (Idempotency check).
        """
        async with self._session_factory() as session:
            # Важно добавить .limit(1), так как теперь на 1 событие может быть много тиков
            stmt = select(self.table).where(self.table.trigger_event_id == event_id).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_tick_by_id(self, tick_id: int) -> AgentTick | None:
        async with self._session_factory() as session:
            return await session.get(self.table, tick_id)

    async def get_all_ticks(self, limit: int = 100, offset: int = 0) -> Sequence[AgentTick]:
        async with self._session_factory() as session:
            stmt = (
                select(self.table)
                .order_by(self.table.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    # ==========================================
    # 🟡 UPDATE
    # ==========================================

    async def update_tick(self, tick_id: int, **kwargs) -> AgentTick | None:
        """
        Обновляет тик. Используется в конце работы LLM для записи мыслей и смены статуса на 'success' или 'failed'.
        """
        async with self._session_factory() as session:
            tick = await session.get(self.table, tick_id)
            if not tick:
                return None

            for key, value in kwargs.items():
                if hasattr(tick, key):
                    setattr(tick, key, value)

            await session.commit()
            await session.refresh(tick)
            return tick

    # ==========================================
    # 🔴 DELETE
    # ==========================================

    async def delete_tick(self, tick_id: int) -> bool:
        async with self._session_factory() as session:
            tick = await session.get(self.table, tick_id)
            if not tick:
                return False

            await session.delete(tick)
            await session.commit()
            return True

    async def cleanup_zombie_ticks(self) -> int:
        """
        Вызывается при старте сервера. Находит все зависшие тики (статус 'processing')
        и переводит их в 'failed', чтобы они не засоряли промпт.
        """
        async with self._session_factory() as session:
            stmt = select(self.table).where(self.table.status == "processing")
            result = await session.execute(stmt)
            zombies = result.scalars().all()

            for z in zombies:
                z.status = "failed"
                z.error_message = "System Crash / Zombie Tick (Очищено при рестарте)"

            await session.commit()
            return len(zombies)

    # ==========================================
    # MARKDOWN
    # ==========================================

    async def get_ticks_markdown(self, limit: int = 10, offset: int = 0) -> str:
        """
        Возвращает историю тиков агента в текстовом Markdown формате.
        Жестко сжимает данные, чтобы не переполнять контекстное окно LLM.
        """
        ticks = await self.get_all_ticks(limit, offset)
        if not ticks:
            return "История действий пуста."

        ticks = reversed(ticks)
        lines = []

        for t in ticks:
            if t.status == "processing":
                continue

            lines.append(f"\n### Tick #{t.id} [{t.status.upper()}]")

            if t.error_message:
                err = (
                    t.error_message
                    if len(t.error_message) < 300
                    else t.error_message[:297] + "..."
                )
                lines.append(f"Error: {err}")

            if t.thoughts:
                # Форматируем мысли: убираем переносы строк и лишние пробелы (всё в 1 строку)
                clean_thoughts = re.sub(r"\s+", " ", t.thoughts).strip()
                if len(clean_thoughts) > 500:
                    clean_thoughts = clean_thoughts[:497] + "... [ОБРЕЗАНО]"
                lines.append(f"*Thoughts*: {clean_thoughts} \n---")

            if t.called_functions:
                formatted_calls = []

                for f in t.called_functions:
                    name = f.get("tool_name", "unknown")
                    params = f.get("parameters", {})
                    param_parts = []

                    for k, v in params.items():
                        # Конвертируем в строку и заменяем реальные переносы на литералы '\n'
                        # Это сохранит логику кода (LLM поймет структуру), но текст будет в 1 строку
                        val_str = str(v).replace("\n", "\\n").replace("\r", "")

                        if len(val_str) > 300:
                            val_str = val_str[:297] + "... [ОБРЕЗАНО]"

                        if isinstance(v, str):
                            param_parts.append(f"{k}='{val_str}'")

                        else:
                            param_parts.append(f"{k}={val_str}")

                    formatted_calls.append(f"{name}({', '.join(param_parts)})")

                lines.append(f"*Action*: {', '.join(formatted_calls)} \n")

            if t.function_results:
                res_str = json.dumps(t.function_results, ensure_ascii=False)
                if len(res_str) > 500:
                    res_str = res_str[:497] + "... [ОБРЕЗАНО]"
                lines.append(f"*Result*: {res_str} \n---")

        return "\n".join(lines).strip()
