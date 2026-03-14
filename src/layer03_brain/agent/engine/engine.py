import time
import asyncio
from dataclasses import dataclass, field
from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog import event_driven_module, proactivity_module, thoughts_module
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events
from src.layer03_brain.agent.engine.react_management import react_cycles
from src.layer03_brain.agent.engine.state import brain_state


@dataclass(order=True)
class BrainTask:
    # 1 - EVENT, 2 - PROACTIVE, 3 - THOUGHTS
    priority: int
    task_type: str = field(compare=False)
    payload: dict = field(compare=False, default_factory=dict)

class BrainEngine:
    def __init__(self):
        self.queue = asyncio.PriorityQueue()
        self.proactivity_interval = config.rhythms.proactivity_interval_sec
        self.thoughts_interval = config.rhythms.thoughts_interval_sec

        # Настройки умной проактивности
        self.min_cooldown = config.rhythms.min_proactivity_cooldown_sec
        self.reduction_medium = config.rhythms.reduction_medium_sec
        self.reduction_low = config.rhythms.reduction_low_sec
        
        # Таймеры
        self.last_proactive_time = time.time()
        self.target_proactive_time = self.last_proactive_time + self.proactivity_interval

    def nudge_proactivity(self, level: str):
        """Ускоряет наступление следующего цикла проактивности при входящих событиях уровня MEDIUM, LOW"""
        if level == "MEDIUM":
            reduction = self.reduction_medium
        elif level == "LOW":
            reduction = self.reduction_low
        else:
            return

        now = time.time()
        new_target = self.target_proactive_time - reduction
        
        # Защита: не запускать чаще, чем разрешает min_cooldown
        earliest_possible = self.last_proactive_time + self.min_cooldown
        
        if new_target < earliest_possible:
            new_target = earliest_possible
            
        # Если время уже подошло, таргетом становится "прямо сейчас" (но с учетом кулдауна)
        if new_target < now:
            new_target = max(now, earliest_possible)

        # Обновляем, только если реально приблизили запуск
        if new_target < self.target_proactive_time:
            self.target_proactive_time = new_target
            seconds_left = max(0, int(self.target_proactive_time - now))
            if level == "MEDIUM":
                system_logger.info(f"[BrainEngine] Фоновое событие (уровень: {level}) ускорило проактивность. До запуска: {seconds_left} сек.")
            else:
                system_logger.debug(f"[BrainEngine] Фоновое событие (уровень: {level}) ускорило проактивность. До запуска: {seconds_left} сек.")
        
    async def add_event_to_queue(self, event, args, kwargs):
        """Интерфейс для EventsMonitoring: кидает входящее событие в очередь обработки задач"""
        task = BrainTask(
            priority=1,
            task_type="EVENT",
            payload={"event": event, "args": args, "kwargs": kwargs}
        )
        await self.queue.put(task)

        args_str = str(args)
        kwargs_str = str(kwargs)
        
        limit = 150
        safe_args = (args_str[:limit] + '... [Обрезано]') if len(args_str) > limit else args_str
        safe_kwargs = (kwargs_str[:limit] + '... [Обрезано]') if len(kwargs_str) > limit else kwargs_str

        system_logger.info(f"[BrainEngine] Входящее событие '{event.name}' добавлено в очередь. Args: {safe_args}; Kwargs: {safe_kwargs}")


    # ---------------------------------------------------------
    # ФОНОВЫЕ ЦИКЛЫ
    async def _proactivity_ticker(self):
        """Фоновый процесс: умный поллинг (каждую секунду) для вызова проактивности"""
        if not config.system.flags.enable_proactivity:
            system_logger.info("[BrainEngine] Проактивный цикл отключен в настройках (settings.yaml).")
            return

        while True:
            await asyncio.sleep(1) # Дешевый поллинг
            now = time.time()
            # ... (дальше твой код без изменений)
            if now >= self.target_proactive_time:
                self.last_proactive_time = now
                self.target_proactive_time = now + self.proactivity_interval
                await self.queue.put(BrainTask(priority=2, task_type="PROACTIVE"))

    async def _thoughts_ticker(self):
        """Фоновый процесс: кидает задачу на интроспекцию в очередь"""
        if not config.system.flags.enable_thoughts:
            system_logger.info("[BrainEngine] Цикл интроспекции отключен в настройках (settings.yaml).")
            return

        while True:
            await asyncio.sleep(self.thoughts_interval)
            await self.queue.put(BrainTask(priority=3, task_type="THOUGHTS"))


    # ---------------------------------------------------------
    # ОРКЕСТРАТОР
    async def run_worker_loop(self):
        """Цикл, следящий за очередью выполнения задач"""
        system_logger.info("[BrainEngine] Центральный цикл мозга запущен.")

        await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=event_driven_module, status="ON")
        await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=proactivity_module, status="ON")
        await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=thoughts_module, status="ON")

        brain_state["status"] = "thinking"
        
        while True:
            task = await self.queue.get()
            system_logger.info(f"[BrainEngine] Выполнение задачи: {task.task_type} (Priority: {task.priority})")

            try:
                # Маршрутизируем задачу в нужный обработчик
                if task.task_type == "EVENT":
                    await react_cycles.respond_to_event(**task.payload)
                elif task.task_type == "PROACTIVE":
                    await react_cycles.run_proactivity()
                elif task.task_type == "THOUGHTS":
                    await react_cycles.run_thoughts()

            except Exception as e:
                system_logger.error(f"[BrainEngine] Ошибка при выполнении задачи {task.task_type}: {e}")

                failed_module = event_driven_module
                if task.task_type == "PROACTIVE":
                    failed_module = proactivity_module
                elif task.task_type == "THOUGHTS":
                    failed_module = thoughts_module

                await event_bus.publish(Events.SYSTEM_MODULE_ERROR, module_name=failed_module, status="ERROR", error_msg=str(e))

            finally:
                brain_state["status"] = "sleeping"
                brain_state["step"] = 0
                brain_state["action"] = "None"
                self.queue.task_done()

    async def run_loops(self):
        """Запускает цикл очереди выполнения задач и фоновые таймеры"""
        asyncio.create_task(self._proactivity_ticker())
        asyncio.create_task(self._thoughts_ticker())
        await self.run_worker_loop()

brain_engine = BrainEngine()