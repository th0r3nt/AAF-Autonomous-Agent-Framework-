import asyncio
from config.config_manager import config

from src.layer00_utils._tools import get_datetime#, get_weather
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog import global_state_monitoring_module
from src.layer00_utils.workspace import workspace_manager
from src.layer01_datastate.event_bus.events import Events
from src.layer01_datastate.event_bus.event_bus import event_bus

WEATHER_ALERT = Events.WEATHER_ALERT

# Класс, взаимодействующий с глобальным состоянием (телеметрия, погода и т.п.)
class GlobalStateMonitoring:
    def __init__(self):
        self.states = {
            # "TELEMETRY": {"func": get_telemetry, "interval": config.rhythms.telemetry_poll_sec, "status": "Загрузка..."},
            # "NETWORK": {"func": get_network_status, "interval": config.rhythms.telemetry_poll_sec, "status": "Загрузка..."},
            "DATETIME": {"func": get_datetime, "interval": config.rhythms.telemetry_poll_sec, "status": "Загрузка..."},
            # "WEATHER": {"func": get_weather, "interval": config.rhythms.weather_poll_sec, "status": "Загрузка..."},
        }

        self.last_weather_conditions = ""
        self.first_weather_call = True

    async def _run_task(self, name: str, config: dict) -> None:
        """Индивидуальный цикл выполнения для каждой задачи"""
        func = config["func"]
        interval = config["interval"]
        
        while True:
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func()
                else:
                    result = await asyncio.to_thread(func)

                self.states[name]["status"] = result
                await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=global_state_monitoring_module, status="ON")

            except Exception as e:
                self.states[name]["status"] = f"Error: {e}"
                await event_bus.publish(Events.SYSTEM_MODULE_ERROR, module_name=global_state_monitoring_module, status="ERROR", error_msg=str(e))
                system_logger.error(f"Ошибка в задаче {name}: {e}")
            
            await asyncio.sleep(interval)

    async def _run_workspace_ttl_cleaner(self):
        """Фоновая задача для очистки старых временных файлов в workspace (раз в час)"""
        while True:
            await asyncio.sleep(3600) # Проверять раз в час
            try:
                ttl = config.memory.workspace_garbage_collector.temp_files_ttl_hours
                # Запускаем в to_thread, так как там синхронные операции с диском
                await asyncio.to_thread(workspace_manager.cleanup_old_temp_files, max_age_hours=ttl)
            except Exception as e:
                system_logger.error(f"Ошибка при очистке workspace: {e}")

    async def run_loop(self) -> None:
        system_logger.info("[GlobalState] Мониторинг запущен.")

        runners = [
            self._run_task(name, config) 
            for name, config in self.states.items()
        ]

        runners.append(self._run_workspace_ttl_cleaner())

        await asyncio.gather(*runners)

    async def get_global_state(self) -> str:
        """Возвращает глобальное состояние"""
        lines = []
        for key, value in self.states.items():
            status = value.get('status', 'Н/Д')
            lines.append(f"- {key}: {status}")
            
        return "\n".join(lines)

global_state_monitoring = GlobalStateMonitoring()