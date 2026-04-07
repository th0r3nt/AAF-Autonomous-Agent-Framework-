import re
import subprocess
import time
import threading
from collections import deque
from pathlib import Path
import hashlib
import json

from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from src.cli import ui

current_dir = Path(__file__).resolve()
project_root = current_dir.parents[2]


def _run_cmd(cmd: list, cwd: Path) -> subprocess.CompletedProcess:
    """Вспомогательная функция для запуска shell-команд."""
    return subprocess.run(
        cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )


def compose_up(dev_mode: bool = False) -> bool:
    """
    Поднимает контейнеры с асинхронным UI.
    Поддерживает умный кэш сборки и элегантную отмену через Ctrl+C.
    """
    cmd = ["docker", "compose", "--ansi", "never", "up", "-d", "--remove-orphans"]

    needs_build = _is_build_required()
    if needs_build:
        cmd.append("--build")
        ui.info("Обнаружены изменения в Dockerfile/requirements.txt. Инициализация сборки.")

    if dev_mode:
        cmd.extend(["postgres", "rabbitmq"])
        title_msg = "Сборка DEV Инфраструктуры"
    else:
        title_msg = "Сборка Фреймворка AAF"

    log_queue = deque(maxlen=8)
    error_log = deque(maxlen=50)

    process_status = {
        "done": False,
        "return_code": 0,
        "current_step": "Инициализация...",
        "downloaded_mb": 0.0,
    }

    start_time = time.time()

    # Запускаем процесс
    process = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    def _read_stdout():
        size_pattern = re.compile(r"\(([\d.]+)\s*(MB|kB)\)")

        for line in process.stdout:
            clean_line = line.strip()
            if not clean_line:
                continue

            error_log.append(clean_line)

            # Парсинг текущего шага и мегабайт
            if "Downloading" in clean_line:
                process_status["current_step"] = "Скачивание пакетов..."
                match = size_pattern.search(clean_line)
                if match:
                    size_val = float(match.group(1))
                    unit = match.group(2)
                    mb_val = size_val / 1024 if unit == "kB" else size_val
                    process_status["downloaded_mb"] += mb_val

            elif clean_line.startswith("Step "):
                process_status["current_step"] = clean_line.split(" : ")[0]

            elif "Building" in clean_line:
                process_status["current_step"] = "Сборка зависимостей..."

            elif "exporting" in clean_line:
                process_status["current_step"] = "Упаковка образа..."

            short_line = clean_line[:90] + "..." if len(clean_line) > 90 else clean_line
            log_queue.append(short_line)

        process.wait()
        process_status["return_code"] = process.returncode
        process_status["done"] = True

    reader_thread = threading.Thread(target=_read_stdout, daemon=True)
    reader_thread.start()

    def generate_layout() -> Panel:
        elapsed = int(time.time() - start_time)
        mins, secs = divmod(elapsed, 60)
        timer_str = f"{mins:02}:{secs:02}"

        dl_mb = process_status["downloaded_mb"]

        grid = Table.grid(expand=True)
        grid.add_column()
        grid.add_column(justify="right")

        # Шапка с шагом и таймером
        header = Text()
        header.append("⚙ ", style="bold cyan")
        header.append(f"{process_status['current_step']}", style="bold white")

        right_panel = Text()
        if dl_mb > 0:
            right_panel.append(f"📦 {dl_mb:.1f} MB  ", style="bold magenta")

        right_panel.append(f"⏳ {timer_str} ", style="bold yellow")

        grid.add_row(header, right_panel)
        grid.add_row(Text("─" * 80, style="dim"))

        for idx, log_line in enumerate(log_queue):
            style = "dim white" if idx < len(log_queue) - 2 else "bold green"
            grid.add_row(Text(f"  > {log_line}", style=style))

        # Подвал с подсказкой про отмену
        grid.add_row(Text("─" * 80, style="dim"))
        grid.add_row(Text("Нажмите [Ctrl+C] для отмены", style="dim red", justify="center"))

        return Panel(
            grid,
            title=f"[bold cyan]🐳 {title_msg}[/bold cyan]",
            border_style="cyan",
            width=100,
        )

    # Запускаем Live с перехватом KeyboardInterrupt
    try:
        with Live(
            generate_layout(), console=ui.console, refresh_per_second=10, transient=True
        ) as live:
            while not process_status["done"]:
                live.update(generate_layout())
                time.sleep(0.1)

    except KeyboardInterrupt:
        # Если юзер нажал Ctrl+C, убиваем докер-сборку
        ui.console.print(
            "\n[bold yellow]Отмена сборки... Очистка процессов Docker.[/bold yellow]"
        )
        process.terminate()  # Мягко просим процесс завершиться
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()  # Жестко убиваем, если сопротивляется

        ui.warning("Сборка отменена пользователем.")
        return False

    # Проверка результатов после нормального завершения
    if process_status["return_code"] != 0:
        ui.error("Ошибка при сборке и запуске Docker Compose:")
        ui.console.print("\n".join(list(error_log)[-20:]), style="bold red")
        return False
    
    if needs_build:
        _save_build_hash()

    elapsed = int(time.time() - start_time)
    mins, secs = divmod(elapsed, 60)

    total_mb_str = (
        f" ({process_status['downloaded_mb']:.1f} MB)"
        if process_status["downloaded_mb"] > 0
        else ""
    )
    ui.success(f"Контейнеры успешно стартовали за {mins:02}:{secs:02}{total_mb_str}.")
    return True


def compose_down(remove_volumes: bool = False) -> bool:
    """Останавливает и удаляет контейнеры."""
    cmd = ["docker", "compose", "down", "--remove-orphans"]
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
    """Мониторит статус контейнера aaf_core в течение 15 секунд."""
    ui.info("Ожидание стабилизации системы агента (до 15 секунд).")
    container_name = "aaf_core"

    with ui.console.status("[bold cyan]Мониторинг пульса aaf_core.[/bold cyan]"):
        time.sleep(6)  # Ожидание стабилизации БД и Кролика

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
                    ui.console.print(
                        "\n[bold green]🚀 Фреймворк AAF успешно запущен![/bold green]"
                    )
                    return True
            elif status in ["exited", "restarting", "dead"]:
                ui.error(
                    f"Контейнер {container_name} перешел в аварийный статус: {status.upper()}"
                )
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


def _get_build_context_hash() -> str:
    """Считает комбинированный хэш файлов, влияющих на сборку Docker-образа."""
    hasher = hashlib.md5()
    for filename in ["requirements.txt", "Dockerfile"]:
        filepath = project_root / filename
        if filepath.exists():
            hasher.update(filepath.read_bytes())
    return hasher.hexdigest()


def _is_build_required() -> bool:
    """Проверяет, изменились ли файлы сборки с прошлого успешного запуска."""
    hash_file = project_root / "agent" / "data" / ".build_hash.json"
    if not hash_file.exists():
        return True
    try:
        with open(hash_file, "r") as f:
            data = json.load(f)
            return data.get("hash") != _get_build_context_hash()
    except Exception:
        return True


def _save_build_hash():
    """Сохраняет текущий хэш после успешной сборки."""
    hash_file = project_root / "agent" / "data" / ".build_hash.json"
    hash_file.parent.mkdir(parents=True, exist_ok=True)
    with open(hash_file, "w") as f:
        json.dump({"hash": _get_build_context_hash()}, f)
