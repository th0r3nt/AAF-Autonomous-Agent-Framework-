import shutil
from pathlib import Path
from src.l00_utils.managers.logger import system_logger
from src.l02_state.system.agency import AgencyState


class ShadowBackupManager:
    """
    Машина времени для файловой системы.
    Создает теневые копии файлов перед их изменением агентом и управляет транзакциями (commit/rollback).
    """

    def __init__(self, project_root: Path, agency_state: AgencyState):
        self.project_root = project_root.resolve()
        self.agency_state = agency_state

        # Папка для теневых копий, она недоступна агенту и служит для хранения оригинальных версий файлов на время ReAct-цикла
        self.backup_dir = self.project_root / "agent" / "data" / "shadow_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _get_transaction_dir(self, transaction_id: str) -> Path:
        """Возвращает путь к папке бэкапов конкретной транзакции (цикла)."""
        return self.backup_dir / f"tx_{transaction_id}"

    def create_backup(self, target_absolute_path: Path) -> bool:
        """Копирует оригинальный файл в папку бэкапов текущего цикла перед тем, как агент его перезапишет."""
        transaction_id = self.agency_state.current_transaction_id.get()
        if not transaction_id or transaction_id == "none":
            system_logger.warning(
                f"[Shadow Backup] Попытка изменения файла {target_absolute_path.name} вне контекста транзакции. Бэкап не создан."
            )
            return False

        if not target_absolute_path.exists() or not target_absolute_path.is_file():
            return False

        tx_dir = self._get_transaction_dir(transaction_id)

        try:
            rel_path = target_absolute_path.relative_to(self.project_root)
        except ValueError:
            rel_path = Path(target_absolute_path.name)

        backup_path = tx_dir / rel_path

        if not backup_path.exists():
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target_absolute_path, backup_path)
            system_logger.debug(
                f"[Shadow Backup] Создан бэкап: {rel_path} (TX: {transaction_id})"
            )

        return True

    def commit_transaction(self, transaction_id: str):
        """Удаляет папку с бэкапами (Транзакция успешна)."""
        tx_dir = self._get_transaction_dir(transaction_id)
        if tx_dir.exists():
            try:
                shutil.rmtree(tx_dir)
                system_logger.debug(
                    f"[Shadow Backup] Транзакция {transaction_id} успешна, бэкапы удалены."
                )
            except Exception as e:
                system_logger.error(f"[Shadow Backup] Ошибка очистки бэкапов: {e}")

    def rollback_transaction(self, transaction_id: str):
        """Аварийный откат файлов."""
        tx_dir = self._get_transaction_dir(transaction_id)
        if not tx_dir.exists():
            return

        system_logger.warning(f"[Shadow Backup] Аварийный откат транзакции {transaction_id}.")

        try:
            # Ищем все файлы в папке бэкапа рекурсивно
            for backup_file in tx_dir.rglob("*"):
                if backup_file.is_file():
                    # Вычисляем оригинальный путь
                    rel_path = backup_file.relative_to(tx_dir)
                    original_path = self.project_root / rel_path

                    # Восстанавливаем файл (с перезаписью)
                    original_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, original_path)
                    system_logger.info(f"[Shadow Backup] Восстановлен файл: {rel_path}")

            # После успешного отката удаляем следы
            shutil.rmtree(tx_dir)
            system_logger.info(
                f"[Shadow Backup] Откат транзакции {transaction_id} успешно завершен. Система в безопасности."
            )

        except Exception as e:
            system_logger.error(
                f"[Shadow Backup] Критическая ошибка отката транзакции {transaction_id}: {e}"
            )
