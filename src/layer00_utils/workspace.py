import time
from pathlib import Path
from datetime import datetime
from src.layer00_utils.logger import system_logger

class WorkspaceManager:
    def __init__(self):
        # Ищем корень проекта отталкиваясь от текущего файла
        current_dir = Path(__file__).resolve()
        src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
        
        if src_dir:
            self.project_root = src_dir.parent
        else:
            self.project_root = current_dir.parent.parent.parent

        self.workspace_dir = self.project_root / "workspace"
        self.temp_dir = self.workspace_dir / "temp"
        self.sandbox_dir = self.workspace_dir / "sandbox"

    def init_workspace(self) -> None:
        """Создает необходимые папки при старте системы"""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        system_logger.info(f"[Workspace] Инициализирован. Путь: {self.workspace_dir}")

    def get_temp_file(self, prefix: str = "", extension: str = "") -> Path:
        """Генерирует безопасный абсолютный путь для нового временного файла"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        filename = f"{prefix}{timestamp}{extension}"
        return self.temp_dir / filename

    def get_sandbox_file(self, filename: str) -> Path:
        """
        Возвращает путь к файлу в песочнице. 
        Включает жесткую защиту от выхода за пределы папки (Path Traversal).
        """
        target_path = (self.sandbox_dir / filename).resolve()
        # Проверяем, что итоговый путь действительно находится внутри sandbox_dir
        if not str(target_path).startswith(str(self.sandbox_dir.resolve())):
            raise PermissionError(f"[Security] Попытка выхода за пределы sandbox: {filename}")
        return target_path

    def clean_temp_workspace(self) -> str:
        """Полностью очищает папку temp"""
        count = 0
        freed_space = 0
        for item in self.temp_dir.iterdir():
            if item.is_file():
                freed_space += item.stat().st_size
                item.unlink()
                count += 1
                
        mb_freed = freed_space / (1024 * 1024)
        msg = f"Удалено {count} файлов. Освобождено {mb_freed:.2f} МБ."
        system_logger.info(f"[Workspace] Ручная очистка temp: {msg}")
        return msg

    def cleanup_old_temp_files(self, max_age_hours: int = 48) -> None:
        """Фоновый сборщик мусора: удаляет файлы старше max_age_hours"""
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        count = 0

        for item in self.temp_dir.iterdir():
            if item.is_file():
                # Проверяем время последней модификации файла
                if now - item.stat().st_mtime > max_age_seconds:
                    try:
                        item.unlink()
                        count += 1
                    except Exception as e:
                        system_logger.error(f"[Workspace] Не удалось удалить старый файл {item.name}: {e}")
        
        if count > 0:
            system_logger.info(f"[Workspace] Автоочистка: удалено {count} старых файлов (>{max_age_hours}ч).")

    def get_workspace_telemetry(self) -> str:
        """Возвращает строку с размером и количеством файлов для телеметрии"""
        def get_dir_size_and_count(directory: Path):
            if not directory.exists():
                return 0, 0
            count = 0
            size = 0
            for item in directory.rglob('*'):
                if item.is_file():
                    count += 1
                    size += item.stat().st_size
            return count, size / (1024 * 1024)

        temp_count, temp_mb = get_dir_size_and_count(self.temp_dir)
        sandbox_count, sandbox_mb = get_dir_size_and_count(self.sandbox_dir)

        return f"Workspace: {temp_count} файлов ({temp_mb:.2f} МБ) в temp/, {sandbox_count} файлов ({sandbox_mb:.2f} МБ) в sandbox/"
    
    def get_sandbox_files_list(self) -> str:
        """Возвращает список файлов, находящихся в песочнице"""
        if not self.sandbox_dir.exists():
            return "Песочница не инициализирована."
        
        files = [f.name for f in self.sandbox_dir.iterdir() if f.is_file()]
        
        # Игнорируем технические файлы
        files = [f for f in files if f not in ['.gitkeep', 'sandbox_state.json', 'agent_sdk.py']]
        
        if not files:
            return "В песочнице сейчас пусто."
            
        return "\n".join([f"- {f}" for f in files])

workspace_manager = WorkspaceManager()