# Проверка базовых зависимостей и окружения перед импортом остальных модулей
from src.cli.requirement_manager import check_and_install_dependencies

check_and_install_dependencies()

import os  # noqa: E402
import sys  # noqa: E402
import platform  # noqa: E402
import subprocess  # noqa: E402
import shutil  # noqa: E402
import typer  # noqa: E402
import questionary  # noqa: E402

from src.cli import ui  # noqa: E402
from src.cli import main as conductor  # noqa: E402

# Инициализируем Typer приложение
app = typer.Typer(
    name="AAF",
    help="Autonomous Agentic Framework CLI",
    add_completion=False,
    invoke_without_command=True,  # Позволяет запускать aaf.py без аргументов
)


def clear_screen():
    """Очищает консоль для красивой перерисовки меню."""
    os.system("cls" if os.name == "nt" else "clear")


def open_logs_in_new_window():
    """
    Определяет операционную систему и запускает стрим логов
    в новом независимом окне терминала.
    """
    cmd = "docker logs -f aaf_core"
    curr_os = platform.system()

    try:

        # Проверяем, существует ли вообще контейнер aaf_core
        check = subprocess.run(
            ["docker", "ps", "-a", "-q", "-f", "name=aaf_core"], 
            stdout=subprocess.PIPE, 
            text=True
        )
        
        if not check.stdout.strip():
            ui.error("Контейнер 'aaf_core' не найден. Сейчас активирован в Dev-режим/система еще не стартовала.")
            return

        cmd = "docker logs -f aaf_core"

        if curr_os == "Windows":
            # /k оставляет окно открытым даже при прерывании
            subprocess.Popen(f'start cmd.exe /k "{cmd}"', shell=True)

        elif curr_os == "Darwin":  # macOS
            apple_script = f'tell application "Terminal" to do script "{cmd}"'
            subprocess.Popen(["osascript", "-e", apple_script])

        elif curr_os == "Linux":
            # Разные терминалы требуют разные флаги для передачи команды
            terminals = {
                "gnome-terminal": ["--", "bash", "-c", f"{cmd}; exec bash"],
                "konsole": ["-e", "bash", "-c", f"{cmd}; exec bash"],
                "xfce4-terminal": ["-e", f'bash -c "{cmd}; exec bash"'],
                "alacritty": ["-e", "bash", "-c", f"{cmd}; exec bash"],
                "xterm": ["-e", "bash", "-c", f"{cmd}; exec bash"],
            }

            for term, args in terminals.items():
                if shutil.which(term):
                    subprocess.Popen([term] + args)
                    return
            ui.warning(
                "Не удалось автоматически определить терминал Linux. Откройте новое окно и введите: docker logs -f aaf_core"
            )

        else:
            ui.warning(f"ОС {curr_os} не поддерживается для авто-открытия окон.")

    except Exception as e:
        ui.error(f"Ошибка при открытии окна логов: {e}")


def interactive_menu():
    """Главный цикл интерактивного меню (State Machine)."""
    while True:
        clear_screen()
        ui.print_banner()

        choice = questionary.select(
            "Добро пожаловать в AAF. Выберите действие:",
            choices=[
                "🚀 Запустить AAF",
                "⏹️  Остановить AAF",
                "📋 Открыть логи (в новом окне)",
                "🛠️  Запустить Dev-режим (только инфраструктура БД)",
                "⚙️  Мастер настройки (интерфейсы и ключи)",
                "🧹 Полный сброс (удалить БД и контейнеры)",
                "❌ Выход",
            ],
            instruction="(Используйте стрелочки ↑/↓ и Enter)",
        ).ask()

        # Если юзер нажал Ctrl+C или выбрал Выход
        if choice is None or choice.startswith("❌"):
            ui.info("Выход из лаунчера. До встречи!")
            sys.exit(0)

        clear_screen()
        ui.print_banner()

        # Обработка выбора
        if choice.startswith("🚀"):
            ui.info("Запуск полного стека AAF.")
            conductor.run_startup_sequence(dev_mode=False)

        elif choice.startswith("⏹️"):
            conductor.run_teardown_sequence(remove_volumes=False)

        elif choice.startswith("📋"):
            ui.info("Открытие логов в новом окне.")
            open_logs_in_new_window()
            ui.success("Окно логов запущено!")

        elif choice.startswith("🛠️"):
            ui.info("Запуск в режиме разработчика (Только инфраструктура).")
            conductor.run_startup_sequence(dev_mode=True)

        elif choice.startswith("⚙️"):
            conductor.run_wizard()
            continue

        elif choice.startswith("🧹"):
            # Защита от случайного сноса памяти агента
            ui.warning(
                "Внимание: Это действие необратимо удалит все базы данных (вектора, графы, SQL)."
            )
            confirm = questionary.confirm(
                "Вы уверены, что хотите полностью очистить память агента?", default=False
            ).ask()

            if confirm:
                conductor.run_teardown_sequence(remove_volumes=True)
            else:
                ui.info("Сброс отменен.")

        # Пауза перед возвратом в Главное меню
        print()
        input("[Нажмите Enter, чтобы вернуться в меню]")


@app.callback()
def main(ctx: typer.Context):
    """
    Точка входа. Если переданы аргументы (например, `up --dev`),
    Typer выполнит их. Если аргументов нет — запускаем UI.
    """
    if ctx.invoked_subcommand is None:
        interactive_menu()


# =========================================================
# Старые CLI команды (оставляем для CI/CD и скриптов)
# =========================================================


@app.command()
def up(dev: bool = typer.Option(False, "--dev", help="Запустить только инфраструктуру")):
    """Запускает фреймворк AAF (CLI режим)."""
    ui.print_banner()
    conductor.run_startup_sequence(dev_mode=dev)


@app.command()
def down(volumes: bool = typer.Option(False, "-v", "--volumes", help="Удалить тома БД")):
    """Останавливает систему (CLI режим)."""
    conductor.run_teardown_sequence(remove_volumes=volumes)


@app.command()
def wizard():
    """Запускает мастера настройки (CLI режим)."""
    ui.print_banner()
    conductor.run_wizard()


@app.command()
def logs(tail: int = typer.Option(100, "-n", "--tail", help="Количество строк")):
    """Смотреть логи прямо в текущем окне (CLI режим)."""
    import subprocess

    try:
        subprocess.run(["docker", "logs", "aaf_core", "--tail", str(tail), "-f"])
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    app()
