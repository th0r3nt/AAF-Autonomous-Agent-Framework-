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
        system_logger.info(f"[Sandbox Listener] Получено уведоление от скрипта: {message}")
        
        return web.Response(text="OK")
    except Exception as e:
        system_logger.error(f"[Sandbox Listener] Ошибка обработки уведомления: {e}")
        return web.Response(status=400, text="Bad Request")

async def handle_webhook(request):
    """Обработчик для входящих данных от внешних сервисов"""
    topic_name = request.match_info.get('topic_name', 'unknown_topic')
    try:
        # Пытаемся прочитать как JSON, если не выйдет - как обычный текст
        try:
            payload = await request.json()
        except Exception:
            payload = await request.text()
            
        await event_bus.publish(Events.EXTERNAL_WEBHOOK_RECEIVED, topic_name=topic_name, payload=payload)
        system_logger.info(f"[Sandbox Listener] Получен внешний Webhook (Топик: {topic_name})")
        
        return web.Response(text='{"status": "received"}', content_type='application/json')
    except Exception as e:
        system_logger.error(f"[Sandbox Listener] Ошибка обработки webhook '{topic_name}': {e}")
        return web.Response(status=500, text="Internal Server Error")

async def start_sandbox_listener():
    """Запускает фоновый aiohttp сервер для приема сигналов"""
    app = web.Application()
    app.router.add_post('/alert', handle_alert)
    app.router.add_post('/webhook/{topic_name}', handle_webhook) # Регистрация маршрута хука
    app.router.add_get('/webhook/{topic_name}', handle_webhook)  # На всякий случай разрешаем и GET
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 18790) 
    await site.start()
    system_logger.info("[Sandbox Listener] Сервер приема уведомлений запущен на порту 18790.")