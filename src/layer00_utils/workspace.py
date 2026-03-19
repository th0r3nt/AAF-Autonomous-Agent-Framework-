import time
from pathlib import Path
from datetime import datetime
from src.layer00_utils.logger import system_logger
from src.layer00_utils.env_manager import AGENT_NAME

class WorkspaceManager:
    def __init__(self):
        current_dir = Path(__file__).resolve()
        src_dir_path = next((p for p in current_dir.parents if p.name == "src"), None)
        
        if src_dir_path:
            self.project_root = src_dir_path.parent
            self.src_dir = src_dir_path
        else:
            self.project_root = current_dir.parent.parent.parent
            self.src_dir = self.project_root / "src"

        # Динамический путь до изолированного рабочего пространства отдельного агента
        self.workspace_dir = self.project_root / "Agents" / AGENT_NAME / "workspace"
        self.temp_dir = self.workspace_dir / "temp"
        self.sandbox_dir = self.workspace_dir / "sandbox"

    def init_workspace(self) -> None:
        """Создает необходимые папки при старте системы"""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        system_logger.info(f"[Workspace] Инициализирован для '{AGENT_NAME}'. VFS зоны: sandbox/, src/")

    def resolve_vfs_path(self, vfs_path: str, mode: str = 'read') -> Path:
        """
        Преобразует виртуальный путь агента в абсолютный путь системы.
        READ: Разрешено читать любой файл в контейнере.
        WRITE/DELETE: Строго заперты внутри песочницы (sandbox/).
        .env: Заблокирован глобально и аппаратно.
        """
        if not vfs_path:
            raise PermissionError("Путь не может быть пустым.")
            
        clean_path = vfs_path.replace("\\", "/").strip("/")
        
        # Защита от дурака (нейросети): Если агент прислал абсолютный путь из логов
        # Вырезаем всё до слова sandbox или src
        if "/workspace/sandbox/" in clean_path:
            clean_path = "sandbox/" + clean_path.split("/workspace/sandbox/")[-1]
        elif "/src/" in clean_path:
            clean_path = "src/" + clean_path.split("/src/")[-1]
        elif clean_path.startswith("file:///"):
            clean_path = clean_path.replace("file:///", "")
        
        # Защита от .env
        if ".env" in clean_path.split("/") or clean_path.endswith(".env"):
            raise PermissionError("Security: Доступ к файлам окружения (.env) строго запрещен.")

        # Умный маппинг псевдонимов (чтобы агенту не нужно было писать Agents/VEGA/workspace/...)
        if clean_path == "sandbox" or clean_path.startswith("sandbox/"):
            rel_part = clean_path[len("sandbox"):].strip("/")
            target_path = (self.sandbox_dir / rel_part).resolve()

        elif clean_path == "temp" or clean_path.startswith("temp/"):
            rel_part = clean_path[len("temp"):].strip("/")
            target_path = (self.temp_dir / rel_part).resolve()
            
        elif clean_path == "src" or clean_path.startswith("src/"):
            rel_part = clean_path[len("src"):].strip("/")
            target_path = (self.src_dir / rel_part).resolve()
            
        else:
            # Любые другие пути (абсолютные или от корня проекта)
            target_path = Path(clean_path)
            if not target_path.is_absolute():
                target_path = (self.project_root / target_path).resolve()
            else:
                target_path = target_path.resolve()

        # 3. Повторная защита от .env (отлавливает хитрые пути)
        if target_path.name == ".env" or target_path.suffix == ".env":
            raise PermissionError("Security: Физический доступ к файлам .env заблокирован.")

        # 4. Тюрьма для Write/Delete
        if mode in ['write', 'delete']:
            if target_path.name == "agent_sdk.py":
                raise PermissionError("Security: Системный файл 'agent_sdk.py' аппаратно защищен.")
                
            is_in_sandbox = False
            is_in_temp = False
            
            try:
                target_path.relative_to(self.sandbox_dir.resolve())
                is_in_sandbox = True
            except ValueError: 
                pass
            
            try:
                target_path.relative_to(self.temp_dir.resolve())
                is_in_temp = True
            except ValueError: 
                pass
            
            if not (is_in_sandbox or is_in_temp):
                raise PermissionError(f"Security: Операция '{mode}' разрешена только внутри 'sandbox/' или 'temp/'.")
        return target_path

    def vfs_path_to_display(self, abs_path: Path) -> str:
        """Служебная функция: Преобразует абсолютный путь обратно в виртуальный (для логов)"""
        try:
            rel = abs_path.relative_to(self.sandbox_dir.resolve())
            return f"sandbox/{rel.as_posix()}"
        except ValueError:
            pass
        try:
            rel = abs_path.relative_to(self.src_dir.resolve())
            return f"src/{rel.as_posix()}"
        except ValueError:
            return abs_path.name

    def get_sandbox_file(self, filename: str) -> Path:
        """[DEPRECATED - Оставлено для обратной совместимости внутренних систем]"""
        return self.resolve_vfs_path(f"sandbox/{filename}", mode="write")

    def get_temp_file(self, prefix: str = "", extension: str = "") -> Path:
        """Генерирует безопасный абсолютный путь для нового временного файла"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        filename = f"{prefix}{timestamp}{extension}"
        return self.temp_dir / filename

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
        """Динамический блок контекста: Возвращает список файлов песочницы (рекурсивно)"""
        if not self.sandbox_dir.exists():
            return "Песочница не инициализирована."
        
        files = []
        for p in self.sandbox_dir.rglob('*'):
            if p.is_file():
                # Получаем относительный путь от корня песочницы
                rel_path = p.relative_to(self.sandbox_dir).as_posix()
                # Игнорируем технические файлы
                if rel_path not in ['.gitkeep', 'sandbox_state.json', 'agent_sdk.py']:
                    files.append(f"sandbox/{rel_path}")
        
        if not files:
            return "В Sandbox пусто."
            
        return "\n".join([f"- {f}" for f in sorted(files)])

workspace_manager = WorkspaceManager()