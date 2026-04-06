import logging
import os

# ANSI-коды цветов для консоли
class LogColors:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

    # Яркие (Bright) версии цветов для лучшего контраста
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

class ColorFormatter(logging.Formatter):
    """Кастомный форматтер для раскраски логов в консоли"""

    PREFIX_COLORS = {
        # Оркестратор
        "[BrainEngine]": LogColors.BRIGHT_CYAN,
        "[Brain]": LogColors.BRIGHT_CYAN,
        "[WatchDog]": LogColors.BRIGHT_RED,
        "[System]": LogColors.BRIGHT_WHITE,
        "[APIKeyManager]": LogColors.BRIGHT_GREEN,
        "[GlobalState]": LogColors.WHITE,
        "[Workspace]": LogColors.GRAY,
        # Циклы мышления (разводим по светофору)
        "[Event-Driven ReAct]": LogColors.BRIGHT_GREEN,
        "[Proactivity ReAct]": LogColors.BRIGHT_BLUE,
        "[Thoughts ReAct]": LogColors.BRIGHT_YELLOW,
        # Инструменты и действия
        "[Agent Action]": LogColors.BRIGHT_MAGENTA,
        "[Agent Action Result]": LogColors.GRAY,
        # Память и RAG
        "[MemoryManager]": LogColors.MAGENTA,
        "[Vector DB]": LogColors.GRAY,
        "[SQL DB]": LogColors.BLUE,
        "[Graph DB]": LogColors.MAGENTA,
        "[Graph-RAG]": LogColors.BRIGHT_MAGENTA,
        "[MentalState]": LogColors.BLUE,
        "[Consolidation]": LogColors.BRIGHT_MAGENTA,
        "[Fractal Memory]": LogColors.MAGENTA,
        # Сенсоры и внешние модули
        "[Telegram Telethon]": LogColors.BRIGHT_BLUE,
        "[Telegram Tools]": LogColors.CYAN,
        "[Web Search]": LogColors.YELLOW,
        "[Web Reader]": LogColors.YELLOW,
        "[Vosk]": LogColors.CYAN,
        "[TTS]": LogColors.CYAN,
        "[Vision]": LogColors.CYAN,
        "[Audio]": LogColors.CYAN,
        "[Terminal Input]": LogColors.GREEN,
        "[System Map]": LogColors.GREEN,
        # Sandbox и Swarm
        "[Sandbox]": LogColors.BRIGHT_YELLOW,
        "[Sandbox Listener]": LogColors.YELLOW,
    }

    def format(self, record):
        log_message = super().format(record)

        if record.levelno >= logging.ERROR:
            return f"{LogColors.BRIGHT_RED}{log_message}{LogColors.RESET}"
        if record.levelno == logging.WARNING:
            return f"{LogColors.BRIGHT_YELLOW}{log_message}{LogColors.RESET}"

        for prefix, color in self.PREFIX_COLORS.items():
            if prefix in record.getMessage():
                return f"{color}{log_message}{LogColors.RESET}"

        return log_message


def setup_specific_logger(name, log_file, level):
    log_dir = os.path.join("logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    full_path = os.path.join(log_dir, log_file)

    file_format = "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Файловый логгер (без цветов!)
    file_handler = logging.FileHandler(full_path, encoding="utf-8", mode="a")
    file_formatter = logging.Formatter(fmt=file_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)

    # Консольный логгер (с цветами)
    console_handler = logging.StreamHandler()
    color_formatter = ColorFormatter(fmt=file_format, datefmt=date_format)
    console_handler.setFormatter(color_formatter)

    specific_logger = logging.getLogger(name)
    specific_logger.setLevel(level)

    # Защита от дублирования логов при перезагрузках
    if not specific_logger.handlers:
        specific_logger.addHandler(file_handler)
        specific_logger.addHandler(console_handler)
    
    specific_logger.propagate = False
    return specific_logger

# Создаем логгер с уровнем INFO по умолчанию
system_logger = setup_specific_logger(name="SYSTEM", log_file="system.log", level=logging.INFO)

def update_log_level(level_str: str):
    """Динамически обновляет уровень логирования (вызывается после загрузки конфига)"""
    numeric_level = getattr(logging, level_str.upper(), logging.INFO)
    system_logger.setLevel(numeric_level)
    for handler in system_logger.handlers:
        handler.setLevel(numeric_level)