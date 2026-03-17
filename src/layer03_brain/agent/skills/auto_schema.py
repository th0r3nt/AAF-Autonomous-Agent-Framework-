import inspect
from typing import Callable, Any

# Глобальные реестры для новой архитектуры "All L2"
global_l2_registry = {}      # dict: URI -> Python-функция
global_l0_manifest = {}      # dict: Категория -> Список строк-сигнатур
global_l1_docs = {}          # dict: URI -> Markdown документация

# Тот самый единственный инструмент, который мы отдаем OpenAI
global_openai_tools = [
    {
        "type": "function",
        "function": {
            "name": "execute_skill",
            "description": "ЕДИНСТВЕННЫЙ способ взаимодействия с миром. Вызывает навыки из системной библиотеки (L0 Manifest).",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_uri": {
                        "type": "string",
                        "description": "Точный URI навыка из L0 Справочника."
                    },
                    "kwargs": {
                        "type": "object",
                        "description": "Словарь аргументов для навыка. Строго соблюдай типы данных (int, str, bool) и обязательные параметры из L0 Manifest!",
                        "additionalProperties": True
                    }
                },
                "required": ["skill_uri", "kwargs"],
                "additionalProperties": False
            }
        }
    }
]
 
# Шпаргалка для красивого вывода типов
def _get_type_name(annotation) -> str:
    if annotation == inspect.Parameter.empty or annotation == Any:
        return "any"
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def llm_skill(description: str, parameters: dict = None, category_override: str = None): 
    """
    Магический декоратор.
    Автоматически определяет категорию навыка, генерирует L0-сигнатуру и L1-документацию.
    """
    if parameters is None:
        parameters = {}

    def decorator(func: Callable):
        func_name = func.__name__
        
        # 1. Определяем категорию
        if category_override:
            category = category_override
        else:
            module_parts = func.__module__.split('.')
            category = "core"
            if "skills" in module_parts:
                idx = module_parts.index("skills")
                if len(module_parts) > idx + 1:
                    category = module_parts[idx + 1]
            elif "plugins" in module_parts:
                category = "plugins"
                
        uri = f"aaf://{category}/{func_name}" # Для более подробного вывода
        # uri = func_name
        
        # 2. Регистрируем функцию в глобальном реестре
        global_l2_registry[uri] = func
        
        # 3. Разбираем аргументы для L0 и L1
        sig = inspect.signature(func)
        
        l0_args = []
        l1_args_details = []
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'args', 'kwargs']:
                continue

            param_type = _get_type_name(param.annotation)
            is_optional = param.default != inspect.Parameter.empty
            
            # Получаем инфу из parameters декоратора
            param_data = parameters.get(param_name, "Без описания")
            param_desc = param_data if isinstance(param_data, str) else param_data.get("description", "Без описания")
            param_enum = param_data.get("enum") if isinstance(param_data, dict) else None

            # СБОРКА L0 (Кратко)
            # Если есть Enum, вставляем его прямо в тип (гениально)
            if param_enum:
                enum_str = "|".join([f"'{e}'" for e in param_enum])
                arg_type_display = enum_str
            else:
                arg_type_display = param_type

            # Формируем аргумент: action: 'upsert'|'delete'
            arg_str = f"{param_name}: {arg_type_display}"
            if is_optional:
                arg_str += f"={repr(param.default)}"
            else:
                arg_str += " [REQ]"  # <--- Добавляем жесткий маркер
            l0_args.append(arg_str)

            # СБОРКА L1 (Подробно) 
            req_str = "Опционально" if is_optional else "Обязательно"
            enum_details = f"\n   - *Допустимые значения:* {param_enum}" if param_enum else ""
            l1_args_details.append(f"- **`{param_name}`** (`{param_type}`, {req_str}): {param_desc}{enum_details}")

        # 4. Сохраняем L0 сигнатуру
        signature_str = f"{uri}({', '.join(l0_args)})"
        
        # Оставляем только чистую сигнатуру и короткое описание!
        l0_line = f"- `{signature_str}` -> {description}"
            
        if category not in global_l0_manifest:
            global_l0_manifest[category] =[]
        global_l0_manifest[category].append(l0_line)

        # 5. Сохраняем L1 документацию (Markdown)
        # А вот здесь (в L1) сохраняем ВСЕ подробности, Enum'ы и описания аргументов
        l1_doc = f"## Навык: {uri}\n\n**Описание:** {description}\n\n"
        if l1_args_details:
            l1_doc += "### Аргументы (kwargs):\n" + "\n".join(l1_args_details)
        else:
            l1_doc += "### Аргументы: Нет.\n"
        global_l1_docs[uri] = l1_doc

        return func
    return decorator

# Сразу регистрируем системный навык для чтения L1-доков (он доступен всегда)
@llm_skill(
    description="Получить полную Markdown-справку (L1) по любому навыку...",
    parameters={"target_uri": "Точный URI навыка."},
    category_override="core"
)
def get_skill_docs(target_uri: str) -> str:
    if target_uri in global_l1_docs:
        return global_l1_docs[target_uri]
    return f"Справка не найдена. Навык '{target_uri}' не существует. Проверь список в L0 Manifest."