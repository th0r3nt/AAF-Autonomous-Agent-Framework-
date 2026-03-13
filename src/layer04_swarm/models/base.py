from collections import deque
from src.layer00_utils.logger import system_logger
from src.layer01_datastate.sql_db.management.swarm_state import update_subagent_status

class BaseSubagent:
    def __init__(self, db_record):
        self.id = db_record.id
        self.name = db_record.name
        self.role = db_record.role
        self.instructions = db_record.instructions
        self.status = db_record.status
        self.memory_state = db_record.memory_state or {}

        # Наследие и флаги
        self.parent_name = getattr(db_record, 'parent_name', None)
        self.chain_depth = getattr(db_record, 'chain_depth', 0)
        self.is_delegated = False
        self.is_escalated = False
        
        self.logs = deque(maxlen=50) 
        self.allowed_tools = []
        self.system_prompt = ""

    def add_log(self, message: str):
        import time
        timestamp = time.strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")
        system_logger.debug(f"[{self.role} | {self.name}] {message}")

    async def die(self, final_status: str = "completed"):
        self.status = final_status
        await update_subagent_status(self.name, final_status)
        self.add_log(f"Процесс завершен со статусом: {final_status}")

    async def run(self):
        raise NotImplementedError("Метод run() должен быть переопределен")