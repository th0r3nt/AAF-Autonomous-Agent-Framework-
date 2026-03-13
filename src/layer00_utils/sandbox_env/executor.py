import asyncio
from src.layer00_utils.logger import system_logger
from src.layer00_utils.workspace import workspace_manager

# Максимальная длина вывода, которую мы вернем агенту
MAX_OUTPUT_LENGTH = 80000 

def _truncate_output(text: str) -> str:
    """Обрезает слишком длинный текст, оставляя начало и конец"""
    if not text:
        return ""
    if len(text) > MAX_OUTPUT_LENGTH:
        half = MAX_OUTPUT_LENGTH // 2
        return text[:half] + "\n\n... [ВЫВОД ОБРЕЗАН ИЗ-ЗА ЛИМИТОВ КОНТЕКСТА] ...\n\n" + text[-half:]
    return text

async def execute_once(filename: str, timeout: int = 120) -> str:
    """
    Разовый запуск скрипта в изолированном Docker-контейнере с таймаутом.
    Возвращает STDOUT и STDERR.
    """
    try:
        filepath = workspace_manager.get_sandbox_file(filename)
        
        if not filepath.exists():
            return f"[Error] Файл '{filename}' не найден в директории sandbox."

        system_logger.info(f"[Sandbox] Запуск '{filename}' в Docker (Таймаут: {timeout}с).")
        
        import socket
        current_container_id = socket.gethostname()

        docker_cmd = [
            "docker", "run",
            "--rm",                                         
            "--memory=1g",                                  
            "--cpus=1",                                     
            "--pids-limit=100",                             
            "--add-host=host.docker.internal:host-gateway", 
            # Docker-in-Docker: берем ВСЕ вольюмы из текущего контейнера (включая sandbox)
            "--volumes-from", current_container_id,         
            "-w", "/app/workspace/sandbox", # Рабочая директория теперь полная
            "python:3.11-slim",                             
            "python", filename                              
        ]

        # Запускаем процесс Docker асинхронно
        process = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Ждем выполнения с таймаутом
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            # Если зависло, жестко убиваем процесс docker
            try:
                process.kill()
            except OSError:
                pass
            system_logger.warning(f"[Sandbox] Скрипт '{filename}' превысил таймаут {timeout}с и был убит.")
            return f"[Timeout Error] Скрипт выполнялся дольше {timeout} секунд (возможно, долго скачивались библиотеки или возник бесконечный цикл) и был принудительно завершен."

        # Декодируем и обрезаем вывод
        out_str = stdout.decode('utf-8', errors='replace').strip()
        err_str = stderr.decode('utf-8', errors='replace').strip()

        out_str = _truncate_output(out_str)
        err_str = _truncate_output(err_str)

        # Формируем ответ для LLM
        result = f"--- STDOUT ---\n{out_str if out_str else 'Пусто'}"
        if err_str:
            # Docker часто пишет служебную инфу (например от pip) в STDERR, это нормально
            result += f"\n\n--- STDERR ---\n{err_str}"

        system_logger.debug(f"[Sandbox] Выполнение '{filename}' в Docker завершено (Код выхода: {process.returncode}).")
        return result

    except Exception as e:
        system_logger.error(f"[Sandbox] Ошибка выполнения '{filename}': {e}")
        return f"[System Error] Внутренняя ошибка песочницы: {e}"