"""
Универсальная схема для вызова инструментов агентом.
Заставляет LLM генерировать 'thoughts' перед массивом 'actions',
обеспечивая механизм Chain-of-Thought (CoT).
"""

ACTION_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "execute_skill",
            "description": "Главный интерфейс взаимодействия с внешним миром и базами данных. Обязателен к вызову для любых действий.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thoughts": {
                        "type": "string",
                        "description": "Цепочка рассуждений/мыслей перед действием."
                    },
                    "actions": {
                        "type": "array",
                        "description": "Список действий для параллельного выполнения.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tool_name": {
                                    "type": "string",
                                    "description": "Точное имя функции из блока SKILLS LIBRARY."
                                },
                                "parameters": {
                                    "type": "object",
                                    "description": "Аргументы функции в формате ключ-значение.",
                                    "additionalProperties": False
                                }
                            },
                            "required": ["tool_name", "parameters"]
                        }
                    }
                },
                "required": ["thoughts", "actions"]
            }
        }
    }
]