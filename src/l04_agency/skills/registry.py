import inspect
from typing import Callable, Dict, Any, List, get_origin, get_args, Literal
from src.l00_utils.managers.logger import system_logger


class ToolRegistry:
    """
    Единственный источник правды для навыков агента.
    Плоский словарь, хранящий ссылки на все функции.
    """

    _tools: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(
        cls, domain: str, name: str, description: str, signature: str, func: Callable
    ):
        """
        Регистрирует инструмент в глобальном словаре.
        """
        tool_id = f"{domain}.{name}"
        if tool_id in cls._tools:
            system_logger.warning(f"[Registry] Инструмент {tool_id} перезаписан!")

        cls._tools[tool_id] = {
            "id": tool_id,
            "description": description,
            "signature": signature,
            "callable": func,
        }
        system_logger.debug(f"[Registry] Зарегистрирован навык: {tool_id}")

    @classmethod
    def get_all_tools(cls) -> List[Dict[str, Any]]:
        """Возвращает метаданные всех инструментов для сборки промпта."""
        return [
            {"id": v["id"], "signature": v["signature"], "description": v["description"]}
            for v in cls._tools.values()
        ]

    @classmethod
    def get_tool(cls, tool_id: str) -> Callable | None:
        """Возвращает ссылку на функцию для выполнения."""
        tool = cls._tools.get(tool_id)
        return tool["callable"] if tool else None


def skill(name: str = None, description: str = None, domain: str = None):
    """
    Декоратор. Автоматически регистрирует метод в ToolRegistry,
    собирает его аргументы (включая Literal) и схлопывает docstring в одну строку.
    """

    def decorator(func: Callable):
        func.__is_skill__ = True
        func.__skill_domain__ = domain
        func.__skill_name__ = name or func.__name__

        # 1. Форматируем описание в одну строку
        raw_doc = description or func.__doc__ or "Без описания"
        clean_doc = inspect.cleandoc(raw_doc)
        func.__skill_desc__ = " ".join(clean_doc.split())

        # 2. Магия: Извлекаем сигнатуру (аргументы, типы, дефолты, Literal)
        sig = inspect.signature(func)
        params = []
        for p_name, p in sig.parameters.items():
            if p_name in ("self", "args", "kwargs"):
                continue

            type_str = ""
            if p.annotation != inspect.Parameter.empty:
                origin = get_origin(p.annotation)

                # Если это Literal, разворачиваем его в формат 'A' | 'B' | 'C'
                if origin is Literal:
                    args = get_args(p.annotation)
                    # Оборачиваем строки в кавычки, числа оставляем как есть
                    formatted_args = [f"'{a}'" if isinstance(a, str) else str(a) for a in args]
                    type_str = f": {' | '.join(formatted_args)}"
                else:
                    # Обычные типы (str, int, dict и т.д.)
                    if hasattr(p.annotation, "__name__"):
                        type_str = f": {p.annotation.__name__}"
                    else:
                        type_str = f": {str(p.annotation).replace('typing.', '')}"

            default_str = ""
            if p.default != inspect.Parameter.empty:
                if isinstance(p.default, str):
                    default_str = f" = '{p.default}'"
                else:
                    default_str = f" = {p.default}"

            params.append(f"{p_name}{type_str}{default_str}")

        func.__skill_signature__ = f"({', '.join(params)})"

        return func

    return decorator
