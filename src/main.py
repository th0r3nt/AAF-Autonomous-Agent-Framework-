import asyncio
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog import setup_watchdog
from src.layer00_utils.workspace import workspace_manager

from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events
from src.layer01_datastate.sql_db.sql_db import setup_sql_db
from src.layer01_datastate.vector_db.vector_db import setup_vector_db
from src.layer01_datastate.graph_db.graph_db import setup_graph_db
from src.layer01_datastate.global_state.global_state_monitoring import global_state_monitoring

from src.layer02_sensors.pc.pc_monitoring import pc_monitoring
from src.layer02_sensors.telegram.tg_manager import setup_telegram
from src.layer02_sensors.sandbox_listener import start_sandbox_listener

from src.layer03_brain.events_monitoring import events_monitoring
from src.layer03_brain.agent.engine.engine import brain_engine

from src.layer04_swarm.manager import swarm_manager

START_SYSTEM = Events.START_SYSTEM
STOP_SYSTEM = Events.STOP_SYSTEM

th0r3nt = None

# >>>>> docker ps - проверка пульса
# >>>>> docker-compose up -d --build
# >>>>> docker-compose down - убить контейнеры
# >>>>> docker compose logs agent_core -f - вывести логи


class Gateway:
    def __init__(self):
        self.tasks = []
        workspace_manager.init_workspace() 
        setup_watchdog()

    # LAYER 1: DATASTATE
    async def setup_datastate(self) -> None:
        """Запускает базы данных и мониторинг глобального состояния"""
        await setup_sql_db()
        await setup_vector_db()
        await setup_graph_db()

        self.tasks.append(asyncio.create_task(global_state_monitoring.run_loop()))

    # LAYER 2: SENSORS
    async def setup_sensors(self) -> None:
        """Запускает мониторинг PC и Telegram"""
        self.tasks.append(asyncio.create_task(pc_monitoring.run_loop()))
        self.tasks.append(asyncio.create_task(setup_telegram()))
        self.tasks.append(asyncio.create_task(start_sandbox_listener()))

    # LAYER 3: BRAIN
    async def setup_brain(self) -> None:
        """Запускает мониторинг входящих событий с Event Bus, агента на базе LLM и циклы проактивности"""
        self.tasks.append(asyncio.create_task(events_monitoring.setup_monitoring()))
        self.tasks.append(asyncio.create_task(brain_engine.run_loops())) # Запускает цикл ответов на входящие события + цикл проактивности и интроспекции

    # LAYER 4: SWARM
    async def setup_swarm(self) -> None:
        """Запускает Agent Swarm System"""
        await swarm_manager.startup()

    # MANAGEMENT
    async def startup(self) -> None:
        """Запускает всё"""
        await self.setup_datastate()
        await self.setup_sensors()
        await self.setup_brain()
        await self.setup_swarm()

        # Даем сенсорам (особенно Telegram) время на подключение к серверам
        system_logger.info("[System] Ожидание инициализации подключения к серверам.")
        await asyncio.sleep(10) 

        # Публикуем событие старта
        await event_bus.publish(START_SYSTEM) 

        # Запускаем задачи
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def stop(self):
        system_logger.info("[System] Остановка агента...")
        await event_bus.publish(STOP_SYSTEM)

        await asyncio.sleep(3) # Даем хендлерам (особенно Telegram) время на корректное закрытие баз

        # Отменяем таски
        for task in self.tasks:
            task.cancel()

        system_logger.info("[System] Агент полностью отключен.")


async def main() -> None:
    """Запускает систему"""
    gateway = Gateway()
    try:
        await gateway.startup() # Запускает бесконечные циклы

    except asyncio.CancelledError:
        pass # Игнорируем штатную отмену задач

    finally:
        await gateway.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main()) 

    except KeyboardInterrupt:
        print("[System] Получен сигнал прерывания (Ctrl+C). Завершение работы.") 