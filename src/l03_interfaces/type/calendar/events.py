import asyncio
from datetime import datetime, timezone
from croniter import croniter

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.event.registry import Events
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.l03_interfaces.type.calendar.client import CalendarClient


class CalendarEvents:
    def __init__(self, event_bus: EventBus, client: CalendarClient):
        self.event_bus = event_bus
        self.client = client
        self.crud = client.crud

    async def _process_due_events(self):
        """
        Проверяет БД на наличие просроченных задач и отправляет их агенту.
        """
        now_utc = datetime.now(timezone.utc)

        try:
            # Получаем задачи, время которых наступило
            due_events = await self.crud.get_due_events(now_utc)

            for event in due_events:
                system_logger.info(
                    f"[Calendar] Сработал будильник ID {event.id}: {event.note[:50]}..."
                )

                # Публикуем событие для LLM
                await self.event_bus.publish(
                    Events.SYSTEM_CALENDAR_ALARM,
                    event_id=event.id,
                    task_type=event.task_type,
                    note=event.note,
                    scheduled_time=str(event.execution_time),
                )

                # Обновляем БД в зависимости от типа задачи
                if event.task_type == "timer":
                    # Одноразовый таймер — закрываем
                    await self.crud.update_event(event.id, status="completed")

                elif event.task_type == "cron" and event.cron_expression:
                    # Регулярная задача - вычисляем следующую дату и обновляем
                    try:
                        cron = croniter(event.cron_expression, now_utc)
                        next_execution = cron.get_next(datetime)
                        await self.crud.update_event(event.id, execution_time=next_execution)
                        system_logger.debug(
                            f"[Calendar] Cron ID {event.id} перенесен на {next_execution}"
                        )
                    except Exception as e:
                        system_logger.error(
                            f"[Calendar] Ошибка вычисления cron '{event.cron_expression}': {e}"
                        )
                        await self.crud.update_event(event.id, status="error")

        except Exception as e:
            system_logger.error(f"[Calendar] Ошибка обработки задач: {e}")

    async def calendar_ticker_loop(self):
        """
        Бесконечный цикл, проверяющий БД каждую минуту.
        """
        if not await self.client.check_connection():
            return

        while True:
            await self._process_due_events()

            # Спим так, чтобы просыпаться ровно в 00 секунд каждой минуты
            # (это делает крон более точным)
            now = datetime.now()
            sleep_time = 60 - now.second
            await asyncio.sleep(sleep_time)

    def start_ticker(self):
        """
        Синхронная обертка для удобного запуска из менеджера интерфейсов.
        """
        asyncio.create_task(self.calendar_ticker_loop())
