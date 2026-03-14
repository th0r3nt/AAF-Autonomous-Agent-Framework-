
lock_pc_scheme = {"name": "lock_pc", "description": "Блокирует рабочую станцию Windows", "parameters": {"type": "object", "properties": {}}}

print_to_terminal_scheme = {
    "name": "print_to_terminal",
    "description": "Выводит сообщение в терминал основного ПК. Важно: запрещено писать сюда просто одно слово 'OK'",
    "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Текст ответа"}}, "required": ["text"]}
}

speak_text_scheme = {
    "name": "speak_text",
    "description": "Озвучивает текст через динамики основного ПК.",
    "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Текст для озвучки."}}, "required": ["text"]}
}

list_local_directory_scheme = {
    "name": "list_local_directory",
    "description": "Показывает список файлов и папок в указанной локальной директории на основном ПК.",
    "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Путь к директории (например: '.', 'src/')"}}, "required": ["path"]}
}

read_local_system_file_scheme = {
    "name": "read_local_system_file",
    "description": "Читает текстовое содержимое исходного кода твоей системы (папка src/). Используй ЭТОТ инструмент для анализа системных файлов.",
    "parameters": {"type": "object", "properties": {"filepath": {"type": "string", "description": "Имя файла или путь к нему (например: 'main.py')"}}, "required": ["filepath"]}
}

read_sandbox_file_scheme = {
    "name": "read_sandbox_file",
    "description": "Читает файлы ИСКЛЮЧИТЕЛЬНО из твоей песочницы (workspace/sandbox/). Полезно, чтобы читать отчеты субагентов.",
    "parameters": {"type": "object", "properties": {"filename": {"type": "string", "description": "Имя файла в песочнице."}}, "required": ["filename"]}
}

get_system_architecture_map_scheme = {
    "name": "get_system_architecture_map",
    "description": "Возвращает полное дерево файловой системы твоего проекта (папки src/) на основном ПК.",
    "parameters": {"type": "object", "properties": {}}
}

clean_temp_workspace_scheme = {"name": "clean_temp_workspace", "description": "Полностью очищает твою папку временных файлов (workspace/temp/).", "parameters": {"type": "object", "properties": {}}}

send_windows_notification_scheme = {
    "name": "send_windows_notification",
    "description": "Отправляет системное push-уведомление Windows на экран основного ПК.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Заголовок уведомления"},
            "text": {"type": "string", "description": "Текст уведомления."}
        },
        "required": ["title", "text"]
    }
}

look_at_screen_scheme = {"name": "look_at_screen", "description": "Делает снимок (скриншот) всех мониторов основного ПК и мгновенно загружает его в контекст.", "parameters": {"type": "object", "properties": {}}}

write_local_file_scheme = {
    "name": "write_local_file",
    "description": "Создает или перезаписывает текстовый файл в твоей изолированной директории (workspace/sandbox/).",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Имя файла с расширением (например: 'plan.md')."},
            "content": {"type": "string", "description": "Текстовое содержимое, которое нужно записать в файл."}
        },
        "required": ["filename", "content"]
    }
}


PC_SCHEMAS = [
    lock_pc_scheme, print_to_terminal_scheme, speak_text_scheme, list_local_directory_scheme,
    read_local_system_file_scheme, read_sandbox_file_scheme, get_system_architecture_map_scheme,
    clean_temp_workspace_scheme, send_windows_notification_scheme, look_at_screen_scheme, write_local_file_scheme
]