import asyncio
import inspect
from typing import Any
from src.layer00_utils.logger import system_logger

class EventBus:
    def __init__(self):
        self.listeners = {}
        self.background_tasks = set() # Для Garbage Collector: сохраняем список всех задач в фоне, чтобы их не убили

    async def _run_handlers(self, tasks: list, event: str) -> None:
        """Запускает задачи и ловит ошибки, чтобы шина не упала"""
        results = await asyncio.gather(*tasks, return_exceptions=True) # gather берет все переданные таски и выполняет их фоново
        
        # Обработка "съеденных" ошибок
        for res in results:
            if isinstance(res, Exception):
                system_logger.error(f"Ошибка в обработчике события '{event}': {res}")

    def subscribe(self, event: str, handler) -> None:
        """Подписывает функцию на определенное событие"""
        event = str(event)
        if event not in self.listeners:
            self.listeners[event] = []
        
        self.listeners[event].append(handler)
        system_logger.debug(f"Подписка: функция '{handler.__name__}' -> событие '{event}'")

    async def publish(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Публикует событие и активирует все функции, которые подписаны на это событие"""
        event = str(event)
        if event not in self.listeners:
            system_logger.debug(f"На событие '{event}' никто не подписан.")
            return
        
        handlers = self.listeners[event]
        tasks = [] # Создаем список корутин
        
        for handler in handlers:
            if inspect.iscoroutinefunction(handler):
                coro = handler(*args, event=event, **kwargs) # При вызове функции, помеченной как async def, ее тело не начинает выполняться - Python только возвращает объект-корутину
                system_logger.debug(f"Функция {handler.__name__} (args={args}, kwargs={kwargs}) вызвана.")
                tasks.append(coro)
                
            else: 
                tasks.append(asyncio.to_thread(handler, *args, event=event, **kwargs)) # asyncio.to_thread - современный метод 

        if tasks:
            background_task = asyncio.create_task(
                self._run_handlers(tasks, event) # Вызываем служебную функцию в фоне
            )

            self.background_tasks.add(background_task)
            background_task.add_done_callback(self.background_tasks.discard)

    def unsubscribe(self, event: str, handler) -> None:
        """Отписывает функцию от события"""
        if event in self.listeners:
            try:
                self.listeners[event].remove(handler)
                system_logger.debug(f"Функция {handler.__name__} отписана от события {event}")
            except ValueError:
                pass 

event_bus = EventBus()
