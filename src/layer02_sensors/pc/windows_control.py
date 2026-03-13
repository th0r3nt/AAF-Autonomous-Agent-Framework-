import platform
from src.layer00_utils.logger import system_logger

if platform.system() == "Windows":
    try:
        from win11toast import toast
    except ImportError:
        toast = None
        system_logger.warning("[PC Control] Библиотека win11toast не установлена. Уведомления работать не будут.")
else:
    toast = None

def show_windows_notification(title: str, text: str, duration: int = 5) -> str:
    """Отображает нативную плашку уведомления Windows 10/11"""
    if platform.system() != "Windows":
        return "Ошибка: Уведомления поддерживаются только в ОС Windows."
        
    if not toast:
        return "Ошибка: Модуль уведомлений не инициализирован (отсутствует win11toast)."

    try:
        # win11toast работает асинхронно/в фоне по умолчанию, если не просить его ждать клика
        toast(title, text, duration="short")
        
        system_logger.info(f"[PC Control] Отправлено уведомление Windows: '{title}'")
        return "Уведомление успешно отправлено на экран."
        
    except Exception as e:
        system_logger.error(f"[PC Control] Ошибка при отправке уведомления: {e}")
        return f"Ошибка при отправке уведомления: {e}"