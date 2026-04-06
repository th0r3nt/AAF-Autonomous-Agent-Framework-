from pathlib import Path
from src.cli import ui

# Вычисляем корень проекта (там, где лежит aaf.py)
current_dir = Path(__file__).resolve()
project_root = current_dir.parents[3]

REQUIRED_DIRS = [
    "agent/sandbox",
    "agent/data/kuzu_db",
    "agent/data/chroma_db",
    "agent/data/telegram_sessions",
    "agent/data/shadow_backups",
    "logs",
]


def prevent_docker_root_trap():
    """
    Превентивно создает директории на хосте от имени текущего юзера.
    Предотвращает создание папок Докером от имени root.
    """
    ui.info("Проверка файловой структуры (защита от Docker Root Trap).")

    for dir_path in REQUIRED_DIRS:
        full_path = project_root / dir_path

        try:
            if not full_path.exists():
                full_path.mkdir(parents=True, exist_ok=True)

        except PermissionError:
            ui.fatal(
                f"Отказано в доступе при создании '{dir_path}'.\n"
                "Убедитесь, что у вас есть права на запись в папку проекта."
            )

    ui.success("Структура директорий подготовлена.")


def run_all_fs_checks():
    prevent_docker_root_trap()
