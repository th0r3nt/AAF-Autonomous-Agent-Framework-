import aio_pika
from src.l00_utils.managers.logger import system_logger


class RabbitMQTopology:
    """
    Архитектор брокера. Отвечает за создание инфраструктуры:
    Exchange, Queues, DLX  и настройку маршрутизации.
    """

    def __init__(
        self,
        channel: aio_pika.abc.AbstractChannel,
        exchange_events: str = "aaf_events",
        exchange_dlx: str = "aaf_dlx",
        queue_dlq: str = "q_dead_letters",
        queue_event_driven: str = "q_event_driven",
        queue_proactivity: str = "q_proactivity",
        queue_system: str = "q_system",
    ):
        self.channel = channel

        # Создаем названия сортировочных центров, Exchanges
        self.exchange_events = exchange_events
        self.exchange_dlx = exchange_dlx

        # Создаем названия очередей, Queues
        self.queue_dlq = queue_dlq
        self.queue_event_driven = queue_event_driven
        self.queue_proactivity = queue_proactivity
        self.queue_system = queue_system

        # Общие настройки рабочих очередей агента
        self.agent_queue_args = {  # Защита от бесконечных падений
            "x-queue-type": "quorum",  # Движок очередей, Raft
            "x-dead-letter-exchange": self.exchange_dlx,  # Куда отправлять трупы
            "x-dead-letter-routing-key": "poison_pill",  # С какой биркой
            "x-delivery-limit": 3,  # Убивать письмо после 3 неудачных попыток
        }

    async def setup(self):
        """Главный метод. Вызывает строителей по очереди."""
        system_logger.info("[Broker] Инициализация топологии RabbitMQ.")

        # Создаем Обменники
        events_exch, dlx_exch = await self._declare_exchanges()

        # Создаем Кладбище
        await self._declare_dlq(dlx_exch)

        # Создаем рабочие очереди и настраиваем маршрутизацию
        await self._declare_agent_queues(events_exch)

        system_logger.info("[Broker] Топология RabbitMQ успешно построена.")

    # ======================================================
    # СЛУЖЕБНЫЕ МЕТОДЫ
    # ======================================================

    async def _declare_exchanges(self):
        """Создает главный хаб и хаб для кладбища."""
        # Главный роутер (topic позволяет использовать маски * и #)
        events_exchange = await self.channel.declare_exchange(
            name=self.exchange_events, type=aio_pika.ExchangeType.TOPIC, durable=True
        )

        # Роутер Кладбища (direct - прямая маршрутизация по точному совпадению)
        dlx_exchange = await self.channel.declare_exchange(
            name=self.exchange_dlx, type=aio_pika.ExchangeType.DIRECT, durable=True
        )
        return events_exchange, dlx_exchange

    async def _declare_dlq(self, dlx_exchange: aio_pika.abc.AbstractExchange):
        """Создает корзину для ядовитых сообщений."""
        graveyard_queue = await self.channel.declare_queue(name=self.queue_dlq, durable=True)
        # Все сообщения с биркой "poison_pill", попавшие в dlx_exchange, летят сюда
        await graveyard_queue.bind(exchange=dlx_exchange, routing_key="poison_pill")

    async def _declare_agent_queues(self, events_exchange: aio_pika.abc.AbstractExchange):
        """Создает боевые корзины и привязывает их к главному хабу по приоритетам."""

        # Очередь Event-Driven (срочные дела: упоминания, ошибки)
        q_event = await self.channel.declare_queue(
            name=self.queue_event_driven, durable=True, arguments=self.agent_queue_args
        )
        await q_event.bind(exchange=events_exchange, routing_key="*.*.*.critical")
        await q_event.bind(exchange=events_exchange, routing_key="*.*.*.high")

        # Очередь Proactivity (фон для свободного времени: лайки, новые посты)
        q_proact = await self.channel.declare_queue(
            name=self.queue_proactivity, durable=True, arguments=self.agent_queue_args
        )
        await q_proact.bind(exchange=events_exchange, routing_key="*.*.*.medium")
        await q_proact.bind(exchange=events_exchange, routing_key="*.*.*.low")
        await q_proact.bind(exchange=events_exchange, routing_key="*.*.*.background")

        # Очередь System (Чисто технические логи, пишутся напрямую в базу без LLM)
        q_sys = await self.channel.declare_queue(
            name=self.queue_system, durable=True, arguments=self.agent_queue_args
        )
        await q_sys.bind(exchange=events_exchange, routing_key="*.*.*.info")
