import asyncio
import os
import socket

from src.layer00_utils.logger import system_logger
from src.layer00_utils.workspace import workspace_manager
from src.layer00_utils.env_manager import AGENT_NAME
from src.layer00_utils.config_manager import config

MAX_OUTPUT_LENGTH = config.llm.limits.max_file_read_chars 

def _truncate_output(text: str) -> str:
    if not text:
        return ""
    if len(text) > MAX_OUTPUT_LENGTH:
        half = MAX_OUTPUT_LENGTH // 2
        return text[:half] + "\n\n... [ВЫВОД ОБРЕЗАН ИЗ-ЗА ЛИМИТОВ КОНТЕКСТА] ...\n\n" + text[-half:]
    return text

async def execute_once(vfs_filepath: str, timeout: int = 120) -> str:
    try:
        # Проверяем путь через новый резолвер
        filepath = workspace_manager.resolve_vfs_path(vfs_filepath, mode='read')
        
        if not filepath.exists():
            return f"[Error] Файл '{vfs_filepath}' не найден."

        # Гарантируем, что запуск происходит строго из песочницы
        if not vfs_filepath.startswith("sandbox/"):
            return "[Error] Выполнение скриптов разрешено только из директории 'sandbox/'."

        # Высчитываем путь относительно корня песочницы
        rel_path = filepath.relative_to(workspace_manager.sandbox_dir).as_posix()
        script_dir = os.path.dirname(rel_path)
        script_name = os.path.basename(rel_path)

        system_logger.info(f"[Sandbox] Запуск '{vfs_filepath}' в Docker DinD (Агент: {AGENT_NAME}, Таймаут: {timeout}с).")

        sandbox_root_in_docker = f"/app/Agents/{AGENT_NAME}/workspace/sandbox"
        working_dir_in_docker = f"{sandbox_root_in_docker}/{script_dir}" if script_dir else sandbox_root_in_docker

        agent_alias = f"agent_{AGENT_NAME.lower()}"
        try:
            agent_ip = socket.gethostbyname(agent_alias)
        except Exception:
            agent_ip = agent_alias

        docker_cmd =[
            "docker", "run",
            "--rm",                                         
            "--memory=1g",                                  
            "--cpus=1",                                     
            "--pids-limit=100", 
            "--network=host",
            "-e", f"MASTER_AGENT={agent_ip}", # Пробрасываем чистый IP
            "-e", f"TZ={os.getenv('TZ', 'UTC')}",
            "-v", f"{sandbox_root_in_docker}:{sandbox_root_in_docker}",         
            "-w", working_dir_in_docker,
            "aaf-sandbox-base:latest",                             
            "python", script_name                              
        ]

        process = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except OSError:
                pass
            system_logger.warning(f"[Sandbox] Скрипт '{vfs_filepath}' превысил таймаут {timeout}с и был жестоко убит (без суда и следствия).")
            return f"[Timeout Error] Скрипт выполнялся дольше {timeout} секунд."

        out_str = stdout.decode('utf-8', errors='replace').strip()
        err_str = stderr.decode('utf-8', errors='replace').strip()

        out_str = _truncate_output(out_str)
        err_str = _truncate_output(err_str)

        result = f"--- STDOUT ---\n{out_str if out_str else 'Пусто'}"
        if err_str:
            result += f"\n\n--- STDERR ---\n{err_str}"

        system_logger.debug(f"[Sandbox] Выполнение '{vfs_filepath}' завершено (Код выхода: {process.returncode}).")
        return result

    except PermissionError as e:
        return f"[Security] {e}"
    except Exception as e:
        system_logger.error(f"[Sandbox] Ошибка выполнения '{vfs_filepath}': {e}")
        return f"[System Error] Внутренняя ошибка песочницы: {e}"