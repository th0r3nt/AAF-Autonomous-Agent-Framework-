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

def compose_up(dev_mode: bool = False) -> bool:
    """Поднимает контейнеры. Возвращает True при успехе."""
    cmd = ["docker", "compose", "up", "-d", "--build"]
    if dev_mode:
        cmd.extend(["postgres", "rabbitmq"])
        msg = "Сборка и запуск инфраструктуры (DEV режим)."
    else:
        msg = "Сборка и запуск фреймворка AAF."

    with ui.console.status(f"[bold green]{msg}[/bold green]", spinner="bouncingBar"):
        result = _run_cmd(cmd, cwd=project_root)

        if result.returncode != 0:
            ui.error("Ошибка при запуске Docker Compose:")
            ui.console.print(result.stderr)
            return False # Возвращаем False, меню не закроется

    ui.success("Контейнеры успешно стартовали.")
    return True

def compose_down(remove_volumes: bool = False) -> bool:
    """Останавливает и удаляет контейнеры."""
    cmd = ["docker", "compose", "down"]
    if remove_volumes:
        cmd.append("-v")
        ui.warning("Флаг -v активирован. Внимание: тома баз данных будут удалены.")

    with ui.console.status("[bold yellow]Остановка контейнеров AAF.[/bold yellow]"):
        result = _run_cmd(cmd, cwd=project_root)

        if result.returncode != 0:
            ui.error("Ошибка при остановке Docker Compose:")
            ui.console.print(result.stderr)
            return False

    ui.success("Система AAF полностью остановлена.")
    return True

def monitor_health() -> bool:
    """
    Мониторит статус контейнера aaf_core в течение 15 секунд.
    """
    ui.info("Ожидание стабилизации ядра агента (до 15 секунд)...")
    container_name = "aaf_core"

    with ui.console.status("[bold cyan]Мониторинг пульса aaf_core...[/bold cyan]"):
        time.sleep(6) # Ожидание стабилизации БД и Кролика

        for attempt in range(10):
            time.sleep(1)
            result = _run_cmd(
                ["docker", "inspect", "-f", "{{.State.Status}}", container_name],
                cwd=project_root,
            )
            status = result.stdout.strip().lower()

            if status == "running":
                if attempt >= 3:
                    ui.success(f"Ядро агента стабильно (Статус: {status.upper()}).")
                    ui.console.print("\n[bold green]🚀 Фреймворк AAF успешно запущен![/bold green]")
                    return True
            elif status in ["exited", "restarting", "dead"]:
                ui.error(f"Контейнер {container_name} перешел в аварийный статус: {status.upper()}")
                break

    return _handle_crash(container_name)

def _handle_crash(container_name: str) -> bool:
    """Вытягивает логи упавшего контейнера, показывает их красиво и возвращает в меню."""
    ui.console.print("\n[bold red]КРИТИЧЕСКАЯ ОШИБКА ПРИ СТАРТЕ[/bold red]")
    ui.info(f"Получение последних логов из {container_name}...")

    result = _run_cmd(["docker", "logs", container_name, "--tail", "30"], cwd=project_root)
    logs = result.stderr.strip() or result.stdout.strip()

    if logs:
        from rich.panel import Panel
        ui.console.print(
            Panel(logs, title="[bold red]Traceback / Logs[/bold red]", border_style="red")
        )
    else:
        ui.warning("Логи пусты. Возможно, контейнер даже не успел запуститься.")

    ui.error("Запуск AAF прерван из-за падения системы. Исправьте ошибку и попробуйте снова.")
    return False