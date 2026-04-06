import os
import shutil
import asyncio
from pathlib import Path

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.vfs.client import VFSClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class FilesArchive(BaseInstrument):
    """
    Создание и распаковка архивов.
    Полезно при скачивании репозиториев, датасетов или подготовке файлов к отправке.
    """

    def __init__(self, client: VFSClient):
        self.vfs_client = client

    # ==========================================
    # РАСПАКОВКА АРХИВА
    # ==========================================

    def _sync_unpack_archive(self, archive_path: str, extract_to_dir: str = "") -> ToolResult:
        """
        Синхронная логика распаковки архива.
        """
        abs_archive = self.vfs_client.get_secure_path(archive_path)

        # Если папка для распаковки не указана, создаем папку с именем архива (без расширения)
        if not extract_to_dir:
            extract_to_dir = abs_archive.stem if abs_archive else "unpacked"

        abs_extract_to = self.vfs_client.get_secure_path(extract_to_dir)

        if not abs_archive or not abs_extract_to:
            return ToolResult.fail(msg="Ошибка безопасности: Путь выходит за пределы песочницы.")

        if not abs_archive.exists() or not abs_archive.is_file():
            return ToolResult.fail(msg=f"Ошибка: Архив '{archive_path}' не найден.")

        try:
            # Создаем целевую директорию, если её нет
            abs_extract_to.mkdir(parents=True, exist_ok=True)

            # Распаковываем. shutil сам определяет формат по расширению (.zip, .tar, .tar.gz, .gztar)
            shutil.unpack_archive(filename=str(abs_archive), extract_dir=str(abs_extract_to))

            # Считаем количество распакованных файлов для красивого отчета
            extracted_count = sum([len(files) for r, d, files in os.walk(abs_extract_to)])

            system_logger.info(f"[VFS] Архив '{archive_path}' распакован в '{extract_to_dir}'.")
            return ToolResult.ok(
                msg=f"Успех. Архив '{archive_path}' распакован.\nЦелевая папка: '{extract_to_dir}/'\nИзвлечено файлов: ~{extracted_count} шт.",
                data={
                    "extract_to_dir": extract_to_dir,
                    "extracted_count": extracted_count,
                },
            )

        except shutil.ReadError:
            return ToolResult.fail(
                msg=f"Ошибка: Файл '{archive_path}' не является поддерживаемым архивом или он поврежден."
            )

        except Exception as e:
            system_logger.error(f"[VFS] Ошибка распаковки {archive_path}: {e}")
            return ToolResult.fail(msg=f"Ошибка при распаковке: {e}", error=str(e))

    # ==========================================
    # СОЗДАНИЕ АРХИВА
    # ==========================================

    def _sync_create_archive(
        self, source_path: str, archive_name: str, format: str = "zip"
    ) -> ToolResult:
        """
        Синхронная логика создания архива.
        """
        abs_source = self.vfs_client.get_secure_path(source_path)

        # shutil.make_archive сам добавит расширение .zip или .tar, поэтому мы убираем его из имени, если агент передал
        if archive_name.endswith(f".{format}"):
            archive_name = archive_name[: -(len(format) + 1)]

        abs_archive_base = self.vfs_client.get_secure_path(archive_name)

        if not abs_source or not abs_archive_base:
            return ToolResult.fail(msg="Ошибка безопасности: Путь выходит за пределы песочницы.")

        if not abs_source.exists():
            return ToolResult.fail(msg=f"Ошибка: Источник '{source_path}' не найден.")

        if format not in ["zip", "tar", "gztar"]:
            return ToolResult.fail(
                msg=f"Ошибка: Формат '{format}' не поддерживается. Доступные: zip, tar, gztar."
            )

        try:
            # Создаем родительские папки для архива, если их нет
            abs_archive_base.parent.mkdir(parents=True, exist_ok=True)

            # Создаем архив
            created_file = shutil.make_archive(
                base_name=str(abs_archive_base),
                format=format,
                root_dir=(str(abs_source.parent) if abs_source.is_file() else str(abs_source)),
                base_dir=abs_source.name if abs_source.is_file() else ".",
            )

            # Получаем относительный путь созданного файла для вывода
            rel_created_file = (
                Path(created_file).relative_to(self.vfs_client.sandbox_path).as_posix()
            )

            # Считаем размер
            size_mb = Path(created_file).stat().st_size / (1024 * 1024)

            system_logger.info(
                f"[VFS] Создан архив '{rel_created_file}' (Размер: {size_mb:.2f} MB)."
            )
            return ToolResult.ok(
                msg=f"Успех. Архив создан.\nПуть: '{rel_created_file}'\nРазмер: {size_mb:.2f} MB.",
                data={"archive_path": rel_created_file, "size_mb": size_mb},
            )

        except Exception as e:
            system_logger.error(f"[VFS] Ошибка создания архива {archive_name}: {e}")
            return ToolResult.fail(msg=f"Ошибка при создании архива: {e}", error=str(e))

    # ==========================================
    # АСИНХРОННЫЕ ФАСАДЫ
    # ==========================================

    @skill()
    async def unpack_archive(self, archive_path: str, extract_to_dir: str = "") -> ToolResult:
        """
        Распаковывает ZIP или TAR архив.
        :param archive_path: Путь к архиву (например, 'downloads/repo.zip').
        :param extract_to_dir: Папка назначения. Если оставить пустым, создаст папку с именем архива.
        """
        return await asyncio.to_thread(self._sync_unpack_archive, archive_path, extract_to_dir)

    @skill()
    async def create_archive(
        self, source_path: str, archive_name: str, format: str = "zip"
    ) -> ToolResult:
        """
        Упаковывает директорию или файл в архив.
        :param source_path: Путь к файлу или папке, которые нужно сжать.
        :param archive_name: Имя будущего архива (например, 'results/data_backup').
        :param format: Формат: 'zip', 'tar' или 'gztar' (по умолчанию 'zip').
        """
        return await asyncio.to_thread(self._sync_create_archive, source_path, archive_name, format)
