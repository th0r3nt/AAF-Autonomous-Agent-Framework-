from pathlib import Path

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings


class VFSAccessController:
    """
    Контроллер доступа к файловой системе.
    Регулирует права агента в зависимости от madness_level.
    """

    def __init__(self, sandbox_path: Path, project_root: Path):
        self.sandbox_path = sandbox_path.resolve()
        self.project_root = project_root.resolve()

        self.madness_level = settings.interfaces.vfs.madness_level

        self.HARD_BLACKLIST = []

        # Динамически добавляем папки в зависимости от настроек безопасности
        if not settings.interfaces.vfs.env_access:
            self.HARD_BLACKLIST.extend([".env", "agent/data/telegram_sessions"])

        if not settings.interfaces.vfs.db_access:
            self.HARD_BLACKLIST.extend(
                ["agent/data/chroma_db", "agent/data/kuzu_db", "agent_ticks.db"]
            )

        # Системные папки, которые заблокированы всегда
        self.HARD_BLACKLIST.extend(
            [
                ".git",
            ]
        )

    def _is_blacklisted(self, target_path: Path) -> bool:
        """Проверяет, не попадает ли путь под жесткие ограничения."""
        for blacklisted_item in self.HARD_BLACKLIST:
            # Превращаем строку из блэклиста в Path относительно корня
            blacklisted_path = (self.project_root / blacklisted_item).resolve()
            if target_path.is_relative_to(blacklisted_path) or target_path == blacklisted_path:
                return True
        return False

    def resolve_path(self, virtual_path: str, mode: str = "read") -> Path | None:
        """
        Главный метод-шлюз. Принимает путь от агента и возвращает абсолютный путь Path,
        если действие разрешено, или None, если доступ закрыт.
        """
        clean_vpath = str(virtual_path).lstrip("/\\")

        # Определяем точку отсчета в зависимости от уровня безумия
        if self.madness_level == 0:
            # Уровень 0: агент вообще не знает, что есть мир за пределами sandbox/
            base_dir = self.sandbox_path
        else:
            # Уровни 1, 2, 3: агент может указывать пути от корня проекта (например, 'src/main.py')
            base_dir = self.project_root

        target_path = (base_dir / clean_vpath).resolve()

        # Защита от Path Traversal (выход за пределы разрешенной зоны через '../../')
        if not target_path.is_relative_to(base_dir):
            system_logger.warning(
                f"[VFS Security] Отклонена попытка выхода за пределы базы (Path Traversal): {virtual_path}"
            )
            return None

        # Проверка Hard Blacklist
        if self._is_blacklisted(target_path):
            system_logger.warning(
                f"[VFS Security] Отклонен доступ к запрещенной зоне: {target_path}"
            )
            return None

        # Логика прав (Read/Write)
        if mode == "write":
            if self.madness_level in [0, 1]:
                # Уровень 0 и 1: Писать можно ТОЛЬКО внутри sandbox/
                if not target_path.is_relative_to(self.sandbox_path):
                    system_logger.warning(
                        f"[VFS Security] Отказ в записи (Madness {self.madness_level}). Разрешено писать только в sandbox/: {target_path}"
                    )
                    return None
            elif self.madness_level >= 2:
                # Уровень 2 и 3: запись разрешена везде (кроме blacklist).
                pass

        elif mode == "read":
            if self.madness_level == 0:
                # Уровень 0: Читать ТОЛЬКО внутри sandbox/
                if not target_path.is_relative_to(self.sandbox_path):
                    return None
            # Уровни 1, 2, 3: Читать разрешено весь проект (кроме blacklist)
            pass

        return target_path
