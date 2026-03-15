import inspect
from typing import Callable, Any

global_skills_registry = {}
global_openai_tools = []

# Шпаргалка для перевода типов Python в типы JSON
TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    Any: "string" # Если тип не указан, считаем строкой
}

def llm_skill(description: str, parameters: dict = None):
    """
    Магический декоратор. 
    Сам собирает JSON-схему для OpenAI из аргументов функции.
    """
    if parameters is None:
        parameters = {}

    def decorator(func: Callable):
        func_name = func.__name__
        
        # 1. Автоматически добавляем функцию в реестр для вызова
        global_skills_registry[func_name] = func

        # 2. Анализируем аргументы функции (читаем код)
        sig = inspect.signature(func)
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'args', 'kwargs']:
                continue

            param_type = TYPE_MAP.get(param.annotation, "string")
            
            # Получаем настройки параметра (строка-описание или словарь с enum)
            param_data = parameters.get(param_name, "Без описания")
            
            if isinstance(param_data, str):
                param_info = {"type": param_type, "description": param_data}
            else:
                param_info = {"type": param_type}
                param_info.update(param_data) # Если передали enum или что-то еще

            # Если это список, по стандарту OpenAI нужно указать тип элементов
            if param_type == "array" and "items" not in param_info:
                param_info["items"] = {"type": "string"}

            properties[param_name] = param_info

            # Если у аргумента нет дефолтного значения (например, `limit: int = 50`), 
            # значит он обязателен для LLM
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        # 3. Собираем финальный JSON
        schema = {
            "type": "function",
            "function": {
                "name": func_name,
                "description": description
            }
        }
        
        # Защита от кривых API-прокси (OneAPI/LiteLLM):
        # Добавляем блок parameters ТОЛЬКО если у функции реально есть аргументы.
        if properties:
            schema["function"]["parameters"] = {
                "type": "object",
                "properties": properties,
            }
            if required:
                schema["function"]["parameters"]["required"] = required

        # Автоматически добавляем схему в список
        global_openai_tools.append(schema)

        return func
    return decorator