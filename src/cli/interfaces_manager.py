import yaml
import shutil
from pathlib import Path
import questionary

from src.cli import ui
from src.cli import env_manager

current_dir = Path(__file__).resolve()
config_dir = current_dir.parents[2] / "agent" / "config"
interfaces_path = config_dir / "interfaces.yaml"
interfaces_example = config_dir / "interfaces.example.yaml"


# Карта интерфейсов: (Отображаемое имя, Путь_в_YAML, ID_для_ENV_Manager)
INTERFACES_MAP = [
    ("Telegram Bot (Aiogram)", ["telegram", "bot"], "telegram.bot"),
    ("Telegram Userbot (Telethon)", ["telegram", "userbot"], "telegram.userbot"),
    ("GitHub API", ["api", "github"], "api.github"),
    ("Reddit API", ["api", "reddit"], "api.reddit"),
    ("Habr API", ["api", "habr"], "api.habr"),
    ("Email (IMAP/SMTP)", ["email"], "email"),
    ("Web Browser", ["web", "browser"], "web.browser"),
    ("Web HTTP Requests", ["web", "http"], "web.http"),
    ("Web Search (Google/DDG)", ["web", "search"], "web.search"),
    ("Local Calendar (Cron)", ["calendar"], "calendar"),
    ("System Settings Control", ["system"], "system"),
]


def ensure_interfaces_exists():
    """Проверяет наличие файла, если нет - копирует из шаблона."""
    config_dir.mkdir(parents=True, exist_ok=True)
    if not interfaces_path.exists():
        if interfaces_example.exists():
            shutil.copy(interfaces_example, interfaces_path)
            ui.info("Файл interfaces.yaml создан из шаблона.")
            return True  # Файл только что создан, запускаем визард
        else:
            ui.fatal("Не найден interfaces.example.yaml. Восстановите его из репозитория.")
    return False


def _get_yaml_val(config: dict, path_keys: list, default=False):
    """Безопасно извлекает значение из вложенного словаря."""
    curr = config
    for key in path_keys:
        if isinstance(curr, dict) and key in curr:
            curr = curr[key]
        else:
            return default
    # Обычно нас интересует поле 'enabled'
    return curr.get("enabled", default) if isinstance(curr, dict) else default


def _set_yaml_val(config: dict, path_keys: list, value: bool):
    """Безопасно устанавливает значение во вложенный словарь."""
    curr = config
    for key in path_keys:
        curr = curr.setdefault(key, {})
    curr["enabled"] = value


def run_interactive_wizard() -> bool:
    """Пошаговый интерактивный мастер настройки модулей (State Machine)."""
    
    try:
        with open(interfaces_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        ui.fatal(f"Ошибка чтения interfaces.yaml: {exc}")

    while True:
        ui.clear_screen()
        ui.console.print("\n[bold cyan]МАСТЕР НАСТРОЙКИ ИНТЕРФЕЙСОВ AAF[/bold cyan]")
        ui.info("Выберите модуль, чтобы включить/выключить его.")
        
        # 1. Формируем динамический список кнопок
        choices = []
        
        # Обрабатываем VFS (Файловая система)
        vfs_enabled = _get_yaml_val(config, ["vfs"])
        vfs_level = config.get("vfs", {}).get("madness_level", 0)
        
        vfs_status = "[ON]" if vfs_enabled else "[OFF]"
        vfs_emoji = "🟢" if vfs_enabled else "🔴"
        # : <12 означает выравнивание текста по левому краю шириной ровно 12 символов
        vfs_icon = f"{vfs_emoji} {vfs_status: <12}" 
        
        choices.append(questionary.Choice(title=f"{vfs_icon} VFS (Файловая система) [Lvl: {vfs_level}]", value="vfs_toggle"))
        
        # Обрабатываем остальные модули
        for name, path_keys, env_id in INTERFACES_MAP:
            is_enabled = _get_yaml_val(config, path_keys)
            
            if not is_enabled:
                status_str = "[OFF]"
                emoji = "🔴"
            else:
                has_keys = env_manager.has_credentials(env_id)
                can_be_limited = env_id in env_manager.INTERFACE_CREDENTIALS and not env_manager.INTERFACE_CREDENTIALS[env_id]["required"]
                
                if has_keys:
                    status_str = "[FULL]"
                    emoji = "🟢"
                elif can_be_limited:
                    status_str = "[READ-ONLY]"
                    emoji = "🟡"
                else:
                    status_str = "[NO KEYS]"
                    emoji = "⚠️"

            # То же самое выравнивание до 12 символов
            icon = f"{emoji} {status_str: <12}"

            choices.append(
                questionary.Choice(title=f"{icon} {name}", value=(name, path_keys, env_id, is_enabled))
            )
            
        choices.append(questionary.Separator("   " + "-"*40))
        choices.append(questionary.Choice(title="💾 Сохранить и выйти", value="save"))
        choices.append(questionary.Choice(title="❌ Отмена (без сохранения)", value="cancel"))

        # 2. Запрашиваем действие у пользователя
        selected = questionary.select(
            "Навигация: ↑/↓ | Выбор: Enter",
            choices=choices,
            use_indicator=True
        ).ask()

        # 3. Обработка выбора
        if selected == "cancel" or selected is None:
            ui.warning("Изменения отменены. Возврат в главное меню.")
            return False
            
        elif selected == "save":
            try:
                with open(interfaces_path, "w", encoding="utf-8") as f:
                    yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                ui.success("Конфигурация интерфейсов успешно сохранена.")
                return True
            except Exception as e:
                ui.fatal(f"Ошибка сохранения interfaces.yaml: {e}")
            return False
            
        elif selected == "vfs_toggle":
            # Переключаем VFS
            new_state = not vfs_enabled
            _set_yaml_val(config, ["vfs"], new_state)
            
            if new_state: # Если включили, спрашиваем уровень доступа
                ui.console.print(
                    "\n[dim]Уровни доступа VFS:\n"
                    "0 - Строго в sandbox/ (Безопасно)\n"
                    "1 - Чтение всего проекта, запись в sandbox/\n"
                    "2 - Чтение/Запись всего проекта (Агент может переписать свой код)\n"
                    "3 - God Mode (Выполнение кода на хосте ОС)[/dim]"
                )
                level_str = questionary.select(
                    "Выберите уровень безумия (madness_level):",
                    choices=["0", "1", "2", "3"],
                    default=str(vfs_level)
                ).ask()
                
                if level_str is not None:
                    level = int(level_str)
                    if level == 3:
                        if ui.ask_madness_confirmation():
                            config["vfs"]["madness_level"] = 3
                        else:
                            config["vfs"]["madness_level"] = 1
                    else:
                        config["vfs"]["madness_level"] = level
                else:
                    _set_yaml_val(config, ["vfs"], False) # Если отменил выбор уровня - выключаем VFS
                    
        else:
            # Обработка стандартного модуля
            name, path_keys, env_id, is_enabled = selected
            new_state = not is_enabled
            
            if new_state:
                # Включаем: запрашиваем ключи у env_manager
                keys_ok = env_manager.check_and_prompt_keys(env_id)
                if keys_ok:
                    _set_yaml_val(config, path_keys, True)
                else:
                    ui.error(f"Включение '{name}' отменено (отсутствуют обязательные ключи).")
                    input("\n[Нажмите Enter для продолжения...]")
            else:
                # Выключаем
                _set_yaml_val(config, path_keys, False)


def run_interfaces_checks(force_wizard: bool = False) -> bool:
    ui.info("Проверка конфигурации интерфейсов.")
    is_new = ensure_interfaces_exists()

    # Запускаем визард, если файл только что создан ИЛИ если юзер вызвал его из меню
    if is_new or force_wizard:
        return run_interactive_wizard()

    ui.success("Файлы интерфейсов в порядке.")
    return True # Если визард не запускался, значит всё ок