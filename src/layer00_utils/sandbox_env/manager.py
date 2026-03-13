import subprocess
from src.layer00_utils.logger import system_logger
from src.layer00_utils.workspace import workspace_manager

def _get_running_python_scripts() -> dict:
    """
    Сканирует Docker и находит все запущенные контейнеры с префиксом agent_daemon_
    Возвращает словарь {имя_файла: ID_контейнера}
    """
    running = {}
    try:
        # Запрашиваем список контейнеров (формат: Имя|ID)
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}|{{.ID}}"],
            capture_output=True, text=True, check=True
        )
        
        output = result.stdout.strip()
        if not output:
            return running
            
        for line in output.split('\n'):
            if line.startswith("agent_daemon_"):
                parts = line.split('|')
                if len(parts) == 2:
                    container_name = parts[0]
                    container_id = parts[1]
                    
                    # Извлекаем оригинальное имя файла (убираем префикс)
                    # agent_daemon_monitor.py -> monitor.py
                    filename = container_name.replace("agent_daemon_", "", 1)
                    running[filename] = container_id
                    
    except Exception as e:
        system_logger.error(f"[Sandbox] Ошибка при поиске Docker-контейнеров: {e}")
        
    return running

def _start_background_python_script(filename: str) -> str:
    """Запускает скрипт как независимого фонового демона в Docker"""
    filepath = workspace_manager.get_sandbox_file(filename)
    
    if not filepath.exists():
        return f"[Error] Файл '{filename}' не найден."

    # 1. Проверяем, не запущен ли он уже
    running = _get_running_python_scripts()
    if filename in running:
        return f"[Info] Скрипт '{filename}' уже работает в фоне (Container ID: {running[filename]})."

    # 2. Формируем уникальное имя для контейнера
    # Docker требует, чтобы имена контейнеров состояли только из [a-zA-Z0-9_.-]
    safe_filename = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
    container_name = f"agent_daemon_{safe_filename}"
    
    # 3. Запускаем отвязанный процесс в Docker (флаг -d)
    import socket
    current_container_id = socket.gethostname()
    
    docker_cmd = [
        "docker", "run", "-d",                          
        "--name", container_name,                       
        "--memory=512m",                                
        "--cpus=1.0",                                   
        "--pids-limit=50",                              
        "--add-host=host.docker.internal:host-gateway", 
        "--volumes-from", current_container_id,         # Берем вольюмы из текущего контейнера
        "-w", "/app/workspace/sandbox",                 # Рабочая директория
        "python:3.11-slim",                             
        "python", filename                              
    ]

    try:
        # Запускаем синхронно, так как docker run -d отрабатывает мгновенно
        result = subprocess.run(docker_cmd, capture_output=True, text=True, check=True)
        container_id = result.stdout.strip()[:12] # Берем короткий ID
        
        system_logger.info(f"[Sandbox] Запущен фоновый демон: '{filename}' (ID: {container_id})")
        return f"Скрипт '{filename}' успешно запущен в фоновом режиме (Docker Container: {container_name})."
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        system_logger.error(f"[Sandbox] Ошибка запуска демона '{filename}': {error_msg}")
        
        # Если контейнер с таким именем уже существует (например, упал, но не удалился)
        if "Conflict" in error_msg or "already in use" in error_msg:
            # Пытаемся принудительно удалить мертвый контейнер и запустить заново
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
            return "[Warning] Обнаружен зависший контейнер. Он был удален. Попробуйте запустить скрипт еще раз."
            
        return f"[Error] Не удалось запустить скрипт в Docker: {error_msg}"
    except Exception as e:
        system_logger.error(f"[Sandbox] Системная ошибка запуска демона '{filename}': {e}")
        return f"[Error] Внутренняя ошибка: {e}"

def _kill_background_python_script(filename: str) -> str:
    """Находит и принудительно удаляет фоновый Docker-контейнер"""
    running = _get_running_python_scripts()
    
    if filename not in running:
        return f"[Info] Скрипт '{filename}' не найден среди запущенных контейнеров."
        
    # Имя контейнера, которое мы ему давали при запуске
    safe_filename = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
    container_name = f"agent_daemon_{safe_filename}"
    
    try:
        # docker rm -f принудительно останавливает (SIGKILL) и удаляет контейнер
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True, text=True, check=True
        )
        system_logger.warning(f"[Sandbox] Демон '{filename}' (Контейнер {container_name}) убит.")
        return f"Фоновый процесс '{filename}' успешно остановлен и удален."
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        return f"[Error] Ошибка при удалении контейнера: {error_msg}"
    except Exception as e:
        return f"[Error] Системная ошибка при удалении: {e}"
    
def cleanup_zombie_containers() -> None:
    """
    Вызывается при старте системы.
    Находит все зависшие/осиротевшие фоновые Docker-контейнеры от прошлых запусков агента и жестко убивает их.
    """
    running = _get_running_python_scripts()
    
    if not running:
        system_logger.info("[Sandbox] Зомби-контейнеры не обнаружены. Песочница чиста.")
        return
        
    system_logger.warning(f"[Sandbox] Обнаружено {len(running)} осиротевших контейнеров. Начинаю зачистку...")
    
    killed_count = 0
    for filename, container_id in running.items():
        try:
            # Восстанавливаем оригинальное имя контейнера
            safe_filename = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
            container_name = f"agent_daemon_{safe_filename}"
            
            # Принудительно убиваем
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True, check=True
            )
            killed_count += 1
            system_logger.debug(f"[Sandbox] Зомби-контейнер '{container_name}' (ID: {container_id}) уничтожен.")
        except Exception as e:
            system_logger.error(f"[Sandbox] Не удалось убить зомби-контейнер '{filename}': {e}")
            
    system_logger.info(f"[Sandbox] Зачистка завершена. Уничтожено {killed_count} зомби-контейнеров.")