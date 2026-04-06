import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from l00_utils.managers.event_bus import EventBus
from src.l00_utils.managers.logger import system_logger


# Базовый класс для всех моделей оставляем глобальным (это требование SQLAlchemy)
class Base(DeclarativeBase):
    __table_args__ = {"schema": "agent"}


class SQLDB:
    def __init__(self, event_bus: EventBus, db_url: str):
        self.event_bus = event_bus
        self._engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=20,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            connect_args={"server_settings": {"search_path": "agent"}},
        )

        self.session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def setup(self):
        """Инициализация БД и таблиц"""
        try:
            async with self._engine.begin() as conn:
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS agent"))
                await asyncio.wait_for(conn.run_sync(Base.metadata.create_all), timeout=15.0)

            system_logger.info("[SQL DB] База данных успешно подключена.")

        except asyncio.TimeoutError:
            system_logger.error(
                "[SQL DB] Ошибка: БД не отвечает (Таймаут). Рекомендуется проверить Docker."
            )
            raise

        except Exception as e:
            system_logger.error(f"[SQL DB] Ошибка подключения/инициализации схем: {e}")
            raise

    async def stop(self, *args, **kwargs):
        """Остановка пула соединений"""
        system_logger.info("[SQL DB] Отключение базы данных.")
        await self._engine.dispose()
        system_logger.info("[SQL DB] База данных успешно отключена.")


# sql_db = SQLDB(SQL_DB_URL)
