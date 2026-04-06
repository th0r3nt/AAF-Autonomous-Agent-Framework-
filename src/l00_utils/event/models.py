import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    """
    Универсальный конверт события для RabbitMQ.
    Все интерфейсы обязаны паковать данные в эту модель.
    """

    # Уникальный ID события. Служит ключом идемпотентности (чтобы не обрабатывать дубли)
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Ключ маршрутизации Кролика (домен.сущность.действие.приоритет)
    routing_key: str

    # Источник события (напр. telegram, github, system, vfs)
    source: str

    # Время создания события в UTC
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Метаданные (напр. ID чата, нужно ли отвечать, служебная инфа)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Чистая полезная нагрузка (текст сообщения, ссылки, пути к файлам)
    data: Dict[str, Any] = Field(default_factory=dict)

    def __str__(self):
        return f"<EventEnvelope {self.routing_key} [{self.event_id}]>"
