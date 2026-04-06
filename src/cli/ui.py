import os
import sys
import time
import random
import textwrap
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.live import Live

# Инициализируем глобальную консоль
console = Console()

def clear_screen():
    """Очищает консоль для красивой перерисовки меню."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    """Отрисовывает баннер AAF при запуске."""
    # textwrap.dedent уберет отступы самого кода Питона, 
    # чтобы justify="center" сработал идеально ровно по центру терминала.
    banner_text = textwrap.dedent("""
                                  
          █████╗  █████╗ ███████╗
         ██╔══██╗██╔══██╗██╔════╝
       ███████║███████║█████╗  
       ██╔══██║██╔══██║██╔══╝  
    ██║  ██║██║  ██║██║     
    ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     
       Autonomous Agent Framework
    """)
    # P.S. Лого выглядит криво, но в консоли каким-то образом выводится ровно... Черная магия
    
    panel = Panel(
        Text(banner_text, style="bold cyan", justify="center"),
        border_style="cyan",
        title="[bold white]AAF Initializer[/bold white]",
        subtitle="[dim]v1.2.3[/dim]",
    )
    console.print(panel)
    console.print()

def _typewriter(prefix: str, msg: str, base_speed: float = 0.01):
    """
    Печатает текст посимвольно, 
    при этом не ломая цвета и стили (Rich теги).
    """
    # Если вывод идет не в терминал (а например, в пайплайн), печатаем мгновенно
    if not console.is_terminal:
        console.print(f"{prefix} {msg}")
        return
        
    icon_text = Text.from_markup(f"{prefix} ")
    msg_text = Text.from_markup(msg)
    
    with Live(icon_text, refresh_per_second=120, transient=False) as live:
        for i in range(1, len(msg_text) + 1):
            live.update(icon_text + msg_text[:i])
            time.sleep(base_speed + random.uniform(0.0, 0.005))

def info(msg: str):
    # Начало блока проверки, печатается без отступа после
    _typewriter("[bold cyan]ℹ[/bold cyan]", msg, base_speed=0.005)

def success(msg: str):
    # Конец блока проверки, делаем отступ
    _typewriter("[bold green]✔[/bold green]", msg, base_speed=0.005)
    console.print()

def warning(msg: str):
    # Ворнинги - тоже конец блока
    _typewriter("[bold yellow]⚠[/bold yellow]", msg, base_speed=0.01)
    console.print()

def error(msg: str):
    # Ошибки выводим чуть медленнее, для драматизма
    _typewriter("[bold red]✖[/bold red]", msg, base_speed=0.02)
    console.print()

def fatal(msg: str):
    """Выводит критическую ошибку и убивает скрипт."""
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