import asyncio 
from collections import deque
import os
from pathlib import Path
from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger

def change_proactivity_interval(seconds: int) -> str:
    """Изменяет частоту вызова проактивного цикла агента"""
    from src.layer03_brain.agent.engine.engine import brain_engine
    try:
        # Учитываем min_cooldown, чтобы агент случайно не поставил интервал меньше жесткого лимита
        if seconds < brain_engine.min_cooldown:
            return f"Ошибка: Интервал не может быть меньше минимального кулдауна ({brain_engine.min_cooldown} сек) во избежание перерасхода бюджета."
        
        old_interval = brain_engine.proactivity_interval
        brain_engine.proactivity_interval = seconds
        
        # Корректируем цель с учетом нового интервала
        brain_engine.target_proactive_time = brain_engine.last_proactive_time + seconds
        
        system_logger.info(f"[Proactivity ReAct] Интервал проактивности успешно изменен с {old_interval} сек. на {seconds} сек.")
        return f"[Proactivity ReAct] Интервал проактивности успешно изменен с {old_interval} сек. на {seconds} сек."
    except Exception as e:
        return f"Ошибка при изменении интервала: {e}"
    
def change_thoughts_interval(seconds: int) -> str:
    """Изменяет частоту вызова цикла интроспекции (мыслей) агента"""
    from src.layer03_brain.agent.engine.engine import brain_engine # Локальный импорт во избежание цикличности
    try:
        if seconds < 10:
            return "Ошибка: Интервал не может быть меньше 10 секунд (во избежание перегрузки БД)."
        
        old_interval = brain_engine.thoughts_interval
        brain_engine.thoughts_interval = seconds
        
        system_logger.info(f"[Thoughts ReAct] Интервал интроспекции успешно изменен с {old_interval} сек. на {seconds} сек.")
        return f"[Thoughts ReAct] Интервал интроспекции успешно изменен с {old_interval} сек. на {seconds} сек."
    except Exception as e:
        return f"[Thoughts ReAct] Ошибка при изменении интервала интроспекции: {e}"

async def read_recent_logs(lines: int = 50) -> str:
    """Обертка: читает последние N строк из системного лога"""
    from pathlib import Path
    current_dir = Path(__file__).resolve()
    # Надежно ищем папку src/ вверх по дереву
    src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
    
    if not src_dir:
        return "Ошибка: Не удалось найти директорию src."
        
    log_path = src_dir / "logs" / "system.log" 
    
    def _read_tail():
        if not os.path.exists(log_path):
            return f"Файл логов не найден по пути: {log_path}"
        
        with open(log_path, 'r', encoding='utf-8') as f:
            tail = deque(f, maxlen=lines)
        
        if not tail:
            return "Файл логов пуст."
            
        return "".join(tail)
        
    try:
        result = await asyncio.to_thread(_read_tail)
        return f"Последние {lines} строк из логов системы:\n\n{result}"
    except Exception as e:
        return f"Ошибка при чтении логов: {e}"
    
async def shutdown_system() -> str:
    """Корректно завершает работу агента (Docker-контейнера)"""
    import os
    import signal
    from src.layer01_datastate.event_bus.event_bus import event_bus
    from src.layer01_datastate.event_bus.events import Events
    
    system_logger.warning("[System] Агент инициировал завершение работы системы.")
    
    # 1. Публикуем событие для корректного закрытия баз и смены статуса ТГ на offline
    await event_bus.publish(Events.STOP_SYSTEM)
    
    # 2. Даем системе секунду на обработку ивента
    await asyncio.sleep(5)
    
    # 3. Отправляем SIGTERM для завершения процесса
    os.kill(os.getpid(), signal.SIGTERM)
    return "Сигнал на завершение работы отправлен. Базы сохранены, система отключается..."

async def change_llm_model(new_model: str) -> str:
    """Изменяет текущую LLM-модель в памяти и в конфиге"""
    if new_model not in config.llm.available_models:
        return f"Ошибка: Модель '{new_model}' не поддерживается. Доступные: {', '.join(config.llm.available_models)}"
    try:
        # 1. Изменяем в памяти, чтобы заработало прямо сейчас
        config.llm.model_name = new_model
        import src.layer03_brain.agent.engine.react as react_module
        react_module.LLM_MODEL = new_model
        
        # 2. Изменяем в файле settings.yaml, чтобы сохранить при рестарте
        current_dir = Path(__file__).resolve()
        yaml_path = current_dir.parents[4] / "config" / "settings.yaml"
        
        if not yaml_path.exists():
            return f"Модель изменена в памяти на '{new_model}', но файл settings.yaml не найден для сохранения."
            
        # Аккуратно читаем файл и заменяем только нужную строку, чтобы не убить комментарии
        def _update_yaml():
            with open(yaml_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            with open(yaml_path, 'w', encoding='utf-8') as f:
                for line in lines:
                    if line.strip().startswith("model_name:"):
                        # Сохраняем оригинальные отступы
                        indent = line[:len(line) - len(line.lstrip())]
                        f.write(f'{indent}model_name: "{new_model}"\n')
                    else:
                        f.write(line)
                        
        await asyncio.to_thread(_update_yaml)
        
        system_logger.warning(f"[System] LLM-модель успешно изменена на: {new_model}")
        return f"Системная архитектура обновлена. Новая модель '{new_model}' активирована и сохранена в конфигурации."
        
    except Exception as e:
        return f"Ошибка при смене модели: {e}"



SYSTEM_REGISTRY = {
    "change_proactivity_interval": change_proactivity_interval,
    "change_thoughts_interval": change_thoughts_interval,
    "read_recent_logs": read_recent_logs,
    "shutdown_system": shutdown_system,
    "change_llm_model": change_llm_model,
}