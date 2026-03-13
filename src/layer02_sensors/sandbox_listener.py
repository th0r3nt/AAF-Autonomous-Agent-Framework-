from aiohttp import web
from src.layer00_utils.logger import system_logger
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events

async def handle_alert(request):
    try:
        data = await request.json()
        message = data.get("message", "Без текста")
        
        # Публикуем событие в шину
        await event_bus.publish(Events.SANDBOX_ATTENTION_REQUIRED, alert_message=message)
        system_logger.info(f"[Sandbox Listener] Получен алерт от скрипта: {message}")
        
        return web.Response(text="OK")
    except Exception as e:
        system_logger.error(f"[Sandbox Listener] Ошибка обработки алерта: {e}")
        return web.Response(status=400, text="Bad Request")

async def start_sandbox_listener():
    """Запускает фоновый aiohttp сервер для приема сигналов от скриптов"""
    app = web.Application()
    app.router.add_post('/alert', handle_alert)
    
    runner = web.AppRunner(app)
    await runner.setup()
    # Слушаем только локалхост, чтобы извне никто не мог дергать агента
    site = web.TCPSite(runner, '127.0.0.1', 18790)
    await site.start()
    system_logger.info("[Sandbox Listener] Сервер приема уведомлений от локальных скриптов Sandbox запущен на порту 18790.")