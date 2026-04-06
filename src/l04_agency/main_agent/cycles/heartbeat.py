import asyncio
import time  # Добавили модуль time
from src.l00_utils.managers.logger import system_logger
from src.l00_utils.event.registry import Events
from src.l00_utils.managers.event_bus import EventBus
from src.l02_state.manager import GlobalState


class AgentHeartbeat:
    """
    Пульсирует в фоне, отсчитывает время и кидает события проактивности/консолидации в шину.
    Умеет динамически ускорять ритм при внешних стимулах.
    """

    def __init__(self, event_bus: EventBus, global_state: GlobalState):
        self.event_bus = event_bus
        self.state = global_state

        rhythms = self.state.settings_state.get_state()["rhythms"]

        # Инициализируем таймеры базовыми значениями из настроек
        self.proactivity_countdown = rhythms.get("proactivity_interval_sec", 900)
        self.consolidation_countdown = rhythms.get("consolidation_interval_sec", 3600)
        
        # Запоминаем физическое время последнего запуска проактивности
        self.last_proactivity_time = time.time()

    def reduce_proactivity_timer(self, level: str):
        """
        Ускоряет запуск проактивности.
        """
        rhythms = self.state.settings_state.get_state()["rhythms"]

        reduction = 0
        if level == "medium":
            reduction = rhythms.get("reduction_medium_sec", 180)
        elif level == "low":
            reduction = rhythms.get("reduction_low_sec", 90)
        elif level == "background":
            reduction = rhythms.get("reduction_background_sec", 30)

        min_cooldown = rhythms.get("min_proactivity_cooldown_sec", 60)

        # Вычисляем, сколько секунд мы еще должны подождать, чтобы не нарушить кулдаун
        seconds_passed = time.time() - self.last_proactivity_time
        remaining_cooldown = max(0, min_cooldown - seconds_passed)

        old_value = self.proactivity_countdown
        self.proactivity_countdown -= reduction

        # Если мы срезали таймер так сильно, что он стал меньше обязательного остатка кулдауна,
        # то приравниваем его к этому остатку (если остаток 0, таймер станет 0 и цикл запустится сразу)
        if self.proactivity_countdown < remaining_cooldown:
            self.proactivity_countdown = int(remaining_cooldown)

        system_logger.info(
            f"[Heartbeat] Фоновое событие ({level}). Таймер проактивности: {old_value} -> {self.proactivity_countdown} сек."
        )

    async def _proactivity_ticker(self):
        """Отдельный независимый тикер для цикла проактивности."""
        while True:
            await asyncio.sleep(1)
            
            settings = self.state.settings_state.get_state()
            if not settings["system"]["flags"].get("enable_proactivity", True):
                continue  

            self.proactivity_countdown -= 1
            
            if self.proactivity_countdown <= 0:
                system_logger.info("[Heartbeat] Сработал ритм проактивности.")
                await self.event_bus.publish(Events.SYSTEM_TIMER_PROACTIVITY)
                
                # Сброс таймера и обновление времени запуска
                rhythms = self.state.settings_state.get_state()["rhythms"]
                self.proactivity_countdown = rhythms.get("proactivity_interval_sec", 900)
                self.last_proactivity_time = time.time()

    async def _consolidation_ticker(self):
        """Отдельный независимый тикер для цикла консолидации памяти."""
        while True:
            await asyncio.sleep(1)
            
            settings = self.state.settings_state.get_state()
            if not settings["system"]["flags"].get("enable_consolidation", True):
                continue  

            self.consolidation_countdown -= 1
            
            if self.consolidation_countdown <= 0:
                system_logger.info("[Heartbeat] Сработал ритм консолидации памяти.")
                await self.event_bus.publish(Events.SYSTEM_TIMER_CONSOLIDATION)
                
                # Сброс таймера
                rhythms = self.state.settings_state.get_state()["rhythms"]
                self.consolidation_countdown = rhythms.get("consolidation_interval_sec", 3600)

    def start(self):
        """Запускает сердцебиение."""
        system_logger.info("[Heartbeat] Запуск независимых ритмов (Проактивность и Консолидация).")
        asyncio.create_task(self._proactivity_ticker())
        asyncio.create_task(self._consolidation_ticker())