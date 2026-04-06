import datetime
from croniter import croniter

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument
from src.l01_databases.sql.management.scheduled_events import ScheduledEventCRUD

from src.l04_agency.skills.registry import skill


class CalendarScheduler(BaseInstrument):
    """Управление внутренним календарем агента (таймеры, напоминания, cron-задачи)."""

    def __init__(self, crud: ScheduledEventCRUD):
        super().__init__()
        self.crud = crud

    @skill()
    async def set_timer(
        self, note: str, delay_minutes: int = None, iso_datetime: str = None
    ) -> ToolResult:
        """
        Устанавливает таймер.
        Передавать либо delay_minutes (через сколько минут напомнить), либо iso_datetime (точная дата и время в UTC формате ISO 8601).
        """
        if not delay_minutes and not iso_datetime:
            return ToolResult.fail("Укажи либо delay_minutes, либо iso_datetime.")

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        exec_time = None

        try:
            if delay_minutes:
                exec_time = now_utc + datetime.timedelta(minutes=delay_minutes)
            elif iso_datetime:
                exec_time = datetime.datetime.fromisoformat(iso_datetime.replace("Z", "+00:00"))
                if exec_time.tzinfo is None:
                    exec_time = exec_time.replace(tzinfo=datetime.timezone.utc)

                if exec_time <= now_utc:
                    return ToolResult.fail("Ошибка: Указанное время уже прошло.")

            event = await self.crud.create_event(
                task_type="timer", execution_time=exec_time, note=note
            )
            time_str = exec_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            system_logger.info(
                f"[Calendar] Таймер установлен на {time_str}. Заметка: {note[:30]}..."
            )
            return ToolResult.ok(
                f"Таймер успешно установлен на {time_str}. (ID задачи: {event.id})"
            )

        except ValueError as e:
            return ToolResult.fail(
                f"Ошибка парсинга даты: {e}. Используй формат ISO 8601 (напр. '2025-12-31T15:00:00Z')."
            )
        except Exception as e:
            return ToolResult.fail(f"Ошибка БД: {e}")

    @skill()
    async def set_cron(self, cron_expr: str, note: str) -> ToolResult:
        """
        Устанавливает повторяющуюся задачу (cron).
        Пример cron_expr: '0 9 * * *' (каждый день в 9:00 UTC).
        """
        if not croniter.is_valid(cron_expr):
            return ToolResult.fail(f"Ошибка: Невалидное cron-выражение '{cron_expr}'.")

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        try:
            cron = croniter(cron_expr, now_utc)
            next_exec = cron.get_next(datetime.datetime)

            event = await self.crud.create_event(
                task_type="cron",
                execution_time=next_exec,
                note=note,
                cron_expression=cron_expr,
            )
            time_str = next_exec.strftime("%Y-%m-%d %H:%M:%S UTC")
            system_logger.info(
                f"[Calendar] Cron ({cron_expr}) установлен. Следующий запуск: {time_str}"
            )
            return ToolResult.ok(
                f"Регулярная задача создана (ID: {event.id}). Следующее срабатывание: {time_str}."
            )

        except Exception as e:
            return ToolResult.fail(f"Ошибка создания cron-задачи: {e}")

    @skill()
    async def get_my_schedule(self) -> ToolResult:
        """
        Возвращает список всех активных таймеров и кронов.
        """
        try:
            events = await self.crud.get_pending_events(limit=20)
            if not events:
                return ToolResult.ok("Ваш календарь пуст. Нет запланированных задач.")

            lines = ["--- Мое расписание (до 20 ближайших задач) ---"]
            for e in events:
                cron_info = (
                    f" (Cron: {e.cron_expression})" if e.task_type == "cron" else " (Таймер)"
                )
                time_str = e.execution_time.strftime("%Y-%m-%d %H:%M UTC")
                lines.append(f"ID: {e.id} | Время: {time_str}{cron_info}\n   Заметка: {e.note}")

            return ToolResult.ok("\n".join(lines))
        except Exception as e:
            return ToolResult.fail(f"Ошибка чтения календаря: {e}")

    @skill()
    async def cancel_task(self, task_id: int) -> ToolResult:
        """
        Отменяет таймер или cron.
        """
        try:
            event = await self.crud.update_event(task_id, status="cancelled")
            if not event:
                return ToolResult.fail(f"Задача с ID {task_id} не найдена.")

            system_logger.info(f"[Calendar] Задача {task_id} отменена агентом.")
            return ToolResult.ok(f"Задача ID {task_id} успешно отменена.")
        except Exception as e:
            return ToolResult.fail(f"Ошибка отмены задачи: {e}")
