import asyncio 
import os


from src.layer00_utils.workspace import (
    workspace_manager
)
from src.layer00_utils.sandbox_env.executor import (
    execute_once
)
from src.layer00_utils.sandbox_env.manager import (
    _start_background_python_script, _kill_background_python_script, _get_running_python_scripts
)

async def execute_python_script(filename: str) -> str:
    """Обертка: разовый запуск скрипта в песочнице"""
    return await execute_once(filename)

async def start_background_python_script(filename: str) -> str:
    """Обертка: запуск фонового демона"""
    return await asyncio.to_thread(_start_background_python_script, filename)

async def kill_background_python_script(filename: str) -> str:
    """Обертка: убийство фонового демона"""
    return await asyncio.to_thread(_kill_background_python_script, filename)

async def get_running_python_scripts() -> str:
    """Обертка: просмотр запущенных скриптов"""
    running = await asyncio.to_thread(_get_running_python_scripts)
    if not running:
        return "В песочнице нет запущенных фоновых скриптов."
    
    lines = ["Запущенные фоновые скрипты:"]
    for fname, pid in running.items():
        lines.append(f"- {fname} (PID: {pid})")
    return "\n".join(lines)

async def delete_sandbox_file(filename: str) -> str:
    """Удаляет файл из Sandbox"""
    try:
        # Очищаем путь, оставляя только имя файла (защита от выхода из директории)
        clean_filename = os.path.basename(filename.replace("file:///", "").replace("/app/", ""))
        
        filepath = workspace_manager.get_sandbox_file(clean_filename)
        
        if not filepath.exists() or not filepath.is_file():
            return f"Ошибка: Файл '{clean_filename}' не найден в песочнице."
            
        # Удаляем файл в отдельном потоке, так как это I/O операция
        await asyncio.to_thread(filepath.unlink)
        return f"Файл '{clean_filename}' успешно удален из песочницы."
    except Exception as e:
        return f"Ошибка при удалении файла: {e}"
    
SANDBOX_REGISTRY = {
    "_execute_python_script": execute_python_script,
    "start_background_python_script": start_background_python_script,
    "kill_background_python_script": kill_background_python_script,
    "_get_running_python_scripts": get_running_python_scripts,
    "delete_sandbox_file": delete_sandbox_file,
}