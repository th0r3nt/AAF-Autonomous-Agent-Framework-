import aio_pika
from typing import Optional
from dotenv import load_dotenv

from src.l00_utils.managers.logger import system_logger

load_dotenv()


class RabbitMQConnection:
    """Менеджер соединений с RabbitMQ."""

    def __init__(self, url: str):
        self.url = url
        self.connection: Optional[aio_pika.RobustConnection] = None

    async def connect(self):
        """Устанавливает соединение с авто-реконнектом."""
        if self.connection and not self.connection.is_closed:
            return

        try:
            # connect_robust сам переподключится при моргании сети
            self.connection = await aio_pika.connect_robust(self.url)
            system_logger.info("[Broker] Успешное подключение к RabbitMQ.")
        except Exception as e:
            system_logger.error(f"[Broker] Критическая ошибка подключения к RabbitMQ: {e}")
            raise

    async def get_channel(self) -> aio_pika.abc.AbstractChannel:
        """Возвращает новый канал для работы (Publisher/Consumer)."""
        if not self.connection or self.connection.is_closed:
            await self.connect()

        # Канал - легковесное виртуальное соединение внутри TCP-коннекта
        return await self.connection.channel()

    async def close(self):
        """Корректно закрывает соединение при остановке системы."""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            system_logger.info("[Broker] Соединение с RabbitMQ закрыто.")
