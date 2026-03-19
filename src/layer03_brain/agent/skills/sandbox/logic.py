import asyncio
from src.layer00_utils.env_manager import AGENT_NAME

from src.layer00_utils.workspace import workspace_manager
from src.layer00_utils.sandbox_env.executor import execute_once
from src.layer00_utils.sandbox_env.deployments import deploy_project, manage_deployments
from src.layer03_brain.agent.skills.auto_schema import llm_skill

@llm_skill(
    description="Разово выполняет Python-скрипт. Поднимает изолированный микро-контейнер, выдает результат и мгновенно умирает. Внутри скрипта необходимо использовать только относительные пути к файлам. Для доступа к микросервисам - 127.0.0.1.",
    parameters={"filepath": "VFS путь к скрипту в песочнице (например: 'sandbox/scripts/parser.py')"}
)
async def execute_script(filepath: str) -> str:
    return await execute_once(filepath)

@llm_skill(
    description="Полностью очищает папку временных файлов."
)
def clean_temp_workspace() -> str:
    return workspace_manager.clean_temp_workspace()

@llm_skill(
    description="Деплоит полноценный микросервис (Docker-контейнер) из папки проекта в Sandbox. Контейнер будет работать 24/7. Все микросервисы и скрипты делят общую сеть. Общение между ними происходит по localhost:<port> или 127.0.0.1:<port>.",
    parameters={
        "vfs_path": "VFS путь к папке проекта (например: 'sandbox/projects/my_api').",
        "project_name": "Уникальное имя для проекта (только латиница, цифры и '_').",
        "env_vars": "(Опционально) Словарь переменных окружения. Например: {'TOKEN': '123'}.",
        "entrypoint": "(Опционально) Главный файл запуска (по умолчанию 'main.py')."
    }
)
async def deploy_sandbox_project(vfs_path: str, project_name: str, env_vars: dict = None, entrypoint: str = "main.py") -> str:
    return await deploy_project(vfs_path, project_name, env_vars, entrypoint)

@llm_skill(
    description="Управление жизненным циклом запущенных микросервисов (чтение логов, перезапуск, удаление и т.д.).",
    parameters={
        "project_name": "Имя проекта, которое было указано при деплое.",
        "action": {"description": "Действие с контейнером.", "enum": ["logs", "stop", "restart", "destroy", "stats"]},
        "lines": "(Опционально) Количество строк лога для чтения (по умолчанию 100, только для action='logs')."
    }
)
async def manage_sandbox_deployments(project_name: str, action: str, lines: int = 100) -> str:
    return await manage_deployments(project_name, action, lines)

@llm_skill(
    description="Выполняет shell-команду внутри работающего микросервиса (Docker-контейнера). Полезно для 'ls', 'cat', 'pip install' или запуска миграций.",
    parameters={
        "project_name": "Имя проекта.",
        "command": "Shell-команда (например: 'pip install bs4' или 'ls -la')."
    }
)
async def run_command_in_container(project_name: str, command: str) -> str:
    safe_name = "".join(c if c.isalnum() or c == "_" else "" for c in project_name.lower())
    container_name = f"aaf_proj_{AGENT_NAME.lower()}_{safe_name}"
    
    try:
        # Проверяем, жив ли контейнер
        check_proc = await asyncio.create_subprocess_exec(
            "docker", "inspect", "-f", "{{.State.Running}}", container_name,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        out, _ = await check_proc.communicate()
        if out.decode().strip() != "true":
            return f"Ошибка: Микросервис '{project_name}' не запущен или упал."

        # Выполняем команду
        cmd_list = ["docker", "exec", container_name, "sh", "-c", command]
        proc = await asyncio.create_subprocess_exec(
            *cmd_list,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        
        # Даем 60 секунд на выполнение (например, для долгого pip install)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        
        out_str = stdout.decode('utf-8', errors='replace').strip()
        err_str = stderr.decode('utf-8', errors='replace').strip()
        
        result = f"--- STDOUT ---\n{out_str if out_str else 'Пусто'}"
        if err_str:
            result += f"\n\n--- STDERR ---\n{err_str}"
            
        # ЗАЩИТА ОТ ДУРАКА: Если агент сделал pip install, напоминаем ему об архитектуре
        if "pip install" in command:
            result += "\n\n[Системное предупреждение]: Пакет установлен в работающий контейнер. Если контейнер перезапустится, пакет исчезнет. Рекомендуется добавить эту библиотеку в 'requirements.txt' проекта, если необходимо."
            
        return result
        
    except asyncio.TimeoutError:
        return f"Ошибка: Команда '{command}' превысила таймаут (60 сек)."
    except Exception as e:
        return f"Системная ошибка: {e}"