import subprocess
import time
from pathlib import Path
from src.cli import ui

# Корень проекта, где лежит docker-compose.yml
current_dir = Path(__file__).resolve()
project_root = current_dir.parents[3]


def _run_cmd(cmd: list, cwd: Path) -> subprocess.CompletedProcess:
    """Вспомогательная функция для запуска shell-команд."""
    return subprocess.run(
        cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


def compose_up(dev_mode: bool = False):
    """Поднимает контейнеры. В dev_mode - только инфраструктуру."""

    cmd = ["docker", "compose", "up", "-d", "--build"]
    if dev_mode:
        # Поднимаем только базы, без агента
        cmd.extend(["postgres", "rabbitmq"])
        msg = "Сборка и запуск инфраструктуры (DEV режим)."
    else:
        msg = "Сборка и запуск фреймворка AAF."

    # Используем спиннер от Rich, чтобы юзер не скучал
    with ui.console.status(f"[bold green]{msg}[/bold green]", spinner="bouncingBar"):
        result = _run_cmd(cmd, cwd=project_root)

        if result.returncode != 0:
            ui.fatal(f"Ошибка при запуске Docker Compose:\n{result.stderr}")

    ui.success("Контейнеры успешно стартовали.")


def compose_down(remove_volumes: bool = False):
    """Останавливает и удаляет контейнеры."""
    cmd = ["docker", "compose", "down"]
    if remove_volumes:
        cmd.append("-v")
        ui.warning("Флаг -v активирован. Внимание: тома баз данных будут удалены.")

    with ui.console.status("[bold yellow]Остановка контейнеров AAF.[/bold yellow]"):
        result = _run_cmd(cmd, cwd=project_root)

        if result.returncode != 0:
            ui.fatal(f"Ошибка при остановке Docker Compose:\n{result.stderr}")

    ui.success("Система AAF полностью остановлена.")


def monitor_health():
    """
    Мониторит статус контейнера aaf_core в течение 15 секунд.
    Если контейнер падает - выводит логи и прерывает работу.
    """
    ui.info("Ожидание стабилизации ядра агента (до 15 секунд)...")
    container_name = "aaf_core"

    with ui.console.status("[bold cyan]Мониторинг пульса aaf_core...[/bold cyan]"):
        # Ждем 6 секунд ПЕРЕД началом проверок, чтобы пропустить 'sleep 5' из compose
        time.sleep(6)

        for attempt in range(10):  # Оставшиеся 10 секунд проверяем реальный статус Python
            time.sleep(1)
            result = _run_cmd(
                ["docker", "inspect", "-f", "{{.State.Status}}", container_name],
                cwd=project_root,
            )
            status = result.stdout.strip().lower()

            if status == "running":
                # Если после слипа он жив хотя бы 3 секунды - всё отлично
                if attempt >= 3:
                    ui.success(f"Ядро агента стабильно (Статус: {status.upper()}).")
                    ui.console.print(
                        "\n[bold green]🚀 Фреймворк AAF успешно запущен![/bold green]"
                    )
                    return
            elif status in ["exited", "restarting", "dead"]:
                ui.error(
                    f"Контейнер {container_name} перешел в аварийный статус: {status.upper()}"
                )
                break

    _handle_crash(container_name)


def _handle_crash(container_name: str):
    """Вытягивает логи упавшего контейнера и красиво их показывает."""
    ui.console.print("\n[bold red]КРИТИЧЕСКАЯ ОШИБКА ПРИ СТАРТЕ[/bold red]")
    ui.info(f"Получение последних логов из {container_name}.")

    result = _run_cmd(["docker", "logs", container_name, "--tail", "30"], cwd=project_root)
    logs = result.stderr.strip() or result.stdout.strip()

    if logs:
        # Оборачиваем логи в красивую панель
        from rich.panel import Panel

        ui.console.print(
            Panel(logs, title="[bold red]Traceback / Logs[/bold red]", border_style="red")
        )
    else:
        ui.warning("Логи пусты. Возможно, контейнер даже не успел запуститься.")

    ui.fatal("Запуск AAF прерван из-за падения системы. Исправьте ошибку и попробуйте снова.")
