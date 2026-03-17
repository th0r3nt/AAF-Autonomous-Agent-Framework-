import asyncio
from src.layer00_utils.logger import system_logger
from src.layer01_datastate.sql_db.management.swarm_state import create_or_reset_subagent, get_active_subagents, update_subagent_status, update_subagent_config
from src.layer04_swarm.models.workers import Researcher, SystemAnalyst, ChatSummarizer, Chronicler
from src.layer04_swarm.models.daemons import WebMonitor

# Реестр доступных ролей
ROLE_CLASSES = {
    "Researcher": Researcher,
    "SystemAnalyst": SystemAnalyst,
    "ChatSummarizer": ChatSummarizer,
    "WebMonitor": WebMonitor,
    "Chronicler": Chronicler,
}

class SwarmManager:
    def __init__(self):
        self.active_processes = {} # {name: {"task": task, "obj": subagent_instance}}

    async def startup(self):
        """Воскрешение демонов при старте системы"""
        system_logger.info("[SwarmManager] Инициализация. Воскрешение субагентов из БД...")
        active_records = await get_active_subagents()
        count = 0
        for record in active_records:
            if record.role in ROLE_CLASSES:
                obj = ROLE_CLASSES[record.role](record)
                task = asyncio.create_task(obj.run())
                self.active_processes[record.name] = {"task": task, "obj": obj}
                task.add_done_callback(lambda t, n=record.name: self.active_processes.pop(n, None))
                count += 1
            else:
                system_logger.warning(f"[SwarmManager] Неизвестная роль '{record.role}' для '{record.name}'")
                await update_subagent_status(record.name, "error")
        system_logger.info(f"[SwarmManager] Успешно воскрешено {count} субагентов.")

    async def spawn_subagent(self, role: str, name: str, instructions: str, trigger_condition: str = None, interval_sec: int = None) -> str:
        if role not in ROLE_CLASSES:
            return f"Ошибка: Роль '{role}' не существует. Доступные: {list(ROLE_CLASSES.keys())}"
        
        if name in self.active_processes:
            self.active_processes[name]["task"].cancel()
            del self.active_processes[name]

        db_record = await create_or_reset_subagent(name, role, instructions, trigger_condition, interval_sec)
        obj = ROLE_CLASSES[role](db_record)
        
        task = asyncio.create_task(obj.run())
        self.active_processes[name] = {"task": task, "obj": obj}
        task.add_done_callback(lambda t, n=name: self.active_processes.pop(n, None))
        
        system_logger.info(f"[SwarmManager] Запущен субагент '{name}' (Роль: {role})")
        return f"Субагент '{name}' (Роль: {role}) успешно запущен в фоне."
    
    async def spawn_child_subagent(self, role: str, name: str, instructions: str, parent_name: str, chain_depth: int):
        """Специальный метод для Agentic Mesh (вызывается внутри инструмента делегирования)"""
        db_record = await create_or_reset_subagent(
            name=name, role=role, instructions=instructions, 
            parent_name=parent_name, chain_depth=chain_depth
        )
        obj = ROLE_CLASSES[role](db_record)
        task = asyncio.create_task(obj.run())
        self.active_processes[name] = {"task": task, "obj": obj}
        task.add_done_callback(lambda t, n=name: self.active_processes.pop(n, None))
        system_logger.info(f"[SwarmManager] Agentic Mesh: {parent_name} создал дополнительного субагента '{name}' (Depth: {chain_depth})")

    async def kill_subagent(self, name: str) -> str:
        if name not in self.active_processes:
            return f"Ошибка: Субагент '{name}' не найден среди активных."
        
        obj = self.active_processes[name]["obj"]
        self.active_processes[name]["task"].cancel()
        
        await obj.die(final_status="killed_by_admin")
        del self.active_processes[name]
        
        msg = f"Субагент '{name}' был принудительно терминирован."
        system_logger.warning(f"[SwarmManager] {msg}")
        return msg

    async def get_swarm_status(self) -> str:
        if not self.active_processes:
            return "Активных процессов Swarm System нет."
        
        lines = []
        for name, info in self.active_processes.items():
            obj = info["obj"]
            status_str = f"- [{obj.role}] '{name}' | Status: {obj.status}"
            if hasattr(obj, "interval_sec") and obj.interval_sec:
                status_str += f" | Interval: {obj.interval_sec}s"
            status_str += f" | Task: {obj.instructions[:300]}..."
            lines.append(status_str)
        return "\n".join(lines)
    
    async def get_process_logs(self, name: str) -> str:
        if name not in self.active_processes:
            return f"Ошибка: Субагент '{name}' не активен."
        obj = self.active_processes[name]["obj"]
        if not obj.logs:
            return f"Логи субагента '{name}' пока пусты."
        return f"Внутренние логи субагента '{name}'\n" + "\n".join(obj.logs)
    
    async def update_subagent(self, name: str, instructions: str = None, trigger_condition: str = None, interval_sec: int = None) -> str:
        """Горячее обновление параметров субагента без его перезапуска"""
        if name not in self.active_processes:
            return f"Ошибка: Субагент '{name}' не найден среди активных процессов."
            
        obj = self.active_processes[name]["obj"]
        
        # Обновляем объекты в оперативной памяти
        changes = []
        if instructions is not None:
            obj.instructions = instructions
            changes.append("инструкции")
        if trigger_condition is not None and hasattr(obj, 'trigger_condition'):
            obj.trigger_condition = trigger_condition
            changes.append("триггер")
        if interval_sec is not None and hasattr(obj, 'interval_sec'):
            obj.interval_sec = interval_sec
            changes.append(f"интервал ({interval_sec} сек)")
            
        if not changes:
            return f"Субагент '{name}' не был изменен, так как не переданы новые параметры."
            
        # Обновляем в БД, чтобы настройки сохранились при рестарте системы
        await update_subagent_config(name, instructions, trigger_condition, interval_sec)
        
        msg = f"Субагент '{name}' успешно переконфигурирован. Изменено: {', '.join(changes)}."
        system_logger.info(f"[SwarmManager] {msg}")
        obj.add_log(f"Горячее обновление конфигурации: {', '.join(changes)}.")
        
        return msg

swarm_manager = SwarmManager()