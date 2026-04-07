from abc import ABC, abstractmethod
from src.l04_agency.skills.registry import ToolRegistry


class BaseClient(ABC):
    """Базовый класс для всех клиентов интерфейсов. Чистый контракт без принудительных зависимостей."""

    # Уникальное имя интерфейса (переопределяется в наследниках, например: "telegram", "github")
    name: str = "unknown"

    @abstractmethod
    async def check_connection(self) -> bool:
        """Проверка доступности (токенов, сети, портов). Fail-Fast механизм."""
        pass

    @abstractmethod
    def register_instruments(self) -> None:
        """Регистрация скиллов (инструментов) в ToolRegistry."""
        pass

    async def start_background_polling(self) -> None:
        """
        Запуск фоновых задач (поллинг, вебхуки, прослушка событий).
        По умолчанию ничего не делает.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Очистка ресурсов при выключении системы."""
        pass

    def get_passive_context(self) -> dict:
        """
        Возвращает слепок последних событий интерфейса из оперативной памяти (O(1)).
        Не делает сетевых запросов.
        """
        return {"name": self.name, "status": "online", "recent_activity": []}


class BaseInstrument:
    """
    Базовый класс для всех инструментов интерфейсов.
    Автоматически вычисляет свой домен из файловой структуры и регистрирует навыки.
    """

    def __init__(self):
        # 1. Пытаемся взять явно заданный домен (если его захотели переопределить вручную)
        class_domain = getattr(self, "domain", None)

        # 2. Если домен не задан руками, генерируем его магией Python из пути к файлу
        if not class_domain:
            # Получаем строку вида: 'src.l03_interfaces.type.api.github.instruments.issues'
            raw_module = self.__class__.__module__
            parts = raw_module.split(".")

            # Фильтруем технический мусор, чтобы оставить только суть
            ignored_folders = {
                "src",
                "l03_interfaces",
                "type",
            }
            clean_parts = [p for p in parts if p not in ignored_folders]

            # Собираем красивый домен: 'api.github.instruments.issues'
            class_domain = ".".join(clean_parts)

        # 3. Пробегаемся по всем методам созданного объекта
        for attr_name in dir(self):
            attr_value = getattr(self, attr_name)

            if callable(attr_value) and getattr(attr_value, "__is_skill__", False):

                # Приоритет: 1. Явный domain в @skill, 2. Сгенерированный домен класса
                method_domain = getattr(attr_value, "__skill_domain__") or class_domain
                name = getattr(attr_value, "__skill_name__")
                desc = getattr(attr_value, "__skill_desc__")
                sig = getattr(attr_value, "__skill_signature__", "()")

                # Регистрируем навык (передаем сигнатуру)
                ToolRegistry.register(
                    domain=method_domain,
                    name=name,
                    description=desc,
                    signature=sig,
                    func=attr_value,
                )
