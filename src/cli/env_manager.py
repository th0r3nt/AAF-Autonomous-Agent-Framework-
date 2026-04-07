import shutil
from pathlib import Path
import questionary
from dotenv import set_key, dotenv_values
from src.cli import ui

# Вычисляем корень проекта
current_dir = Path(__file__).resolve()
project_root = current_dir.parents[2]
env_path = project_root / ".env"
env_example_path = project_root / ".env.example"

# Карта зависимостей: какие ключи нужны для включения конкретных модулей
INTERFACE_CREDENTIALS = {
    "telegram.bot": {
        "keys": ["TELEGRAM_BOT_TOKEN"], 
        "required": True
    },
    "telegram.userbot": {
        "keys": ["TELEGRAM_API_ID", "TELEGRAM_API_HASH"], 
        "required": True
    },
    "api.github": {
        "keys": ["GITHUB_TOKEN_AGENT"], 
        "required": False  # Без токена работает в Read-Only с жесткими лимитами
    },
    "api.reddit": {
        "keys": ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"], 
        "required": True
    },
    "api.habr": {
        "keys": ["HABR_CONNECT_SID", "HABR_CSRF_TOKEN"], 
        "required": False  # Без токена читает статьи анонимно
    },
    "email": {
        "keys": ["EMAIL_ADDRESS", "EMAIL_PASSWORD", "EMAIL_IMAP_SERVER", "EMAIL_SMTP_SERVER"], 
        "required": True
    },
}


def ensure_env_exists():
    """Проверяет наличие .env, если нет - копирует из .env.example"""
    if not env_path.exists():
        if env_example_path.exists():
            shutil.copy(env_example_path, env_path)
            ui.info("Файл .env создан из .env.example.")
        else:
            ui.fatal("Не найден файл .env.example. Восстановите его из репозитория.")

def has_credentials(interface_id: str) -> bool:
    """
    Проверяет наличие ключей для интерфейса БЕЗ запроса ввода.
    Нужно для красивого отображения статуса в меню.
    """
    if interface_id not in INTERFACE_CREDENTIALS:
        return True # Ключи не требуются по определению

    creds = INTERFACE_CREDENTIALS[interface_id]
    keys_to_check = creds["keys"]
    env_vars = dotenv_values(env_path)

    # Если хотя бы один ключ из списка пуст - считаем, что аккаунта нет
    return all(env_vars.get(k) for k in keys_to_check)


def check_and_prompt_keys(interface_id: str) -> bool:
    """
    Проверяет, есть ли ключи для интерфейса в .env. 
    Если их нет - просит ввести. 
    Возвращает True, если ключи готовы к работе, или False, если юзер отменил ввод обязательных ключей.
    """
    if interface_id not in INTERFACE_CREDENTIALS:
        # Для VFS, Web Search и прочих, кому ключи не нужны
        return True

    creds = INTERFACE_CREDENTIALS[interface_id]
    required = creds["required"]
    keys_to_check = creds["keys"]

    env_vars = dotenv_values(env_path)
    missing_keys = []

    for k in keys_to_check:
        if not env_vars.get(k):
            missing_keys.append(k)

    if not missing_keys:
        return True  # Все нужные ключи уже есть

    ui.info(f"Для работы '{interface_id}' требуются ключи/настройки в .env.")
    
    for k in missing_keys:
        # Если это пароль или токен - скрываем ввод звездочками
        is_secret = any(word in k.lower() for word in ["token", "password", "secret", "hash"])
        
        prompt_func = questionary.password if is_secret else questionary.text
        
        val = prompt_func(f"Введите {k} (или нажмите Enter для отмены):").ask()
        
        if val and val.strip():
            set_key(str(env_path), k, val.strip())
            ui.success(f"[{k}] сохранен.")
        else:
            if required:
                ui.warning(f"Ключ {k} обязателен. Модуль не будет включен.")
                return False
            else:
                ui.info(f"Ключ {k} пропущен. Модуль будет работать в Read-Only режиме.")

    return True


def check_llm_keys():
    """Проверяет, есть ли хотя бы один ключ LLM. Если нет - просит ввести."""
    env_vars = dotenv_values(env_path)

    # Ищем любой ключ, начинающийся с LLM_API_KEY_
    has_key = any(k.startswith("LLM_API_KEY_") and v for k, v in env_vars.items())

    if not has_key:
        ui.warning("Не найдено ни одного API ключа для LLM (LLM_API_KEY_*).")
        api_key = questionary.password(
            "Введите ваш основной API ключ (например, от Gemini/OpenAI):"
        ).ask()
        
        if api_key and api_key.strip():
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
        ui.info("Сетевые пути настроены для режима [bold]Development (network: localhost)[/bold].")

    else:
        # Боевой запуск: всё внутри изолированной сети aaf_net
        set_key(str(env_path), "RABBITMQ_URL", "amqp://guest:guest@aaf_rabbitmq:5672/")
        set_key(
            str(env_path),
            "SQL_DB_URL",
            "postgresql+asyncpg://postgres:postgres@aaf_postgres:5432/agent_db",
        )
        ui.info("Сетевые пути настроены для режима [bold]Production (network: aaf_net)[/bold].")


def run_all_env_checks(is_dev_mode: bool = False):
    ui.info("Проверка переменных окружения (.env).")
    ensure_env_exists()
    ui.success("Переменные окружения настроены.")
    check_llm_keys()
    inject_system_vars(is_dev_mode)