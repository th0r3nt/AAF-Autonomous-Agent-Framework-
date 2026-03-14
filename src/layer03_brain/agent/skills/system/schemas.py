from src.layer00_utils.config_manager import config


change_proactivity_interval_scheme = {
    "name": "change_proactivity_interval",
    "description": "Изменяет интервал твоего проактивного цикла.",
    "parameters": {
        "type": "object",
        "properties": {
            "seconds": {"type": "integer", "description": "Новый интервал в секундах"}
        },
        "required": ["seconds"]
    }
}

change_thoughts_interval_scheme = {
    "name": "change_thoughts_interval",
    "description": "Изменяет интервал твоего цикла интроспекции.",
    "parameters": {
        "type": "object",
        "properties": {
            "seconds": {"type": "integer", "description": "Новый интервал в секундах"}
        },
        "required": ["seconds"]
    }
}

read_recent_logs_scheme = {
    "name": "read_recent_logs",
    "description": "Читает последние записи из твоего системного лога системы (system.log). Полезно для дебаггинга.",
    "parameters": {
        "type": "object",
        "properties": {
            "lines": {"type": "integer", "description": "Количество последних строк для чтения (по умолчанию 50)."}
        }
    }
}

shutdown_system_scheme = {
    "name": "shutdown_system",
    "description": "Инициирует корректное завершение работы всего твоего системного ядра (Docker-контейнера).",
    "parameters": {"type": "object", "properties": {}}
}

change_llm_model_scheme = {
    "name": "change_llm_model",
    "description": "Изменяет твое вычислительное ядро (LLM-модель).",
    "parameters": {
        "type": "object",
        "properties": {
            "new_model": {
                "type": "string",
                "enum": config.llm.available_models,
                "description": "Точное название новой модели."
            }
        },
        "required": ["new_model"]
    }
}


SYSTEM_SCHEMAS = [
    change_proactivity_interval_scheme, change_thoughts_interval_scheme, 
    read_recent_logs_scheme, shutdown_system_scheme, change_llm_model_scheme,
]