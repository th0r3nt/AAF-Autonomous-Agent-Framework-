import asyncio
from config.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events
from src.layer00_utils.watchdog.watchdog import userbot_telethon_module
from src.layer02_sensors.telegram.agent_account.client import agent_client
from src.layer02_sensors.telegram.agent_account.events import register_agent_events
from telethon.tl.functions.account import UpdateStatusRequest

from telethon.tl.functions.account import UpdateProfileRequest

# Специальное событие asyncio, чтобы держать клиент открытым
_tg_stop_event = asyncio.Event()
# asyncio.Event - встроенный в Python механизм для синхронизации асинхронных задач. У него есть два состояния. Приводя аналогию с двоичной системой: "0" (по умолчанию) и "1"

async def set_agent_status(status: str):
    """Меняет фамилию агента на [online] или [offline], сохраняя текущее имя"""
    try:
        # Получаем текущие данные профиля
        me = await agent_client.get_me()
        
        # Если имя почему-то пустое, берем дефолтное из конфига
        current_first_name = getattr(me, 'first_name', config.identity.agent_name)
        if not current_first_name:
            current_first_name = config.identity.agent_name
            
        await agent_client(UpdateProfileRequest(
            first_name=current_first_name,
            last_name=f"[{status}]"
        ))
        system_logger.info(f"[Telegram Telethon] Статус профиля аккаунта агента изменен на: [{status}]")
    except Exception as e:
        system_logger.warning(f"[Telegram Telethon] Не удалось изменить статус профиля агента: {e}")

async def stop_telegram(*args, **kwargs):
    system_logger.info("[Telegram Telethon] Отключение клиента...")
    if agent_client.is_connected():
        await set_agent_status("offline")
        # На всякий принудительно ставим статус offline
        await agent_client(UpdateStatusRequest(offline=True)) # Статус online может висеть несколько минут, чертов протокол MTProto
        await agent_client.disconnect()
    
    _tg_stop_event.set() # Отпускаем блокировку
    system_logger.info("[Telegram Telethon] Клиент успешно отключен.")

async def setup_telegram():
    system_logger.info("[Telegram Telethon] Запуск клиента.")
    event_bus.subscribe(Events.STOP_SYSTEM, stop_telegram)
    
    try:
        await agent_client.connect()
        
        if not await agent_client.is_user_authorized():
            error_msg = "Telegram-сессия не авторизована! Запустите 'python src/layer00_utils/auth_tg.py' для входа."
            system_logger.critical(f"[Telegram Telethon] {error_msg}")
            await event_bus.publish(Events.SYSTEM_MODULE_ERROR, module_name=userbot_telethon_module, status="ERROR", error_msg=error_msg)
            return

        await set_agent_status("online")

        system_logger.info("[Telegram Telethon] Agent Client запущен.")
        register_agent_events(agent_client)

        await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=userbot_telethon_module, status="ON")

        # Вместо run_until_disconnected() ждем нашего собственного сигнала STOP_SYSTEM
        try:
            await _tg_stop_event.wait()
        except asyncio.CancelledError:
            # Если процесс убили жестко (например, закрыли окно крестиком)
            if agent_client.is_connected():
                await set_agent_status("offline")
                await agent_client.disconnect()
            raise

    except Exception as e:
        await event_bus.publish(Events.SYSTEM_MODULE_ERROR, module_name=userbot_telethon_module, status="ERROR", error_msg=str(e))
        system_logger.error(f"[Telegram Telethon] Ошибка: {e}")