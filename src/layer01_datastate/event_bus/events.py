from pydantic import BaseModel
from enum import Enum

# Описываем возможные уровни событий
class EventLevel(int, Enum):
    # int позволит сравнивать события (!>)
    CRITICAL = 50
    HIGH = 40
    MEDIUM = 30
    LOW = 20
    INFO = 0 # Системные, не для агента

# Описываем, как должно выглядеть ОДНО событие
class EventConfig(BaseModel):
    name: str
    description: str
    requires_attention: bool = True # По умолчанию считаем, что на события надо реагировать агенту
    level: EventLevel

    def __str__(self):
        return self.name

# Далее описываем события как объекты
class Events:

    # ============================================
    # Telegram
    # ============================================

    AGENT_NEW_INCOMING_MESSAGE_TG = EventConfig(
        name="AGENT_NEW_INCOMING_MESSAGE_TG",
        description="Новое личное сообщение на аккаунт агента",
        requires_attention=True,
        level=EventLevel.HIGH,
    )
    AGENT_NEW_MENTION_TG = EventConfig(
        name="AGENT_NEW_MENTION_TG",
        description="Упоминание агента в группе/чате",
        requires_attention=True,
        level=EventLevel.MEDIUM,
    )

    AGENT_MESSAGE_REACTION = EventConfig(
        name="AGENT_MESSAGE_REACTION",
        description="Кто-то поставил эмодзи-реакцию на сообщение агента в Telegram",
        requires_attention=True,
        level=EventLevel.LOW, # Пойдет в фоновые события
    )

    AGENT_NEW_GROUP_MESSAGE = EventConfig(
        name="AGENT_NEW_GROUP_MESSAGE",
        description="Обычное сообщение в группе/чате (без упоминания агента). Просто для информации.",
        requires_attention=True,
        level=EventLevel.LOW, 
    )


    # ============================================
    # Общие события
    # ============================================

    WEATHER_ALERT = EventConfig(
        name="WEATHER_ALERT",
        description="Резкое изменение погоды",
        requires_attention=True,
        level=EventLevel.MEDIUM,
    )
    START_SYSTEM = EventConfig(
        name="START_SYSTEM",
        description="Запуск всей системы с основного ПК.",
        requires_attention=True,
        level=EventLevel.HIGH,
    )
    STOP_SYSTEM = EventConfig(
        name="STOP_SYSTEM",
        description="Отключение всей системы",
        requires_attention=False,
        level=EventLevel.HIGH,
    )
    SYSTEM_MODULE_HEARTBEAT = EventConfig(
        name="SYSTEM_MODULE_HEARTBEAT",
        description="Системный модуль дает ping о том, что он живой",
        requires_attention=False, # Системное событие
        level=EventLevel.INFO,
    )
    SYSTEM_MODULE_ERROR = EventConfig(
        name="SYSTEM_MODULE_ERROR",
        description="Ошибка в системном модуле",
        requires_attention=True,
        level=EventLevel.CRITICAL,
    )


    # ============================================
    # Agent Swarm
    # ============================================
    
    SWARM_INFO = EventConfig(
        name="SWARM_INFO",
        description="Отчет от субагента об успешном выполнении задачи",
        requires_attention=True,
        level=EventLevel.MEDIUM, 
    )
    SWARM_ALERT = EventConfig(
        name="SWARM_ALERT",
        description="Уведомление от Daemon субагента (сработал триггер)",
        requires_attention=True,
        level=EventLevel.HIGH, 
    )
    SWARM_ERROR = EventConfig(
        name="SWARM_ERROR",
        description="Процесс роя упал с ошибкой",
        requires_attention=True,
        level=EventLevel.MEDIUM, 
    )


    # ============================================
    # Sandbox (Песочница)
    # ============================================
    
    SANDBOX_ATTENTION_REQUIRED = EventConfig(
        name="SANDBOX_ATTENTION_REQUIRED",
        description="Фоновый скрипт из песочницы прислал уведомление",
        requires_attention=True,
        level=EventLevel.HIGH,
    )

    EXTERNAL_WEBHOOK_RECEIVED = EventConfig(
        name="EXTERNAL_WEBHOOK_RECEIVED",
        description="Внешняя система прислала данные на сгенерированный агентом webhook-URL",
        requires_attention=True,
        level=EventLevel.HIGH, 
    )


    # ============================================
    # Deployments
    # ============================================

    DEPLOYMENT_CRASHED = EventConfig(
        name="DEPLOYMENT_CRASHED",
        description="Запущенный микросервис/проект упал с ошибкой",
        requires_attention=True,
        level=EventLevel.HIGH, 
    )
    

    # @classmethod дает методу первым аргументом cls (ссылку на класс), а не self (экземпляр)
    @classmethod
    def all(cls) -> list[EventConfig]:
        """Собирает все EventConfig из атрибутов класса"""
        events =[]

        for attr_name, attr_value in vars(cls).items(): # vars() - встроенная функция, берет внутренности класса и превращает в словарь
            # в этом словаре ключи - это названия переменных, значения - это в данном случае EventConfig
            if isinstance(attr_value, EventConfig):
                events.append(attr_value)

        return events

ALL_EVENTS = Events.all()
