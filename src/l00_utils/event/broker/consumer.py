import json
from typing import Callable, Awaitable
import aio_pika

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.event.broker.connection import RabbitMQConnection
from src.l00_utils.event.models import EventEnvelope


class EventConsumer:
    """
    Cлушатель очередей. Обрабатывает ручное подтверждение (ACK/NACK)
    и защищает консьюмер от падений из-за кривых данных.
    """

    def __init__(self, conn: RabbitMQConnection, prefetch_count: int = 1):
        self.conn = conn
        # prefetch_count=1: Оркестратор берет строго 1 задачу за раз
        self.prefetch_count = prefetch_count
        self._channel: aio_pika.abc.AbstractChannel = None

    # Метод start_consuming будет вызываться из main.py
    # Мы передаем ему имя очереди (напр. q_event_driven) и коллбэк (функция orchestrator'а, которая принимает Envelope (конверт) и возвращает bool)
    async def start_consuming(
        self,
        queue_name: str,
        handler_callback: Callable[[EventEnvelope], Awaitable[bool]],
    ):
        """
        Подключается к очереди и начинает слушать.

        :param queue_name: Имя очереди (например, "q_event_driven").
        :param handler_callback: Асинхронная функция Оркестратора. Должна возвращать True (успех) или выкидывать Exception.
        """
        self._channel = await self.conn.get_channel()

        # Настраиваем QoS (Quality of Service)
        await self._channel.set_qos(prefetch_count=self.prefetch_count)

        # Берем очередь
        queue = await self._channel.get_queue(queue_name)

        system_logger.info(
            f"[RabbitMQ Consumer] Оркестратор начал прослушивание очереди '{queue_name}'."
        )

        # Начинаем бесконечный цикл обработки (consume) - как только в очереди появляется сообщение, мы его забираем
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                # Используем менеджер контекста process(), он автоматически сделает ACK/NACK
                # Под капотом, если внутри with вылетит Exception, aio-pika сделает message.reject(requeue=True)
                async with message.process(requeue=True, ignore_processed=True):
                    try:
                        # 1. Пытаемся распарсить JSON в строгую Pydantic модель
                        raw_data = json.loads(message.body.decode("utf-8"))
                        envelope = EventEnvelope(**raw_data)

                    except Exception as e:
                        # Если формат сломан, сообщение отравлено (Poison Pill).
                        system_logger.error(
                            f"[RabbitMQ Consumer] Критическая ошибка десериализации. Сообщение убито: {e}"
                        )
                        # Reject(requeue=False) мгновенно выбрасывает сообщение на Кладбище (DLX) без 3-х попыток
                        await message.reject(requeue=False)
                        continue  # Идем к следующему сообщению

                    # 2. Передаем конверт в мозг агента - Оркестратор
                    system_logger.debug(
                        f"[RabbitMQ Consumer] Взято в работу событие: {envelope.routing_key} [{envelope.event_id}]"
                    )

                    try:
                        # Запускаем бизнес-логику агента
                        success = await handler_callback(envelope)

                        if success:
                            # Если Оркестратор вернул True, мы вручную подтверждаем успех
                            await message.ack()
                            system_logger.debug(
                                f"[RabbitMQ Consumer] Успех (ACK): {envelope.event_id}"
                            )
                        else:
                            # Если Оркестратор (main_agent/cycles/orchestrator.py) вернул False (логическая ошибка, не Exception)
                            system_logger.warning(
                                "[RabbitMQ Consumer] Оркестратор вернул False. Возврат в очередь (NACK)."
                            )
                            await message.reject(requeue=True)

                    except Exception as handler_error:
                        # Если упало API LLM, БД или докер-песочница
                        system_logger.error(
                            f"[RabbitMQ Consumer] Сбой в Оркестраторе (NACK). Событие {envelope.event_id}: {handler_error}"
                        )
                        # Выбрасываем ошибку дальше, чтобы менеджер контекста `with message.process()` сделал requeue=True
                        raise handler_error
