import shutil
from pathlib import Path
from dotenv import set_key, dotenv_values
from src.cli import ui

# Вычисляем корень проекта
current_dir = Path(__file__).resolve()
project_root = current_dir.parents[3]
env_path = project_root / ".env"
env_example_path = project_root / ".env.example"


def ensure_env_exists():
    """Проверяет наличие .env, если нет - копирует из .env.example"""
    if not env_path.exists():
        if env_example_path.exists():
            shutil.copy(env_example_path, env_path)
            ui.info("Файл .env создан из .env.example.")
        else:
            ui.fatal("Не найден файл .env.example. Восстановите его из репозитория.")


def check_llm_keys():
    """Проверяет, есть ли хотя бы один ключ LLM. Если нет - просит ввести."""
    env_vars = dotenv_values(env_path)

    # Ищем любой ключ, начинающийся с LLM_API_KEY_
    has_key = any(k.startswith("LLM_API_KEY_") and v for k, v in env_vars.items())

    if not has_key:
        ui.warning("Не найдено ни одного API ключа для LLM (LLM_API_KEY_...).")
        api_key = ui.Prompt.ask(
            "[cyan]Введите ваш основной API ключ (например, от Gemini/OpenAI)[/cyan]"
        )
        if api_key.strip():
            set_key(str(env_path), "LLM_API_KEY_1", api_key.strip())
            ui.success("Ключ LLM_API_KEY_1 успешно сохранен в .env.")
        else:
            ui.fatal("Ключ не введен. Агент не сможет функционировать без LLM.")


def inject_system_vars(is_dev_mode: bool):
    """
    Подменяет URL баз данных в зависимости от режима запуска.
    Внедряет HOST_WORKSPACE_PATH для работы Sandbox.
    """
    # Инжект абсолютного пути для Docker-out-of-Docker (VFS Sandbox)
    host_path = str(project_root.resolve())
    set_key(str(env_path), "HOST_WORKSPACE_PATH", host_path)

    # Настройка сетевых путей
    if is_dev_mode:
        # Локальная разработка: скрипт на ПК, базы в Докере
        set_key(str(env_path), "RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        set_key(
            str(env_path),
            "SQL_DB_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_db",
        )
        ui.info("Сетевые пути настроены для режима [bold]Dev (localhost)[/bold].")
    else:
        # Боевой запуск: всё внутри изолированной сети aaf_net
        set_key(str(env_path), "RABBITMQ_URL", "amqp://guest:guest@aaf_rabbitmq:5672/")
        set_key(
            str(env_path),
            "SQL_DB_URL",
            "postgresql+asyncpg://postgres:postgres@aaf_postgres:5432/agent_db",
        )
        ui.info("Сетевые пути настроены для режима [bold]Prod (aaf_net)[/bold].")


def run_all_env_checks(is_dev_mode: bool = False):
    ui.info("Проверка переменных окружения (.env).")
    ensure_env_exists()
    check_llm_keys()
    inject_system_vars(is_dev_mode)
    ui.success("Переменные окружения настроены.")
