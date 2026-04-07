import asyncio
import inspect
from pathlib import Path

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.event_bus import EventBus
from src.l02_state.manager import GlobalState
from src.l01_databases.sql.db import SQLDB

from src.l03_interfaces.type.base import BaseClient

# Импорты всех клиентов для реестра интерфейсов
from src.l03_interfaces.type.system.client import SystemClient
from src.l03_interfaces.type.vfs.client import VFSClient
from src.l03_interfaces.type.calendar.client import CalendarClient
from src.l03_interfaces.type.email.client import EmailClient
from src.l03_interfaces.type.geo.client import GeoClient
from src.l03_interfaces.type.api.github.client import GithubClient
from src.l03_interfaces.type.api.habr.client import HabrClient
from src.l03_interfaces.type.api.reddit.client import RedditClient
from src.l03_interfaces.type.telegram.aiogram.client import AiogramClient
from src.l03_interfaces.type.telegram.telethon.client import TelethonClient
from src.l03_interfaces.type.web.http.client import HTTPClient
from src.l03_interfaces.type.web.search.client import SearchClient


# ==========================================
# РЕЕСТР ИНТЕРФЕЙСОВ
# ==========================================

# Собираем все классы в один список. При добавлении нового интерфейса
# достаточно просто добавить его класс сюда
ALL_CLIENT_CLASSES = [
    SystemClient,
    VFSClient,
    CalendarClient,
    EmailClient,
    GeoClient,
    GithubClient,
    HabrClient,
    RedditClient,
    AiogramClient,
    TelethonClient,
    HTTPClient,
    SearchClient,
]

# Автоматически генерируем словарь { "имя_интерфейса": КлассКлиента }.
# Берем атрибут .name прямо из класса. Это 100% исключает опечатки!
INTERFACE_REGISTRY = {cls.name: cls for cls in ALL_CLIENT_CLASSES}


class InterfaceInitializer:
    """
    Универсальный инициализатор интерфейсов.
    Работает по паттерну Registry + Strict Dependency Injection (IoC Container).
    """

    def __init__(
        self,
        global_state: GlobalState,
        event_bus: EventBus,
        sql_db: SQLDB,
        active_clients: dict,
    ):
        self.global_state = global_state
        self.active_clients = (
            active_clients  # Список для хранения активных клиентов интерфейсов
        )

        # Вычисляем путь к песочнице
        project_root = Path(__file__).resolve().parents[3]
        sandbox_dir = project_root / "agent" / "sandbox"

        # Пул зависимостей, из которого клиенты будут забирать только то, что им нужно
        self.dependency_pool = {
            "global_state": global_state,
            "event_bus": event_bus,
            "sql_db": sql_db,
            "sandbox_dir": sandbox_dir,
        }

    async def setup_all(self) -> None:
        """
        Единый цикл запуска всех включенных интерфейсов.
        """
        interfaces_config = self.global_state.interfaces_state.get_state()
        system_logger.info("[Interfaces] Инициализация активных интерфейсов.")

        init_tasks = []

        # Проходимся по всем интерфейсам, которые есть в памяти
        for interface_name, config in interfaces_config.items():
            if config.get("enabled"):
                if interface_name in INTERFACE_REGISTRY:
                    client_class = INTERFACE_REGISTRY[interface_name]
                    init_tasks.append(
                        self._init_single_interface(interface_name, client_class)
                    )
                else:
                    system_logger.warning(
                        f"[Interfaces] Интерфейс '{interface_name}' включен в конфиге, но не найден в Реестре классов. Рекомендуется проверить правильность написания и наличие класса клиента в initializer.py."
                    )

        # Запускаем инициализацию параллельно
        if init_tasks:
            await asyncio.gather(*init_tasks)

        system_logger.info(
            f"[Interfaces] Слой интерфейсов загружен. Активные интерфейсы: {len(self.active_clients)}."
        )

    async def _init_single_interface(self, name: str, client_class: type[BaseClient]) -> None:
        """
        Универсальный жизненный цикл инициализации любого интерфейса с DI.
        1. Передает зависимости.
        2. Регистрирует инструменты.
        3. Запускает фоновые задачи (если есть).
        4. Обновляет стейт и список живых клиентов.
        """
        try:
            # Читаем сигнатуру конструктора клиента
            sig = inspect.signature(client_class.__init__)
            injected_kwargs = {}

            # Подбираем нужные зависимости из пула
            for param_name in sig.parameters:
                if param_name in ("self", "args", "kwargs"):
                    continue

                if param_name in self.dependency_pool:
                    injected_kwargs[param_name] = self.dependency_pool[param_name]
                else:
                    raise ValueError(
                        f"Интерфейс '{name}' запросил неизвестную зависимость: '{param_name}'"
                    )

            # Инициализация клиента
            client = client_class(**injected_kwargs)

            # Проверка пульса (Fail-Fast)
            is_connected = await client.check_connection()
            if not is_connected:
                return

            # Регистрация инструментов для LLM (если есть)
            client.register_instruments()

            # Запуск фоновых задач (поллинги)
            await client.start_background_polling()

            # Обновление стейта и добавление в список живых
            self.global_state.interfaces_state.set_runtime(name, True)
            self.active_clients.append(client)

        except Exception as e:
            system_logger.error(f"[Interfaces] Критическая ошибка инициализации '{name}': {e}")
