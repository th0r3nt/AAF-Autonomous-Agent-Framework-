import yaml
import shutil
from pathlib import Path
from src.cli import ui

current_dir = Path(__file__).resolve()
config_dir = current_dir.parents[2] / "agent" / "config" 
settings_path = config_dir / "settings.yaml"
settings_example = config_dir / "settings.example.yaml"


def ensure_settings_exists():
    """Проверяет наличие settings.yaml, если нет - копирует из settings.example.yaml"""
    config_dir.mkdir(parents=True, exist_ok=True)
    if not settings_path.exists():
        if settings_example.exists():
            shutil.copy(settings_example, settings_path)
            ui.info("Файл settings.yaml создан из шаблона.")
        else:
            ui.fatal("Не найден settings.example.yaml. Восстановите его из репозитория.")


def validate_yaml_syntax():
    """Читает YAML. Если есть синтаксическая ошибка (например, табы) - совершает сэппуку с красивой ошибкой."""
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            yaml.safe_load(f)
    except yaml.YAMLError as exc:
        ui.fatal(
            f"Синтаксическая ошибка в settings.yaml.\n"
            f"Убедитесь, что вы используете пробелы, а не TAB.\nДетали:\n{exc}"
        )


def run_settings_checks():
    ui.info("Проверка settings.yaml.")
    ensure_settings_exists()
    validate_yaml_syntax()
    ui.success("Файл настроек валиден.")
