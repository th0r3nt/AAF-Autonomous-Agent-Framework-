# Файл: src/cli/main.py

from src.cli.wizard import system, network, filesystem
from src.cli import settings_manager, env_manager, interfaces_manager, docker_manager, prompt_manager


def run_startup_sequence(dev_mode: bool = False):
    """
    Главный дирижер запуска. Оркестрирует все проверки строго по очереди.
    """
    # Защита от дурака (Система и порты)
    system.run_all_system_checks()
    network.run_all_network_checks()
    filesystem.run_all_fs_checks()

    # Менеджмент конфигов и промптов
    settings_manager.run_settings_checks()
    interfaces_manager.run_interfaces_checks(force_wizard=False)
    prompt_manager.run_personality_checks()
    env_manager.run_all_env_checks(is_dev_mode=dev_mode)

    # Docker Orchestration
    docker_manager.compose_up(dev_mode=dev_mode)

    # Мониторинг (только если не dev-режим, так как в dev-режиме агент не запускается в докере)
    if not dev_mode:
        docker_manager.monitor_health()


def run_teardown_sequence(remove_volumes: bool = False):
    """Останавливает проект."""
    docker_manager.compose_down(remove_volumes=remove_volumes)


def run_wizard():
    """Принудительный запуск интерактивной настройки."""
    interfaces_manager.run_interfaces_checks(force_wizard=True)
    # env_manager.check_llm_keys() тоже можно вызвать, если нужно обновить ключи
