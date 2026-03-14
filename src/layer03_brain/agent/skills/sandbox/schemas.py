

execute_python_script_scheme = {
    "name": "_execute_python_script",
    "description": "Разово запускает Python-скрипт из папки sandbox в изолированном Docker-контейнере.",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Имя файла в песочнице."}
        },
        "required": ["filename"]
    }
}

start_background_python_script_scheme = {
    "name": "start_background_python_script",
    "description": "Запускает Python-скрипт из папки sandbox как бесконечного фонового демона.",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Имя файла в песочнице."}
        },
        "required": ["filename"]
    }
}

kill_background_python_script_scheme = {
    "name": "kill_background_python_script",
    "description": "Принудительно завершает работу фонового Python-скрипта в песочнице.",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Имя запущенного файла."}
        },
        "required": ["filename"]
    }
}

_get_running_python_scripts_scheme = {
    "name": "_get_running_python_scripts",
    "description": "Возвращает список всех Python-скриптов, которые сейчас работают в фоне в песочнице.",
    "parameters": {"type": "object", "properties": {}}
}

delete_sandbox_file_scheme = {
    "name": "delete_sandbox_file",
    "description": "Удаляет указанный файл из твоей песочницы (workspace/sandbox/).",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Имя файла для удаления."}
        },
        "required": ["filename"]
    }
}

SANDBOX_SCHEMAS = [
    execute_python_script_scheme, start_background_python_script_scheme,
    kill_background_python_script_scheme, _get_running_python_scripts_scheme,
    delete_sandbox_file_scheme
]