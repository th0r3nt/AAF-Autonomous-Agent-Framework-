import yaml
import shutil
from pathlib import Path
from src.cli import ui
from rich.prompt import Confirm

current_dir = Path(__file__).resolve()
config_dir = current_dir.parents[3] / "agent" / "config"
interfaces_path = config_dir / "interfaces.yaml"
interfaces_example = config_dir / "interfaces.example.yaml"


def ensure_interfaces_exists():
    config_dir.mkdir(parents=True, exist_ok=True)
    if not interfaces_path.exists():
        if interfaces_example.exists():
            shutil.copy(interfaces_example, interfaces_path)
            ui.info("Файл interfaces.yaml создан из шаблона.")
            return True  # Файл только что создан, значит можно предложить пройти визард
        else:
            ui.fatal("Не найден interfaces.example.yaml. Восстановите его из репозитория.")
    return False


def run_interactive_wizard():
    """Пошаговый опросник для быстрой настройки модулей."""
    ui.console.print("\n[bold cyan]=== МАСТЕР НАСТРОЙКИ ИНТЕРФЕЙСОВ AAF===[/bold cyan]")
    ui.info(
        "Сейчас мы настроим базовые модули агента. Вы можете изменить их позже в interfaces.yaml."
    )

    try:
        with open(interfaces_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        ui.fatal(f"Ошибка чтения interfaces.yaml: {exc}")

    # Настройка VFS
    if Confirm.ask("\nВключить доступ агента к файловой системе (VFS)?", default=True):
        config.setdefault("vfs", {})["enabled"] = True
        ui.console.print(
            "[dim]Уровни доступа VFS:\n"
            "0 - Строго в sandbox/ (Безопасно)\n"
            "1 - Чтение всего проекта, запись в sandbox/\n"
            "2 - Чтение/Запись всего проекта (Может переписать свой код)\n"
            "3 - God Mode (Выполнение кода на хосте ОС)[/dim]"
        )

        level_str = ui.Prompt.ask(
            "Выберите уровень доступа (0-3)", choices=["0", "1", "2", "3"], default="0"
        )
        level = int(level_str)

        if level == 3:
            if ui.ask_madness_confirmation():
                config["vfs"]["madness_level"] = 3
            else:
                config["vfs"]["madness_level"] = 1
        else:
            config["vfs"]["madness_level"] = level
    else:
        config.setdefault("vfs", {})["enabled"] = False

    # Настройка Telegram
    if Confirm.ask("\nВключить Telegram Бота (aiogram)?", default=False):
        config.setdefault("telegram", {}).setdefault("bot", {})["enabled"] = True
        ui.info("Не забудьте добавить TELEGRAM_BOT_TOKEN в файл .env.")
    else:
        config.setdefault("telegram", {}).setdefault("bot", {})["enabled"] = False

    # Настройка Web Search
    if Confirm.ask("\nРазрешить агенту гуглить информацию (Web Search)?", default=True):
        config.setdefault("web", {}).setdefault("search", {})["enabled"] = True
    else:
        config.setdefault("web", {}).setdefault("search", {})["enabled"] = False

    # Сохраняем
    try:
        with open(interfaces_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        ui.success("Конфигурация интерфейсов успешно сохранена.")
    except Exception as e:
        ui.fatal(f"Ошибка сохранения interfaces.yaml: {e}")


def run_interfaces_checks(force_wizard: bool = False):
    ui.info("Проверка interfaces.yaml.")
    is_new = ensure_interfaces_exists()

    # Запускаем визард, если файл только что создан ИЛИ если юзер вызвал команду `wizard`
    if is_new or force_wizard:
        run_interactive_wizard()
    else:
        ui.success("Файл интерфейсов найден и готов.")
