import inspect
from typing import Callable, Dict, Any, List
from src.l00_utils.managers.logger import system_logger


class ToolRegistry:
    """
    Единственный источник правды для навыков агента.
    Плоский словарь, хранящий ссылки на все функции.
    """

    _tools: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(cls, domain: str, name: str, description: str, func: Callable):
        """
        Регистрирует инструмент в глобальном словаре.
        """
        tool_id = f"{domain}.{name}"
        if tool_id in cls._tools:
            system_logger.warning(f"[Registry] Инструмент {tool_id} перезаписан!")

        cls._tools[tool_id] = {"id": tool_id, "description": description, "callable": func}
        system_logger.debug(f"[Registry] Зарегистрирован навык: {tool_id}")

    @classmethod
    def get_all_tools(cls) -> List[Dict[str, Any]]:
        """Возвращает метаданные всех инструментов для сборки промпта."""
        return [{"id": v["id"], "description": v["description"]} for v in cls._tools.values()]

    @classmethod
    def get_tool(cls, tool_id: str) -> Callable | None:
        """Возвращает ссылку на функцию для выполнения."""
        tool = cls._tools.get(tool_id)
        return tool["callable"] if tool else None


def skill(name: str = None, description: str = None, domain: str = None):
    """
    Декоратор. Автоматически регистрирует метод в ToolRegistry в момент инициализации класса.
    Если description не передан, забирает его из docstring функции.
    Если domain не передан, он подтянется из атрибута класса в BaseInstrument.
    """

    def decorator(func: Callable):
        func.__is_skill__ = True
        func.__skill_domain__ = domain
        func.__skill_name__ = name or func.__name__

        # Берем переданный description, если его нет - читаем docstring
        raw_doc = description or func.__doc__ or "Без описания"

        # inspect.cleandoc убирает отступы от краев (табы/пробелы), но оставляет переносы абзацев
        func.__skill_desc__ = inspect.cleandoc(raw_doc)

        return func

    return decorator
