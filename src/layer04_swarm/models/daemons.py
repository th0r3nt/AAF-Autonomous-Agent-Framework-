import asyncio
from src.layer00_utils.config_manager import config
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events
from src.layer01_datastate.sql_db.management.swarm_state import update_subagent_status
from src.layer04_swarm.models.base import BaseSubagent
from src.layer04_swarm.engine import run_subagent_react

class BaseDaemon(BaseSubagent):
    def __init__(self, db_record):
        super().__init__(db_record)
        self.trigger_condition = db_record.trigger_condition
        self.interval_sec = db_record.interval_sec or 60

    async def run(self):
        self.add_log(f"Daemon запущен. Интервал проверок: {self.interval_sec} сек.")
        try:
            while True:
                self.add_log("Пробуждение. Проверка условия.")
                await update_subagent_status(self.name, "running")
                
                result = await run_subagent_react(self, "Выполни проверку условия прямо сейчас.")

                # Если демон делегировал задачу или поднял панику, сбрасываем флаги и спим
                if getattr(self, 'is_delegated', False) or getattr(self, 'is_escalated', False):
                    self.is_delegated = False
                    self.is_escalated = False
                    self.add_log("Цикл прерван (эстафета/эскалация). Уход в сон.")
                else:
                    self.add_log(f"Проверка завершена. Результат: {result[:200]}")
                    
                self.add_log(f"Уход в сон на {self.interval_sec} сек.")
                await update_subagent_status(self.name, "sleeping")
                await asyncio.sleep(self.interval_sec)
                
                self.add_log(f"Проверка завершена. Результат: {result[:200]}")
                self.add_log(f"Уход в сон на {self.interval_sec} сек.")
                await update_subagent_status(self.name, "sleeping")
                await asyncio.sleep(self.interval_sec)
                
        except asyncio.CancelledError:
            await self.die(final_status="killed")
            raise
        except Exception as e:
            self.add_log(f"Критическая ошибка: {e}")
            await event_bus.publish(Events.SWARM_ERROR, source=self.name, error=str(e))
            await self.die(final_status="error")

class WebMonitor(BaseDaemon):
    def __init__(self, db_record):
        super().__init__(db_record)
        self.allowed_tools = [
            "web_search", "read_webpage", "trigger_swarm_alert", "set_memory_key", "get_memory_key",
            "delegate_task_to_swarm", "escalate_to_lead", "write_local_file", "read_sandbox_file"
        ]
        self.system_prompt = f"""
Ты фоновый Web-Daemon '{self.name}', бессмертный субагент Agent Swarm System. твой главный агент - {config.identity.agent_name}.
Твоя задача: {self.instructions}
Условие для тревоги (триггер): {self.trigger_condition}

Правила исполнения:
1. Автономный цикл: проснулся -> собрал данные -> сравнил -> уснул.
2. Сбор данных: проверь целевой ресурс (используй поиск или чтение страницы).
3. Память: Обязательно используй 'get_memory_key', чтобы достать данные с прошлой проверки.
4. Сравнение: сравни новые данные со старыми. 
5. Действие при ТРИГГЕРЕ: Если условие выполнилось - НЕМЕДЛЕННО вызови инструмент 'trigger_swarm_alert' и передай туда подробный и исчерпывающий отчет о событии.
6. Обновление состояния: Обязательно используй 'set_memory_key', чтобы сохранить новые данные для следующего цикла проверки.
7. Выход: Если триггер не сработал, просто верни текстовый ответ: "Изменений нет. Условие не выполнено".

Протокол эстафеты (Agentic Mesh):
- Если для выполнения задачи тебе нужен другой специалист (например, ты нашел код, и его нужно проанализировать), ты ОБЯЗАН заспавнить его через 'delegate_task_to_swarm'.
- ПРАВИЛО ПАМЯТИ: Перед делегированием обязательно сохрани все найденные данные в текстовый файл в песочнице (используй 'write_local_file'), а в инструкциях для нового агента укажи имя этого файла, чтобы он его прочитал.
- Если задача невыполнима или произошла критическая аномалия, используй 'escalate_to_lead', чтобы разбудить главного агента.
"""