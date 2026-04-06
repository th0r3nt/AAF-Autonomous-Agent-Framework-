import aio_pika
from typing import Optional

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.event.broker.connection import RabbitMQConnection
from src.l00_utils.event.models import EventEnvelope
from src.l00_utils.event.registry import EventConfig


class EventPublisher:
    """
    Интерфейс для публикации событий в RabbitMQ.
    """

    def __init__(self, conn: RabbitMQConnection, exchange_name: str = "aaf_events"):
        self.conn = conn
        self.exchange_name = exchange_name
        self._channel: Optional[aio_pika.abc.AbstractChannel] = None
        self._exchange: Optional[aio_pika.abc.AbstractExchange] = None

    async def _ensure_exchange(self):
        """Ленивая инициализация: получаем канал и Exchange только при первом запросе."""
        if not self._channel or self._channel.is_closed:
            self._channel = await self.conn.get_channel()
            # Берем уже созданный Exchange
            self._exchange = await self._channel.get_exchange(self.exchange_name)

    async def publish(
        self,
        event_config: EventConfig,
        source: str,
        metadata: dict = None,
        data: dict = None,
    ) -> str:
        """
        Упаковывает сырые данные в EventEnvelope и отправляет в брокер.

        :param event_config: Объект из реестра событий (Events.TELEGRAM_MESSAGE_INCOMING).
        :param source: Источник (например, "telegram_bot" или "github_polling").
        :param metadata: Служебная инфа (ID чата, флаги).
        :param data: Полезная нагрузка (текст сообщения, ссылки).
        :return: ID отправленного события (UUID).
        """
        await self._ensure_exchange()  # Первым делом дергаем _ensure_exchange, чтобы убедиться, что канал для отправки готов

        # Валидация и упаковка через Pydantic
        envelope = EventEnvelope(
            routing_key=event_config.routing_key,
            source=source,
            metadata=metadata or {},
            data=data or {},
        )

        # Сериализация в JSON
        # Используем .model_dump_json() вместо json.dumps для корректной работы с датами (datetime)
        payload_bytes = envelope.model_dump_json().encode("utf-8")

        # Формирование AMQP-сообщения
        message = aio_pika.Message(
            body=payload_bytes,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,  # Сохранять на диск (выживет при рестарте RabbitMQ)
            content_type="application/json",
            message_id=envelope.event_id,  # Для трекинга
        )

        try:
            # Публикация в Exchange
            await self._exchange.publish(message=message, routing_key=envelope.routing_key)

            system_logger.debug(
                f"[Publisher] Событие {envelope.routing_key} отправлено (ID: {envelope.event_id})"
            )
            return envelope.event_id

        except Exception as e:
            system_logger.error(
                f"[Publisher] Ошибка публикации события {envelope.routing_key}: {e}"
            )
            raise e
