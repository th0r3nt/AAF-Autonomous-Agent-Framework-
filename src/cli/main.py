from src.cli import model_manager
from src.cli.wizard import system, network, filesystem
from src.cli import (
    settings_manager,
    env_manager,
    interfaces_manager,
    docker_manager,
    prompt_manager,
)


def run_startup_sequence(dev_mode: bool = False):
    # Защита от дурака (Система и порты)
    system.run_all_system_checks()
    network.run_all_network_checks()
    filesystem.run_all_fs_checks()

    # Менеджмент конфигов и промптов
    settings_manager.run_settings_checks()

    if not interfaces_manager.run_interfaces_checks(force_wizard=False):
        return  # Если интерфейсы не настроены и пользователь отменил визард - возвращаемся в меню

    prompt_manager.run_personality_checks()
    env_manager.run_all_env_checks(is_dev_mode=dev_mode)

    if not dev_mode:
        model_manager.check_and_download_models()

    # Docker Orchestration
    success = docker_manager.compose_up(dev_mode=dev_mode)

    # Если Docker не смог собрать или поднять контейнеры - возвращаемся в меню
    if not success:
        return

    if dev_mode:
        from src.cli import ui

        ui.console.print("\n[bold green]✅ DEV Инфраструктура готова.[/bold green]")
        ui.info("Контейнер агента отключен. Теперь необходимо запустить код локально:")
        ui.console.print("  [bold cyan]python -m src.main[/bold cyan]\n")
    else:
        # В боевом режиме ждем, пока поднимется aaf_core
        docker_manager.monitor_health()


def run_teardown_sequence(remove_volumes: bool = False):
    """Останавливает проект."""
    docker_manager.compose_down(remove_volumes=remove_volumes)


def run_wizard():
    """Принудительный запуск интерактивной настройки."""
    interfaces_manager.run_interfaces_checks(force_wizard=True)
