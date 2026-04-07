from src.l00_utils.managers.logger import system_logger

from src.l02_state.manager import GlobalState

# Родители
from src.l03_interfaces.type.base import BaseClient

# Инструменты
from src.l03_interfaces.type.system.instruments.meta import SystemMeta


class SystemClient(BaseClient):
    """
    Клиент для системного интерфейса агента.
    Обеспечивает доступ к глобальному состоянию для инструментов.
    """

    name = "system"

    def __init__(self, global_state: GlobalState):
        self.global_state = global_state

    def register_instruments(self):
        SystemMeta(self)
        system_logger.debug("[System] Инструменты управления настройками зарегистрированы.")

    async def start_background_polling(self) -> None:
        pass  # Нет фонового поллинга

    async def check_connection(self) -> bool:
        system_logger.info(
            "[System Interface] Интерфейс управления настройками инициализирован."
        )
        return True

    async def close(self):
        pass
