import hashlib
import asyncio

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.vfs.client import VFSClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class FilesCrypto(BaseInstrument):
    """
    Вычисление криптографических хэшей файлов (MD5, SHA256 и др.).
    Позволяет агенту проверять целостность файлов, искать дубликаты и отслеживать изменения.
    """

    def __init__(self, client: VFSClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.vfs_client = client

    def _sync_calculate_hash(self, filepath: str, algorithm: str = "sha256") -> ToolResult:
        """
        Синхронная логика вычисления хэша файла.
        """
        abs_path = self.vfs_client.get_secure_path(filepath)

        if not abs_path:
            return ToolResult.fail(
                msg=f"Ошибка безопасности: Путь '{filepath}' выходит за пределы песочницы.",
                error="Access Denied",
            )

        if not abs_path.exists():
            return ToolResult.fail(
                msg=f"Ошибка: Файл '{filepath}' не найден.", error="FileNotFoundError"
            )
        if not abs_path.is_file():
            return ToolResult.fail(
                msg=f"Ошибка: '{filepath}' является директорией. Хэш можно вычислить только для файла.",
                error="IsADirectoryError",
            )

        algo = algorithm.lower().strip()
        # Проверяем, поддерживает ли система запрошенный алгоритм (Обычно это md5, sha1, sha256, sha512)
        if algo not in hashlib.algorithms_guaranteed:
            available = ", ".join(hashlib.algorithms_guaranteed)
            return ToolResult.fail(
                msg=f"Ошибка: Алгоритм '{algorithm}' не поддерживается. Доступные варианты: {available}",
                error="UnsupportedAlgorithm",
            )

        try:
            hasher = hashlib.new(algo)

            # Читаем файл кусками (чанками по 64 КБ).
            # Это критически важно, чтобы не загружать весь файл в RAM (вдруг агент решит чекнуть ISO-образ на 4 ГБ).
            with open(abs_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)

            digest = hasher.hexdigest()
            size_mb = abs_path.stat().st_size / (1024 * 1024)

            system_logger.debug(f"[VFS Crypto] Вычислен {algo.upper()} для {filepath}: {digest}")

            msg = (
                f"Файл: '{filepath}' (Размер: {size_mb:.2f} MB)\n"
                f"Алгоритм: {algo.upper()}\n"
                f"Хэш: {digest}"
            )
            return ToolResult.ok(
                msg=msg,
                data={
                    "filepath": filepath,
                    "hash": digest,
                    "algorithm": algo,
                    "size_mb": size_mb,
                },
            )

        except PermissionError:
            return ToolResult.fail(
                msg=f"Ошибка: Нет прав на чтение файла '{filepath}'.",
                error="PermissionError",
            )

        except Exception as e:
            system_logger.error(f"[VFS Crypto] Ошибка вычисления хэша для {filepath}: {e}")
            return ToolResult.fail(msg=f"Ошибка при вычислении хэша: {e}", error=str(e))

    # ==========================================
    # АСИНХРОННЫЙ ФАСАД
    # ==========================================

    @skill()
    async def calculate_hash(self, filepath: str, algorithm: str = "sha256") -> ToolResult:
        """
        Вычисляет хэш-сумму файла по заданному алгоритму.
        :param filepath: Относительный путь к файлу в песочнице (например, 'data/model.bin').
        :param algorithm: Алгоритм хэширования ('md5', 'sha1', 'sha256', 'sha512'). По умолчанию 'sha256'.
        """
        return await asyncio.to_thread(self._sync_calculate_hash, filepath, algorithm)
