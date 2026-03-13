import time
from src.layer00_utils.logger import system_logger
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events

SYSTEM_MODULE_HEARTBEAT = Events.SYSTEM_MODULE_HEARTBEAT
SYSTEM_MODULE_ERROR = Events.SYSTEM_MODULE_ERROR

# Логические имена модулей вместо жестких путей к файлам
sql_db_module = "SQL DB"
vector_db_module = "Vector DB"
global_state_monitoring_module = "Global State Monitoring"
stt_module = "STT"
userbot_telethon_module = "Telegram Userbot"
events_monitoring_module = "Events Monitoring"
event_driven_module = "[ReAct] EventDriven"
proactivity_module = "[ReAct] Proactivity"
thoughts_module = "[ReAct] Thoughts"
graph_db_module = "Graph DB"

ALL_SYSTEM_MODULES = [
    sql_db_module, vector_db_module, graph_db_module,
    global_state_monitoring_module, stt_module, userbot_telethon_module,
    events_monitoring_module, event_driven_module, proactivity_module, thoughts_module
]

class WatchDog:
    def __init__(self):
        # Автоматически генерируем словарь статусов
        self.system_modules = {
            mod: {"status": "Loading...", "last_ping": 0} for mod in ALL_SYSTEM_MODULES
        }

    def update_status(self, module_name: str, status: str, error_msg: str = None):
        """Обновляет статус модуля: обновление происходит мгновенно (O(1))"""
        # Если модуль неизвестен (например, добавили новый декоратор), автоматически добавляем его в трекинг
        if module_name not in self.system_modules:
            self.system_modules[module_name] = {"status": "Loading...", "last_ping": 0}
            
        self.system_modules[module_name]["status"] = status
        self.system_modules[module_name]["last_ping"] = time.time()
        
        if error_msg:
            self.system_modules[module_name]["last_error"] = str(error_msg)
        return True

    async def handle_heartbeat(self, module_name: str, status: str, **kwargs) -> None:
        """Хендлер для EventBus. Срабатывает, когда кто-то публикует событие 'HEARTBEAT'"""
        self.update_status(module_name, status)

    async def handle_error(self, module_name: str, status: str, error_msg: str, **kwargs) -> None:
        """Хендлер для EventBus. Срабатывает при критических ошибках в модулях"""
        self.update_status(module_name, status, error_msg=error_msg)
        system_logger.error(f"[WatchDog] Модуль '{module_name}' упал со статусом {status}. Причина: {error_msg}")
        
    async def get_system_modules_report(self) -> str:
        """Возвращает строку с текущим состоянием модулей"""
        lines = []
        now = time.time()

        for module_name, data in self.system_modules.items():
            status = data["status"]
            last = data["last_ping"]
            ago = f"{round(now - last, 1)}s" if last > 0 else "∞"
            
            # Выбираем иконку в зависимости от статуса
            if status == "ON":
                icon = "[ON]"
            elif status == "ERROR":
                icon = "[ERROR]"
            else:
                icon = "[WARNING]" # Loading или другие промежуточные статусы
            
            error_info = f" -> ERROR: {data.get('last_error', 'Unknown Error')}" if status == "ERROR" else ""
            
            lines.append(f"{icon} {module_name} (last_ping: {ago}){error_info}")

        return "\n".join(lines)

watchdog = WatchDog()

def setup_watchdog():
    """Следит за работой других модулей. 
    Подписывается на события SYSTEM_MODULE_HEARTBEAT и SYSTEM_MODULE_ERROR"""
    event_bus.subscribe(SYSTEM_MODULE_HEARTBEAT, watchdog.handle_heartbeat)
    event_bus.subscribe(SYSTEM_MODULE_ERROR, watchdog.handle_error)