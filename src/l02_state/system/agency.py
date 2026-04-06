from collections import deque
from contextvars import ContextVar

from src.l00_utils.managers.logger import system_logger


class AgencyState:
    def __init__(self):
        # Состояние главного мозга агента
        self.main_agent = {
            "status": "sleeping",  # sleeping, thinking, executing, consolidating
            "current_cycle": "none",  # event_driven, proactivity, consolidation, none
            "current_tick_id": 0,  # ID тика в БД (для VFS и бэкапов)
        }
        # Буфер прерываний: список EventEnvelope, которые прилетели, пока мозг думал
        self.interrupt_buffer = []

        # Буфер событий: хранит фоновые события уровня MEDIUM, LOW и BACKGROUND, пока агент спит
        self.sensory_buffer = deque(maxlen=100)

        # Глобальная контекстная переменная для хранения ID текущего тика ReAct-цикла.
        # Нужна для работы теневых бэкапов VFS.
        self.current_tick_id: ContextVar[int] = ContextVar("current_tick_id", default=0)

    def get_state(self) -> dict:
        """
        Возвращает полный слепок состояния всей агентуры.
        """
        return {"main_agent": self.main_agent, "subagents": self.subagents}

    # ==========================================
    # УПРАВЛЕНИЕ ГЛАВНЫМ АГЕНТОМ
    # ==========================================

    def update_main_agent(
        self,
        status: str = None,
        current_cycle: str = None,
        current_tick_id: int = None,
    ):
        """
        Обновляет статус главного агента.
        Передаются только те аргументы, которые действительно изменились.
        """
        if status is not None:
            self.main_agent["status"] = status

        if current_cycle is not None:
            self.main_agent["current_cycle"] = current_cycle

        if current_tick_id is not None:
            self.main_agent["current_tick_id"] = current_tick_id

    # ==========================================
    # УПРАВЛЕНИЕ СУБАГЕНТАМИ
    # ==========================================

    def update_subagent(
        self, role: str, name: str, status: str, task: str = "Фоновая работа"
    ) -> bool:
        """
        Регистрирует или обновляет статус субагента.
        :param role: "daemons" | "workers"
        :param name: Уникальное имя
        :param status: "working" | "sleeping" | "error"
        :param task: Чем конкретно занят
        """
        if role not in self.subagents:
            system_logger.error(f"[AgencyState] Неизвестная роль субагента: {role}")
            return False

        self.subagents[role][name] = {"status": status, "task": task}
        return True

    def remove_subagent(self, role: str, name: str):
        """
        Удаляет субагента из оперативной памяти.
        """
        if role in self.subagents and name in self.subagents[role]:
            del self.subagents[role][name]
            system_logger.debug(f"[AgencyState] Субагент {name} ({role}) удален из активного пула.")
