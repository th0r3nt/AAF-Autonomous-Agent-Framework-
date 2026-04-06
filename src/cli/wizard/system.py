import subprocess
from src.cli import ui


def check_docker_installed():
    """Проверяет, установлен ли Docker и Docker Compose."""
    try:
        # Проверяем наличие docker
        subprocess.run(
            ["docker", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        # Проверяем наличие docker compose (v2)
        subprocess.run(
            ["docker", "compose", "version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        ui.fatal(
            "Docker или Docker Compose не установлены.\n"
            "Установите Docker Desktop (Windows/Mac) или Docker Engine (Linux)."
        )


def check_docker_daemon():
    """Проверяет, запущен ли демон Docker (отвечает ли он)."""
    try:
        subprocess.run(
            ["docker", "info"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
    except subprocess.CalledProcessError:
        ui.fatal(
            "Docker установлен, но демон не запущен.\n"
            "Пожалуйста, запустите Docker Desktop или службу docker."
        )


def run_all_system_checks():
    """Запускает все системные проверки."""
    ui.info("Проверка системы и Docker.")
    check_docker_installed()
    check_docker_daemon()
    ui.success("Docker готов к работе.")
