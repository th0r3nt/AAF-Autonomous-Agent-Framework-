from sqlalchemy import text
from src.l00_utils.managers.logger import system_logger

from src.l00_utils.managers.event_bus import EventBus
from src.l01_databases.sql.db import SQLDB

# Родители
from src.l03_interfaces.type.base import BaseClient

# SQL таблица
from src.l01_databases.sql.models import ScheduledEvent
from src.l01_databases.sql.management.scheduled_events import ScheduledEventCRUD

# Поллинг
from src.l03_interfaces.type.calendar.events import CalendarEvents

# Инструменты
from src.l03_interfaces.type.calendar.instruments.scheduler import CalendarScheduler


class CalendarClient(BaseClient):

    name = "calendar"  # Имя для маппинга

    def __init__(self, event_bus: EventBus, sql_db: SQLDB):
        self.event_bus = event_bus

        self.sql_db = sql_db
        # Инициализируем CRUD сразу здесь, передавая фабрику сессий
        self.crud = ScheduledEventCRUD(
            table=ScheduledEvent, session_factory=self.sql_db.session_factory
        )

    def register_instruments(self):
        CalendarScheduler(crud=self.crud)
        system_logger.debug("[Calendar] Инструменты успешно зарегистрированы.")

    async def start_background_polling(self) -> None:
        events = CalendarEvents(event_bus=self.event_bus, client=self)
        events.start_ticker()  # Проверка задач каждую минуту

    async def check_connection(self) -> bool:
        try:
            # Проверяем, жива ли база
            async with self.sql_db._engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            system_logger.info("[Calendar] Внутренний планировщик успешно запущен.")
            return True
        except Exception as e:
            system_logger.error(f"[Calendar] Ошибка подключения к SQL БД: {e}")
            return False

    async def close(self):
        pass
