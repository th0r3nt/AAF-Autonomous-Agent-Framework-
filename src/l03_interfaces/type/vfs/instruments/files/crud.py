import os
import shutil
import asyncio

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.l03_interfaces.type.vfs.client import VFSClient

from src.l03_interfaces.type.vfs.security.access import VFSAccessController
from src.l03_interfaces.type.vfs.security.ast import ASTValidator
from src.l03_interfaces.type.vfs.security.backup import ShadowBackupManager
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class FilesCRUD(BaseInstrument):
    """
    Продвинутые операции с файловой системой.
    Оснащены AST-валидацией Python кода и теневыми бэкапами (SWK Mode).
    """

    def __init__(
        self,
        client: "VFSClient",
        access_controller: VFSAccessController,
        backup_manager: ShadowBackupManager,
    ):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.client = client
        self.project_root = self.client.sandbox_path.parent.parent
        self.access_controller = access_controller
        self.backup_manager = backup_manager

    # ==========================================
    # ЧТЕНИЕ И ЗАПИСЬ
    # ==========================================

    def _sync_read_file(self, filepath: str) -> ToolResult:
        """
        Синхронная логика чтения файла.
        """
        abs_path = self.access_controller.resolve_path(filepath, mode="read")

        if not abs_path:
            return ToolResult.fail(
                msg=f"Ошибка безопасности: при текущем уровне доступа к VFS чтение файла '{filepath}' запрещено.",
                error="Access Denied",
            )

        if not abs_path.exists():
            return ToolResult.fail(
                msg=f"Ошибка: Файл '{filepath}' не существует.",
                error="FileNotFoundError",
            )
        if not abs_path.is_file():
            return ToolResult.fail(
                msg=f"Ошибка: '{filepath}' является директорией, а не файлом.",
                error="IsADirectoryError",
            )

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            max_chars = 50000
            if len(content) > max_chars:
                return ToolResult.ok(
                    msg=f"--- Файл: {filepath} ---\n{content[:max_chars]}\n\n...[ФАЙЛ СЛИШКОМ БОЛЬШОЙ И БЫЛ ОБРЕЗАН. ПОКАЗАНЫ ПЕРВЫЕ {max_chars} СИМВОЛОВ]...",
                    data=content,
                )

            return ToolResult.ok(msg=f"--- Файл: {filepath} ---\n{content}", data=content)

        except UnicodeDecodeError:
            return ToolResult.fail(
                msg=f"Ошибка: Файл '{filepath}' является бинарным и не может быть прочитан как текст.",
                error="UnicodeDecodeError",
            )

        except Exception as e:
            system_logger.error(f"[VFS] Ошибка чтения файла {filepath}: {e}")
            return ToolResult.fail(msg=f"Ошибка при чтении файла: {e}", error=str(e))

    def _sync_write_file(
        self, filepath: str, content: str, append: bool = False
    ) -> ToolResult:
        """
        Синхронная логика записи (создает или перезаписывает).
        """
        abs_path = self.access_controller.resolve_path(filepath, mode="write")

        if not abs_path:
            allowed_dir = "'agent/sandbox/'" if settings.interfaces.vfs.madness_level in [0, 1] else "разрешенные директории"
            return ToolResult.fail(
                msg=f"Ошибка безопасности (Madness Level {settings.interfaces.vfs.madness_level}): Запись разрешена только в {allowed_dir}. Запись в '{filepath}' запрещена.",
                error="Access Denied",
            )

        if abs_path.exists() and not abs_path.is_file():
            return ToolResult.fail(
                msg=f"Ошибка: По пути '{filepath}' уже существует директория.",
                error="IsADirectoryError",
            )

        # 1. AST-ВАЛИДАЦИЯ (Если это Python-файл)
        if abs_path.suffix == ".py":
            # Если это режим append (добавление), нам нужно проверять ВЕСЬ файл целиком
            if append and abs_path.exists():
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        full_content = f.read() + "\n" + content
                except Exception:
                    full_content = content
            else:
                full_content = content

            # Проверяем синтаксис
            is_valid, error_msg = ASTValidator.validate_python_syntax(full_content)
            if not is_valid:
                return ToolResult.fail(msg=error_msg, error="AST Syntax Error")

            # Проверка на системные деструктивные вызовы (Только для God Mode)
            if settings.interfaces.vfs.madness_level == 3:
                is_safe, sec_msg = ASTValidator.censor_system_calls(full_content)
                if not is_safe:
                    return ToolResult.fail(msg=sec_msg, error="AST Security Violation")

        # 2. ТЕНЕВЫЕ БЭКАПЫ (Если Агент лезет в системные файлы фреймворка)
        if not abs_path.is_relative_to(self.client.sandbox_path):
            # Сохраняем оригинал перед перезаписью!
            self.backup_manager.create_backup(abs_path)

        # 3. ФИЗИЧЕСКАЯ ЗАПИСЬ
        try:
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            with open(abs_path, mode, encoding="utf-8") as f:
                f.write(content)

            action = "дополнен" if append else "создан/перезаписан"
            system_logger.debug(f"[VFS] Файл {filepath} успешно {action}.")
            return ToolResult.ok(
                msg=f"Файл '{filepath}' успешно {action}.",
                data={"filepath": filepath, "append": append},
            )

        except Exception as e:
            system_logger.error(f"[VFS] Ошибка записи в {filepath}: {e}")
            return ToolResult.fail(msg=f"Ошибка при записи файла: {e}", error=str(e))

    def _sync_delete_file(self, filepath: str) -> ToolResult:
        """
        Удаляет файл с поддержкой бэкапов системных файлов.
        """
        abs_path = self.access_controller.resolve_path(filepath, mode="write")
        if not abs_path:
            allowed_dir = "'agent/sandbox/'" if settings.interfaces.vfs.madness_level in [0, 1] else "разрешенные директории"
            return ToolResult.fail(
                msg=f"Ошибка безопасности (Madness Level {settings.interfaces.vfs.madness_level}): удаление разрешено только в {allowed_dir}. Удаление '{filepath}' запрещено.",
                error="Access Denied",
            )

        if not abs_path.exists():
            return ToolResult.fail(
                msg=f"Ошибка: Файл '{filepath}' не существует.",
                error="FileNotFoundError",
            )
        if not abs_path.is_file():
            return ToolResult.fail(
                msg=f"Ошибка: '{filepath}' является директорией.",
                error="IsADirectoryError",
            )

        # ТЕНЕВОЙ БЭКАП (Сохраняем перед удалением!)
        if not abs_path.is_relative_to(self.client.sandbox_path):
            self.backup_manager.create_backup(abs_path)

        try:
            abs_path.unlink()
            system_logger.debug(f"[VFS] Файл {filepath} удален.")
            return ToolResult.ok(
                msg=f"Файл '{filepath}' успешно удален.", data={"filepath": filepath}
            )

        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка при удалении файла: {e}", error=str(e))

    # ==========================================
    # УПРАВЛЕНИЕ ДИРЕКТОРИЯМИ
    # ==========================================

    def _sync_list_directory(self, dirpath: str) -> ToolResult:
        """
        Читает содержимое папки.
        """
        if not dirpath or dirpath == ".":
            # Точка отсчета меняется в зависимости от уровня безумия
            abs_path = (
                self.client.sandbox_path
                if settings.interfaces.vfs.madness_level == 0
                else self.project_root
            )
            display_path = (
                "sandbox/" if settings.interfaces.vfs.madness_level == 0 else "project_root/"
            )
        else:
            abs_path = self.access_controller.resolve_path(dirpath, mode="read")
            display_path = dirpath

        if not abs_path:
            return ToolResult.fail(
                msg="Ошибка безопасности: Доступ к директории запрещен.",
                error="Access Denied",
            )

        if not abs_path.exists() or not abs_path.is_dir():
            return ToolResult.fail(
                msg=f"Ошибка: Директория '{display_path}' не найдена.",
                error="NotADirectoryError",
            )

        try:
            items = os.listdir(abs_path)
            if not items:
                return ToolResult.ok(msg=f"Директория '{display_path}' пуста.", data=[])

            folders = []
            files = []

            for item in sorted(items):
                item_path = abs_path / item
                if item_path.is_dir():
                    folders.append(f"📁 {item}/")
                else:
                    files.append(f"📄 {item}")

            result_lines = [f"Содержимое директории '{display_path}':"] + folders + files
            return ToolResult.ok(
                msg="\n".join(result_lines), data={"folders": folders, "files": files}
            )

        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка при чтении директории: {e}", error=str(e))

    def _sync_manage_directory(self, dirpath: str, action: str) -> ToolResult:
        """
        Создает или удаляет папку.
        """
        abs_path = self.access_controller.resolve_path(dirpath, mode="write")
        if not abs_path:
            allowed_dir = "'agent/sandbox/'" if settings.interfaces.vfs.madness_level in [0, 1] else "разрешенные директории"
            return ToolResult.fail(
                msg=f"Ошибка безопасности (Madness Level {settings.interfaces.vfs.madness_level}): Операция '{action}' разрешена только в {allowed_dir}. Операция '{action}' над '{dirpath}' запрещена.",
                error="Access Denied",
            )

        try:
            if action == "create":
                if abs_path.exists():
                    return ToolResult.fail(
                        msg=f"Ошибка: '{dirpath}' уже существует.",
                        error="FileExistsError",
                    )
                abs_path.mkdir(parents=True, exist_ok=True)
                return ToolResult.ok(
                    msg=f"Директория '{dirpath}' успешно создана.",
                    data={"dirpath": dirpath},
                )

            elif action == "delete":
                if not abs_path.exists():
                    return ToolResult.fail(
                        msg=f"Ошибка: '{dirpath}' не существует.",
                        error="FileNotFoundError",
                    )
                if not abs_path.is_dir():
                    return ToolResult.fail(
                        msg=f"Ошибка: '{dirpath}' - это файл.",
                        error="NotADirectoryError",
                    )

                # Защита от удаления корней
                if abs_path == self.client.sandbox_path or abs_path == self.project_root:
                    return ToolResult.fail(
                        msg="CRITICAL SECURITY WARNING: Попытка удаления корневой директории заблокирована.",
                        error="Security Restriction",
                    )

                # Если удаляем системную папку — бэкапим ВСЕ файлы внутри (рекурсивно)
                if not abs_path.is_relative_to(self.client.sandbox_path):
                    for file in abs_path.rglob("*"):
                        if file.is_file():
                            self.backup_manager.create_backup(file)

                shutil.rmtree(abs_path)
                return ToolResult.ok(
                    msg=f"Директория '{dirpath}' и всё её содержимое успешно удалены.",
                    data={"dirpath": dirpath},
                )

            return ToolResult.fail(
                msg=f"Ошибка: Неизвестное действие '{action}'.", error="UnknownAction"
            )

        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка при {action} директории: {e}", error=str(e))

    # ==========================================
    # АСИНХРОННЫЕ ФАСАДЫ
    # ==========================================

    @skill()
    async def read_file(self, filepath: str) -> ToolResult:
        return await asyncio.to_thread(self._sync_read_file, filepath)

    @skill()
    async def write_file(self, filepath: str, content: str) -> ToolResult:
        return await asyncio.to_thread(self._sync_write_file, filepath, content, append=False)

    @skill()
    async def append_file(self, filepath: str, content: str) -> ToolResult:
        return await asyncio.to_thread(self._sync_write_file, filepath, content, append=True)

    @skill()
    async def delete_file(self, filepath: str) -> ToolResult:
        return await asyncio.to_thread(self._sync_delete_file, filepath)

    @skill()
    async def list_directory(self, dirpath: str = "") -> ToolResult:
        return await asyncio.to_thread(self._sync_list_directory, dirpath)

    @skill()
    async def create_directory(self, dirpath: str) -> ToolResult:
        return await asyncio.to_thread(self._sync_manage_directory, dirpath, "create")

    @skill()
    async def delete_directory(self, dirpath: str) -> ToolResult:
        return await asyncio.to_thread(self._sync_manage_directory, dirpath, "delete")
