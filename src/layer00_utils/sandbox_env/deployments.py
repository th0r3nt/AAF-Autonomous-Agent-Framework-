import asyncio
import subprocess
import socket
import os

from src.layer00_utils.logger import system_logger
from src.layer00_utils.workspace import workspace_manager
from src.layer00_utils.env_manager import AGENT_NAME

from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events

# Глобальный кэш для защиты от спама алертами
_alerted_crashes = set()

async def deploy_project(vfs_path: str, project_name: str, env_vars: dict = None, entrypoint: str = "main.py") -> str:
    """
    Собирает и запускает полноценный Docker-контейнер (микросервис) из папки в песочнице.
    """
    try:
        # 1. Проверки безопасности и путей
        project_dir = workspace_manager.resolve_vfs_path(vfs_path, mode='read')
        if not project_dir.exists() or not project_dir.is_dir():
            return f"[Error] Директория проекта '{vfs_path}' не найдена."
            
        # Очищаем имя проекта (только a-z, 0-9, _)
        safe_name = "".join(c if c.isalnum() or c == "_" else "" for c in project_name.lower())
        container_name = f"aaf_proj_{AGENT_NAME.lower()}_{safe_name}"
        image_name = f"image_{container_name}"

        system_logger.info(f"[Deployments] Инициализация деплоя '{container_name}' из '{vfs_path}'...")

        # Инъекция agent_sdk.py
        import shutil
        sdk_source = workspace_manager.sandbox_dir / "agent_sdk.py"
        sdk_target = project_dir / "agent_sdk.py"
        # Если в корне есть SDK, а в проекте его еще нет - копируем
        if sdk_source.exists() and not sdk_target.exists():
            shutil.copy2(sdk_source, sdk_target)
            system_logger.debug(f"[Deployments] Системный 'agent_sdk.py' автоматически скопирован в '{project_name}'")

        # 2. Автогенерация Dockerfile (если агент, чертила, его не написал)
        dockerfile_path = project_dir / "Dockerfile"
        if not dockerfile_path.exists():
            req_exists = (project_dir / "requirements.txt").exists()
            pip_install = "RUN pip install --no-cache-dir -r requirements.txt" if req_exists else ""
            
            dockerfile_content = f"""
            FROM aaf-sandbox-base:latest 
            WORKDIR /app
            COPY . /app
            {pip_install}
            CMD ["python", "-u", "{entrypoint}"]
            """
            with open(dockerfile_path, "w", encoding="utf-8") as f:
                f.write(dockerfile_content.strip())
            system_logger.debug(f"[Deployments] Сгенерирован базовый Dockerfile для '{project_name}'")

        # Высчитываем абсолютный путь внутри DinD контейнера (sandbox_engine)
        rel_path = project_dir.relative_to(workspace_manager.sandbox_dir).as_posix()
        dind_project_path = f"/app/Agents/{AGENT_NAME}/workspace/sandbox/{rel_path}"

        # 3. Сборка образа (Build)
        build_cmd = ["docker", "build", "-t", image_name, "."]
        build_proc = await asyncio.create_subprocess_exec(
            *build_cmd, cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await build_proc.communicate()
        
        if build_proc.returncode != 0:
            err = stderr.decode('utf-8', errors='replace')
            return f"[Build Error] Ошибка сборки Docker-образа:\n{err[-1000:]}"

        # Убиваем старый контейнер, если он был
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

        # Динамически получаем IP ядра агента 
        agent_alias = f"agent_{AGENT_NAME.lower()}"
        try:
            agent_ip = socket.gethostbyname(agent_alias)
        except Exception:
            agent_ip = agent_alias # Фоллбэк, если DNS шалит
            
        # Подготовка переменных окружения
        env_args = [
            "-e", f"MASTER_AGENT={agent_ip}",
            "-e", f"TZ={os.getenv('TZ', 'UTC')}"
        ]
        
        if env_vars:
            for k, v in env_vars.items():
                env_args.extend(["-e", f"{k}={v}"])

        # Запуск контейнера 
        run_cmd =[
            "docker", "run", "-d",
            "--name", container_name,
            "--memory=512m", "--cpus=1.0", "--pids-limit=100",
            "--restart=unless-stopped",
            "--network=host", # Проект будет доступен по localhost внутри DinD
            "-v", f"{dind_project_path}:/app" # Проброс папки (Stateful)
        ] + env_args + [image_name]

        run_proc = await asyncio.create_subprocess_exec(
            *run_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await run_proc.communicate()

        # Золотой стандарт: Health Check (ждем 3 секунды)
        await asyncio.sleep(3)
        inspect_proc = await asyncio.create_subprocess_exec(
            "docker", "inspect", "-f", "{{.State.Status}}|{{.State.ExitCode}}", container_name,
            stdout=asyncio.subprocess.PIPE
        )
        out, _ = await inspect_proc.communicate()
        status_info = out.decode('utf-8').strip().split('|')

        if len(status_info) == 2 and status_info[0] == "exited":
            # Контейнер упал! Читаем логи и удаляем труп
            logs_proc = await asyncio.create_subprocess_exec(
                "docker", "logs", "--tail=50", container_name,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            l_out, l_err = await logs_proc.communicate()
            logs = (l_out + l_err).decode('utf-8', errors='replace')
            
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
            return f"[Crash Report] Деплой провалился. Контейнер упал после старта (Exit Code: {status_info[1]}).\nЛоги ошибки:\n{logs}"

        system_logger.info(f"[Deployments] Проект '{project_name}' успешно запущен!")
        return f"Деплой успешен. Контейнер '{container_name}' работает в фоне."

    except PermissionError as e:
        return str(e)
    except Exception as e:
        system_logger.error(f"[Deployments] Системная ошибка деплоя: {e}")
        return f"[System Error] Внутренняя ошибка при деплое: {e}"
    
async def manage_deployments(project_name: str, action: str, lines: int = 100) -> str:
    """Управление жизненным циклом запущенных микросервисов"""
    safe_name = "".join(c if c.isalnum() or c == "_" else "" for c in project_name.lower())
    container_name = f"aaf_proj_{AGENT_NAME.lower()}_{safe_name}"

    try:
        if action == "logs":
            proc = await asyncio.create_subprocess_exec(
                "docker", "logs", f"--tail={lines}", container_name,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            out, err = await proc.communicate()
            logs = (out + err).decode('utf-8', errors='replace')
            return f"Логи контейнера '{container_name}':\n\n{logs}" if logs else "Логи пусты."

        elif action == "stop":
            subprocess.run(["docker", "stop", container_name], capture_output=True)
            return f"Контейнер '{container_name}' остановлен."

        elif action == "restart":
            subprocess.run(["docker", "restart", container_name], capture_output=True)
            return f"Контейнер '{container_name}' перезапущен."

        elif action == "destroy":
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
            # Удаляем образ, чтобы не забивать диск
            image_name = f"image_{container_name}"
            subprocess.run(["docker", "rmi", "-f", image_name], capture_output=True)
            return f"Контейнер '{container_name}' и его образ полностью уничтожены. Папка проекта в VFS сохранена."

        elif action == "stats":
            proc = await asyncio.create_subprocess_exec(
                "docker", "stats", "--no-stream", "--format", "CPU: {{.CPUPerc}} | RAM: {{.MemUsage}}", container_name,
                stdout=asyncio.subprocess.PIPE
            )
            out, _ = await proc.communicate()
            stats = out.decode('utf-8').strip()
            return f"Статистика '{container_name}': {stats}" if stats else "Контейнер выключен или не существует."

        else:
            return f"Неизвестное действие: {action}"

    except Exception as e:
        return f"[System Error] Ошибка управления деплоем: {e}"
    
async def get_active_deployments_status() -> str:
    """Собирает список запущенных проектов для системного промпта агента"""
    prefix = f"aaf_proj_{AGENT_NAME.lower()}_"
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "ps", "-a", "--filter", f"name=^{prefix}", "--format", "{{.Names}}|{{.State}}|{{.Status}}",
            stdout=asyncio.subprocess.PIPE
        )
        out, _ = await proc.communicate()
        output = out.decode('utf-8').strip()
        
        if not output:
            return "Нет запущенных микросервисов."
            
        lines = []
        for line in output.split('\n'):
            parts = line.split('|')
            if len(parts) >= 3:
                name = parts[0].replace(prefix, "")
                state = parts[1].upper()
                status_desc = parts[2]
                lines.append(f"- [{name}] | State: {state} | Info: {status_desc}")
                
        return "\n".join(lines)
    except Exception as e:
        return f"[Ошибка получения статуса деплоев: {e}]"

async def monitor_deployments_loop():
    """Фоновый WatchDog: проверяет, не упали ли к чертям микросервисы агента"""
    prefix = f"aaf_proj_{AGENT_NAME.lower()}_"
    
    while True:
        await asyncio.sleep(60) # Проверяем раз в минуту
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "ps", "-a", "--filter", f"name=^{prefix}", "--format", "{{.Names}}|{{.State}}|{{.Status}}",
                stdout=asyncio.subprocess.PIPE
            )
            out, _ = await proc.communicate()
            output = out.decode('utf-8').strip()
            
            if not output:
                _alerted_crashes.clear()
                continue
                
            current_crashed = set()
            
            for line in output.split('\n'):
                parts = line.split('|')
                if len(parts) >= 3:
                    container_name = parts[0]
                    state = parts[1]
                    status_desc = parts[2]
                    project_name = container_name.replace(prefix, "")
                    
                    # Если контейнер упал (exited, но не был остановлен вручную)
                    if state == "exited" and "Exited (0)" not in status_desc:
                        current_crashed.add(project_name)
                        
                        if project_name not in _alerted_crashes:
                            _alerted_crashes.add(project_name)
                            system_logger.warning(f"[Deployments] Микросервис '{project_name}' упал. Отправка Alert агенту.")
                            
                            # Пуляем в EventBus прерывание!
                            await event_bus.publish(
                                Events.DEPLOYMENT_CRASHED, 
                                project=project_name, 
                                status=status_desc
                            )
                    elif state == "running":
                        # Если контейнер починили и он снова работает, убираем из кэша крашей
                        if project_name in _alerted_crashes:
                            _alerted_crashes.remove(project_name)
                            
        except Exception as e:
            system_logger.error(f"[Deployments] Ошибка в мониторе: {e}")