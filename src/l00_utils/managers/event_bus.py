from typing import Any

from src.l00_utils.event.broker.publisher import EventPublisher
from src.l00_utils.event.registry import EventConfig
from src.l00_utils.managers.logger import system_logger


class EventBus:
    """
    Главная шина событий.
    Объединяет локальные подписки (в памяти) и маршрутизацию внешних событий в RabbitMQ.
    """

    def __init__(self):
        # Паблишер инициализируется позже (избегаем циклических импортов)
        self.publisher: EventPublisher | None = None

    def set_publisher(self, publisher: EventPublisher) -> None:
        """Ленивая инициализация RabbitMQ-паблишера."""
        self.publisher = publisher

    async def publish(
        self,
        event: EventConfig,
        source: str = "system",
        metadata: dict = None,
        **kwargs: Any,
    ) -> None:
        """
        Публикует событие.
        Сначала синхронно/асинхронно дергает все локальные функции-подписчики,
        затем кидает конверт с данными (kwargs) в RabbitMQ.
        """
        # Отправка в RabbitMQ (если брокер подключен)
        if self.publisher:
            try:
                await self.publisher.publish(
                    event_config=event,
                    source=source,
                    metadata=metadata or {},
                    data=kwargs,  # Все переданные параметры уходят в payload (data)
                )
            except Exception as e:
                system_logger.error(
                    f"[EventBus] Ошибка публикации {event.name} в RabbitMQ: {e}"
                )
