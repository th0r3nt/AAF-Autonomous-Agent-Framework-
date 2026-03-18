import os
import subprocess
import socket

from src.layer00_utils.logger import system_logger
from src.layer00_utils.workspace import workspace_manager
from src.layer00_utils.env_manager import AGENT_NAME

def _get_running_python_scripts() -> dict:
    running = {}
    # Ищем демонов ТОЛЬКО текущего агента
    prefix = f"agent_daemon_{AGENT_NAME.lower()}_"
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}|{{.ID}}"],
            capture_output=True, text=True, check=True
        )
        
        output = result.stdout.strip()
        if not output:
            return running
            
        for line in output.split('\n'):
            if line.startswith(prefix):
                parts = line.split('|')
                if len(parts) == 2:
                    container_name = parts[0]
                    container_id = parts[1]
                    filename = container_name.replace(prefix, "", 1)
                    running[filename] = container_id
                    
    except Exception as e:
        system_logger.error(f"[Sandbox] Ошибка при поиске Docker-контейнеров: {e}")
        
    return running

def _start_background_python_script(filename: str) -> str:
    filepath = workspace_manager.get_sandbox_file(filename)
    
    if not filepath.exists():
        return f"[Error] Файл '{filename}' не найден."

    running = _get_running_python_scripts()
    if filename in running:
        return f"[Info] Скрипт '{filename}' уже работает в фоне (Container ID: {running[filename]})."

    # Префикс уникальный для каждого агента
    safe_filename = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
    container_name = f"agent_daemon_{AGENT_NAME.lower()}_{safe_filename}"
    
    sandbox_path = f"/app/Agents/{AGENT_NAME}/workspace/sandbox"

    agent_alias = f"agent_{AGENT_NAME.lower()}"
    try:
        agent_ip = socket.gethostbyname(agent_alias)
    except Exception:
        agent_ip = agent_alias

    docker_cmd =[
        "docker", "run", "-d",                          
        "--name", container_name,                       
        "--memory=512m",                                
        "--cpus=1.0",                                   
        "--pids-limit=50",
        "--network=host", 
        "-e", f"MASTER_AGENT={agent_ip}", # Пробрасываем чистый IP
        "-e", f"TZ={os.getenv('TZ', 'UTC')}",
        "-v", f"{sandbox_path}:{sandbox_path}",
        "-w", sandbox_path,
        "aaf-sandbox-base:latest",
        "python", filename                              
    ]

    try:
        result = subprocess.run(docker_cmd, capture_output=True, text=True, check=True)
        container_id = result.stdout.strip()[:12]
        
        system_logger.info(f"[Sandbox] Запущен фоновый демон DinD: '{filename}' (ID: {container_id})")
        return f"Скрипт '{filename}' успешно запущен в фоновом режиме (Docker Container: {container_name})."
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        system_logger.error(f"[Sandbox] Ошибка запуска демона '{filename}': {error_msg}")
        
        if "Conflict" in error_msg or "already in use" in error_msg:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
            return "[Warning] Обнаружен зависший контейнер. Он был удален. Попробуйте запустить скрипт еще раз."
            
        return f"[Error] Не удалось запустить скрипт в Docker: {error_msg}"
    except Exception as e:
        system_logger.error(f"[Sandbox] Системная ошибка запуска демона '{filename}': {e}")
        return f"[Error] Внутренняя ошибка: {e}"

def _kill_background_python_script(filename: str) -> str:
    running = _get_running_python_scripts()
    
    if filename not in running:
        return f"[Info] Скрипт '{filename}' не найден среди запущенных контейнеров агента '{AGENT_NAME}'."
        
    safe_filename = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
    container_name = f"agent_daemon_{AGENT_NAME.lower()}_{safe_filename}"
    
    try:
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
    running = _get_running_python_scripts()
    
    if not running:
        system_logger.info(f"[Sandbox] Зомби-контейнеры для агента '{AGENT_NAME}' не обнаружены.")
        return
        
    system_logger.warning(f"[Sandbox] Обнаружено {len(running)} осиротевших контейнеров агента '{AGENT_NAME}'. Начинаю зачистку...")
    
    killed_count = 0
    for filename, container_id in running.items():
        try:
            safe_filename = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
            container_name = f"agent_daemon_{AGENT_NAME.lower()}_{safe_filename}"
            
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True, check=True
            )
            killed_count += 1
            system_logger.debug(f"[Sandbox] Зомби-контейнер '{container_name}' (ID: {container_id}) уничтожен.")
        except Exception as e:
            system_logger.error(f"[Sandbox] Не удалось убить зомби-контейнер '{filename}': {e}")
            
    system_logger.info(f"[Sandbox] Зачистка завершена. Уничтожено {killed_count} зомби-контейнеров агента '{AGENT_NAME}'.")