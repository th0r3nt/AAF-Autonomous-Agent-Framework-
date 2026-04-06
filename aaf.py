# Проверка базовых зависимостей и окружения перед импортом остальных модулей
from src.cli.requirement_manager import check_and_install_dependencies

check_and_install_dependencies()

import typer  # noqa: E402
from src.cli import ui  # noqa: E402
from src.cli import main as conductor  # noqa: E402

# Инициализируем Typer приложение
app = typer.Typer(
    name="AAF",
    help="Autonomous Agentic Framework CLI",
    add_completion=False,
)


@app.command()
def up(
    dev: bool = typer.Option(
        False, "--dev", help="Запустить только инфраструктуру для разработки"
    )
):
    """Запускает фреймворк AAF."""
    ui.print_banner()
    if dev:
        ui.info("Запуск в режиме разработчика (Только инфраструктура)...")
    else:
        ui.info("Запуск полного стека AAF...")

    conductor.run_startup_sequence(dev_mode=dev)


@app.command()
def down(
    volumes: bool = typer.Option(False, "-v", "--volumes", help="Удалить тома баз данных")
):
    """Останавливает систему."""
    conductor.run_teardown_sequence(remove_volumes=volumes)


@app.command()
def wizard():
    """Запускает мастера настройки."""
    ui.print_banner()
    conductor.run_wizard()


@app.command()
def logs(
    tail: int = typer.Option(100, "-n", "--tail", help="Количество выводимых строк"),
    follow: bool = typer.Option(True, "-f", "--follow", help="Следить за логами"),
):
    """Удобный просмотр логов главного агента."""
    import subprocess

    cmd = ["docker", "logs", "aaf_core", "--tail", str(tail)]
    if follow:
        cmd.append("-f")
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    app()
