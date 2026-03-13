from collections import deque
from src.layer00_utils.logger import system_logger
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import ALL_EVENTS, EventLevel, EventConfig, Events
from src.layer03_brain.agent.engine.engine import brain_engine
from src.layer00_utils.watchdog.watchdog import events_monitoring_module

class EventsMonitoring:
    def __init__(self) -> None:
        self.events_quantity = 0
        self.background_events = deque(maxlen=50) # Записываем все входящие события, которые обладают низкой важностью

    async def events_handler(self, *args, event: EventConfig = None, **kwargs) -> None:
        """Обрабатывает каждое входящее событие, сортирует по важности"""
        # Чертова абстракция, я потратил всю глюкозу мозга на обдумывание этой архитектуры

        # Ищем объект конфигурации по имени (которое прислал EventBus)
        event_config = getattr(Events, event, None)
        
        if not event_config:
            system_logger.warning(f"Получено неизвестное событие: {event}")
            return

        # Теперь используем event_config вместо event
        if event_config.level == EventLevel.CRITICAL:
            await brain_engine.add_event_to_queue(event_config, args, kwargs)

        elif event_config.level == EventLevel.HIGH:
            await brain_engine.add_event_to_queue(event_config, args, kwargs)

        elif event_config.level == EventLevel.MEDIUM:
            postponed_event = {"event": event_config, "args": args, "kwargs": kwargs}
            self.background_events.append(postponed_event)
            brain_engine.nudge_proactivity("MEDIUM")

        elif event_config.level == EventLevel.LOW:
            # Игнорируем фоновые сообщения из групп, чтобы не дублировать историю диалогов
            if event_config.name not in ["AGENT_NEW_GROUP_MESSAGE", "AGENT_MESSAGE_REACTION"]:
                postponed_event = {"event": event_config, "args": args, "kwargs": kwargs}
                self.background_events.append(postponed_event)
            brain_engine.nudge_proactivity("LOW")

        elif event_config.level == EventLevel.INFO:
            pass

        else:
            system_logger.warning("Событие не передано.")

        await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=events_monitoring_module, status="ON")

    async def setup_monitoring(self) -> None:
        """Запускает мониторинг входящий событий с Event Bus"""
        for event in ALL_EVENTS:
            # Запускаем мониторинг только тех событий, которые требуют внимания агента
            if event.requires_attention:
                event_bus.subscribe(event, self.events_handler)
                self.events_quantity += 1

        system_logger.info(f"[Brain] Мониторинг входящих событий запущен: подписано {self.events_quantity} типов событий.")
        await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=events_monitoring_module, status="ON")

    async def get_background_events(self) -> str:
        """Возвращает список отформатированных строк событий с обрезкой длинных текстов"""
        lines = []
        for event in self.background_events:
            # Безопасно копируем kwargs, чтобы не изменить оригинал
            safe_kwargs = dict(event['kwargs'])
            
            # Если в событии есть длинный текст (например, пост из канала), обрезаем его
            if 'text' in safe_kwargs and isinstance(safe_kwargs['text'], str):
                if len(safe_kwargs['text']) > 150:
                    safe_kwargs['text'] = safe_kwargs['text'][:150] + "... [Обрезано]"
            
            # Если есть результат от субагента, даем ему большой лимит (3000 символов), чтобы главный агент мог прочитать отчет, а не выдумывать его
            if 'result' in safe_kwargs and isinstance(safe_kwargs['result'], str):
                if len(safe_kwargs['result']) > 5000:
                    safe_kwargs['result'] = safe_kwargs['result'][:5000] + "\n... [Остаток отчета воркера обрезан для экономии токенов]"

            kwargs_str = str(safe_kwargs)
            lines.append(f"[{event['event'].name}] args: {event['args']}, kwargs: {kwargs_str}")
        
        return "\n".join(lines) if lines else "Нет фоновых событий."



events_monitoring = EventsMonitoring()