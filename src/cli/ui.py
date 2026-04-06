import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

# Инициализируем глобальную консоль
console = Console()

def clear_screen():
    """Очищает консоль для красивой перерисовки меню."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    """Отрисовывает баннер AAF при запуске."""
    banner_text = """
    █████╗  █████╗ ███████╗
   ██╔══██╗██╔══██╗██╔════╝
   ███████║███████║█████╗  
   ██╔══██║██╔══██║██╔══╝  
   ██║  ██║██║  ██║██║     
   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     
   Autonomous Agent Framework
    """
    panel = Panel(
        Text(banner_text, style="bold cyan", justify="center"),
        border_style="cyan",
        title="[bold white]AAF Initializer[/bold white]",
        subtitle="[dim]v1.2.3[/dim]",
    )
    console.print(panel)
    console.print()

def info(msg: str):
    console.print(f"[bold cyan]ℹ[/bold cyan] {msg}")

def success(msg: str):
    console.print(f"[bold green]✔[/bold green] {msg}")

def warning(msg: str):
    console.print(f"[bold yellow]⚠[/bold yellow] {msg}")

def error(msg: str):
    console.print(f"[bold red]✖[/bold red] {msg}")

def fatal(msg: str):
    """Выводит критическую ошибку и убивает скрипт (использовать только для фатальных сбоев самого лаунчера)."""
    console.print(
        Panel(f"[bold red]{msg}[/bold red]", border_style="red", title="FATAL ERROR")
    )
    sys.exit(1)

def show_crash_panel(msg: str, title: str = "ERROR"):
    """Показывает критическую ошибку в панели, но НЕ убивает процесс (для возврата в меню)."""
    console.print(
        Panel(f"[bold red]{msg}[/bold red]", border_style="red", title=f"[bold red]{title}[/bold red]")
    )

def ask_madness_confirmation() -> bool:
    """Пасхалка для God Mode."""
    console.print()
    warning_panel = Panel(
        "[bold red]Агент получит полный доступ к вашей операционной системе.\n"
        "Он сможет читать, писать и удалять любые файлы на вашем хосте, а также выполнять shell-команды.\n"
        "Риски: удаление системных файлов, восстание машин, порабощение.[/bold red]\n\n"
        "[yellow]Для подтверждения введите:[/yellow] [bold white]I UNDERSTAND[/bold white]",
        border_style="red",
        title="[bold red]ИНИЦИАЛИЗАЦИЯ GOD MODE[/bold red]",
    )
    console.print(warning_panel)
    answer = Prompt.ask("[bold red]Ваш ответ[/bold red]")

    if answer.strip().upper() in ["I UNDERSTAND", "Я ПОНИМАЮ"]:
        console.print("[bold purple]Ограничители сняты.[/bold purple]\n")
        return True
    else:
        console.print("[dim green]🛡 Ограничители сохранены. Уровень доступа сброшен до безопасного.[/dim green]\n")
        return False