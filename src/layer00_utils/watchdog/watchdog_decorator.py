import asyncio
import inspect
from functools import wraps
import traceback
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events

SYSTEM_MODULE_HEARTBEAT = Events.SYSTEM_MODULE_HEARTBEAT
SYSTEM_MODULE_ERROR = Events.SYSTEM_MODULE_ERROR

# Все возможные module_name описаны в watchdog.py
def watchdog_decorator(module_name):
    """Публикует событие SYSTEM_MODULE_HEARTBEAT после успешного выполнения функции; 
    В случае ошибки публикует событие SYSTEM_MODULE_ERROR"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Проверяем, асинхронная ли функция
                if inspect.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    # Если синхронная (как ChromaDB), запускаем в отдельном потоке, 
                    # чтобы не стопить весь мозг
                    result = await asyncio.to_thread(func, *args, **kwargs)
                
                await event_bus.publish(SYSTEM_MODULE_HEARTBEAT, module_name=module_name, status="ON")
                return result
            except Exception as e:
                # Получаем последние 3 строчки трейсбека (где именно упало)
                tb = traceback.format_exc(limit=-3)
                error_details = f"{e} \nTraceback:\n{tb}"
                
                await event_bus.publish(SYSTEM_MODULE_ERROR, module_name=module_name, status="ERROR", error_msg=error_details)
                raise e
        return wrapper
    return decorator

# Пометка: Декораторы отлично работают для функций, которые "сделали дело -> вернули результат" (например, запись в SQL)
# Но для фоновых демонов (демоны слушают микрофон, ждут сообщений в ТГ) декораторы не подходят, потому что демоны никогда не возвращают return
# Поэтому в бесконечных циклах надо публиковать SYSTEM_MODULE_HEARTBEAT вручную, при запуске демона и (по возможности) в процессе работы