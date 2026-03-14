
spawn_subagent_scheme = {
    "name": "spawn_subagent",
    "description": "Создает специализированного субагента для выполнения фоновых/рутинных задач.",
    "parameters": {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "enum": ["Researcher", "SystemAnalyst", "ChatSummarizer", "WebMonitor", "Chronicler"],
                "description": "Класс субагента."
            },
            "name": {
                "type": "string", 
                "description": "Уникальное имя субагента."
            },
            "instructions": {
                "type": "string", 
                "description": "Подробная инструкция, что именно он должен сделать."
            },
            "trigger_condition": {
                "type": "string", 
                "description": "ТОЛЬКО ДЛЯ ДЕМОНОВ. Условие для тревоги."
            },
            "interval_sec": {
                "type": "integer", 
                "description": "ТОЛЬКО ДЛЯ ДЕМОНОВ. Интервал сна между проверками в секундах."
            }
        },
        "required": ["role", "name", "instructions"]
    }
}

kill_subagent_scheme = {
    "name": "kill_subagent",
    "description": "Прерывает запущенный процесс субагента по его имени.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Имя субагента."}
        },
        "required": ["name"]
    }
}

update_subagent_scheme = {
    "name": "update_subagent",
    "description": "Обновление параметров уже запущенного субагента без его остановки.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Имя активного субагента."},
            "instructions": {"type": "string", "description": "(Опционально) Новые инструкции."},
            "trigger_condition": {"type": "string", "description": "(Опционально) Новое условие для тревоги."},
            "interval_sec": {"type": "integer", "description": "(Опционально) Новый интервал сна."}
        },
        "required": ["name"]
    }
}

SWARM_SCHEMAS = [spawn_subagent_scheme, kill_subagent_scheme, update_subagent_scheme]