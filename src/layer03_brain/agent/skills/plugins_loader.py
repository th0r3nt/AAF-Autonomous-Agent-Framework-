import importlib.util
import sys
from pathlib import Path

from src.layer00_utils.env_manager import AGENT_NAME
from src.layer00_utils.logger import system_logger

def load_custom_plugins():
    """Динамически загружает пользовательские плагины из папки агента"""
    current_dir = Path(__file__).resolve()
    src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
    project_root = src_dir.parent if src_dir else current_dir.parents[4]
    
    # Динамический путь: AAF/Agents/<NAME>/plugins
    plugins_dir = project_root / "Agents" / AGENT_NAME / "plugins"
    
    if not plugins_dir.exists():
        return
        
    # Ищем все Python-файлы, игнорируя системные (__init__.py)
    for py_file in plugins_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
            
        module_name = f"plugins.custom_plugin_{py_file.stem}"
        
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module 
                spec.loader.exec_module(module)
                system_logger.info(f"[Plugin Loader] Успешно загружен плагин: {py_file.name}")
            else:
                system_logger.error(f"[Plugin Loader] Не удалось создать loader для '{py_file.name}'")
            
        except Exception as e:
            # Перехватываем ошибки (например, SyntaxError), чтобы агент не упал при старте
            system_logger.error(f"[Plugin Loader] Ошибка загрузки плагина '{py_file.name}': {e}")