import logging
import os
from config.config_manager import config

LOGGING_LEVEL_STR = config.system.logging_level.upper()
LOGGING_LEVEL = getattr(logging, LOGGING_LEVEL_STR, logging.INFO)

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
        # Ядро и оркестратор
        "[BrainEngine]": LogColors.BRIGHT_CYAN,
        "[WatchDog]": LogColors.BRIGHT_RED,
        "[System]": LogColors.BRIGHT_WHITE,
        
        # Циклы мышления (разводим по светофору: События - Зеленый, Проактивность - Синий, Мысли - Желтый)
        "[Event-Driven ReAct]": LogColors.BRIGHT_GREEN,
        "[Proactivity ReAct]": LogColors.BRIGHT_BLUE,
        "[Thoughts ReAct]": LogColors.BRIGHT_YELLOW,
        
        # Инструменты и действия
        "[Agent Action]": LogColors.BRIGHT_MAGENTA,
        "[Agent Action Result]": LogColors.GRAY, # Серый, чтобы не отвлекал внимание от самих действий
        
        # Память
        "[MemoryManager]": LogColors.MAGENTA,
        "[Vector DB]": LogColors.GRAY,
        "[SQL DB]": LogColors.BLUE,
        "[Graph DB]": LogColors.BRIGHT_MAGENTA,
        
        # Сенсоры и модули
        "[Web Search]": LogColors.YELLOW,
        "[Web Reader]": LogColors.YELLOW,
        "[Vosk]": LogColors.CYAN,
        "[TTS]": LogColors.CYAN,
        "[Terminal Input]": LogColors.GREEN,
        "[System Map]": LogColors.GREEN,
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

def setup_specific_logger(name, log_file, level=LOGGING_LEVEL):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    full_path = os.path.join(log_dir, log_file)
    
    # Базовый формат (без цветов, для файла)
    file_format = "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 1. Хендлер для ФАЙЛА (Пишет чистый текст без крякозябр ANSI)
    file_handler = logging.FileHandler(full_path, encoding="utf-8", mode="a")
    file_formatter = logging.Formatter(fmt=file_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)

    # 2. Хендлер для КОНСОЛИ (Пишет цветной текст)
    console_handler = logging.StreamHandler()
    color_formatter = ColorFormatter(fmt=file_format, datefmt=date_format)
    console_handler.setFormatter(color_formatter)

    # Создаем логгер
    specific_logger = logging.getLogger(name)
    specific_logger.setLevel(level)
    
    specific_logger.addHandler(file_handler)
    specific_logger.addHandler(console_handler)
    specific_logger.propagate = False
    
    return specific_logger

system_logger = setup_specific_logger("SYSTEM", "system.log")