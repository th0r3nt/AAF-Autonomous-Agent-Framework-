from typing import TYPE_CHECKING
import asyncio

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.event.models import EventEnvelope
from src.l02_state.manager import GlobalState

if TYPE_CHECKING:
    from src.l04_agency.main_agent.cycles.orchestrator import Orchestrator
    from src.l04_agency.main_agent.cycles.heartbeat import AgentHeartbeat


class EventDispatcher:
    """
    Слушает RabbitMQ, фильтрует спам, работает с буфером прерываний.
    При входящих событиях принимает решение: будить агента, отложить в память или кинуть в прерывание.
    """

    def __init__(
        self,
        orchestrator: "Orchestrator",
        global_state: GlobalState,
        heartbeat: "AgentHeartbeat",
    ):
        self.orchestrator = orchestrator
        self.state = global_state
        self.heartbeat = heartbeat

    async def handle_rabbitmq_event(self, envelope: EventEnvelope) -> bool:
        """
        Главный коллбэк для Consumer'а RabbitMQ.
        Возвращает True (событие обработано) или False (сбой).
        """
        routing_key = envelope.routing_key
        level = routing_key.split(".")[-1]  # critical, high, medium, low, background
        event_id = envelope.event_id

        is_timer = routing_key.startswith("system.timer")
        cycle_type = self._determine_cycle(envelope)

        system_logger.debug(f"[Event Dispatcher] Получено: {routing_key} (ID: {event_id})")

        # INTERRUPT BUFFER
        # Если агент занят > кладем в буфер прерывания
        if self.orchestrator.is_busy():
            # Если это таймер от Heartbeat - ставим в очередь ожидания
            if is_timer:
                asyncio.create_task(self.orchestrator.wake_up_neo(envelope, cycle_type))
                system_logger.info(
                    f"[Event Dispatcher] Агент занят. Цикл '{cycle_type}' поставлен в очередь ожидания."
                )
                return True

            # Иначе это реальное событие (ТГ, GitHub и тд), кидаем в буфер прерываний
            self.state.agency_state.interrupt_buffer.append(envelope)
            system_logger.info(
                f"[Event Dispatcher] Агент занят. Событие '{routing_key}' добавлено в Interrupt Buffer."
            )
            return True

        # ФИЛЬТРАЦИЯ ФОНОВЫХ СОБЫТИЙ
        # Если агент спит > кладем в буфер событий и ускоряем проактивность
        if level in ["medium", "low", "background"] and not is_timer:
            self._save_to_memory(envelope)
            self.heartbeat.reduce_proactivity_timer(level)

            system_logger.info(
                f"[Event Dispatcher] Фоновое событие ({level}) отложено в фоновую очередь."
            )
            return True

        # ВАЖНО: Синхронно бронируем агента, чтобы события, прилетевшие через
        # 1 миллисекунду, гарантированно ушли в Interrupt Buffer
        self.orchestrator._is_waking_up = True

        # Отправляем LLM думать в бэкграунд
        asyncio.create_task(self.orchestrator.wake_up_neo(envelope, cycle_type))

        # Мгновенно отдаем True консьюмеру, чтобы RabbitMQ сделал ACK
        # и продолжил бесперебойно слушать очередь в ожидании прерываний
        return True

    def _determine_cycle(self, envelope: EventEnvelope) -> str:
        """Определяет тип цикла мышления на основе ключа маршрутизации."""
        routing_key = envelope.routing_key

        if "consolidation" in routing_key:
            return "consolidation"
        if "proactivity" in routing_key:
            return "proactivity"

        return "event_driven"

    def _save_to_memory(self, envelope: EventEnvelope):
        """
        Сохраняет фоновые события в RAM-буфер агента.
        Позже ContextBuilder заберет их отсюда при сборке промпта.
        """
        self.state.agency_state.sensory_buffer.append(envelope)
