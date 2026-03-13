from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
import os
from dotenv import load_dotenv
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog import sql_db_module
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events
import asyncio

load_dotenv()

# Настройки подключения
SQL_DB_URL = os.getenv("SQL_DB_URL")

# Создаем асинхронный движок
# echo=True будет выводить все SQL-запросы в консоль (удобно для отладки, в проде отключить)
engine = create_async_engine(
    SQL_DB_URL, 
    echo=False,
    pool_size=20,        # Базовое количество соединений в пуле
    max_overflow=10,     # Сколько дополнительных можно открыть при пиковой нагрузке
    pool_timeout=30,     # Сколько секунд ждать свободного коннекта, прежде чем кинуть ошибку
    pool_recycle=1800    # Перезапускать соединения каждые полчаса (защита от зависаний БД)
)

async_session_factory = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Базовый класс для всех моделей
class Base(DeclarativeBase):
    pass

async def stop_sql_db(*args, **kwargs):
    system_logger.info("[SQL DB] Отключение базы данных...")
    await engine.dispose() # Корректно закрываем все подключения
    system_logger.info("[SQL DB] База данных успешно отключена.")

async def setup_sql_db():
    await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=sql_db_module, status="ON")
    event_bus.subscribe(Events.STOP_SYSTEM, stop_sql_db) 
    
    try:
        # Ждем максимум 5 секунд. Если БД не отвечает - падаем с ошибкой
        async with engine.begin() as conn:
            await asyncio.wait_for(conn.run_sync(Base.metadata.create_all), timeout=15.0)
        system_logger.info("[SQL DB] База данных успешно подключена.")
    except asyncio.TimeoutError:
        system_logger.error("[SQL DB] Ошибка: База данных не отвечает (Таймаут). Проверьте Docker.")
        raise
    except Exception as e:
        system_logger.error(f"[SQL DB] Ошибка подключения: {e}")
        raise