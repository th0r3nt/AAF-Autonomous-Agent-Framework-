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

    def _get_tick_dir(self, tick_id: int | str) -> Path:
        """
        Возвращает путь к папке бэкапов конкретного тика.
        """
        return self.backup_dir / f"tick_{tick_id}"

    def create_backup(self, target_absolute_path: Path) -> bool:
        """
        Копирует оригинальный файл в папку бэкапов текущего тика перед тем, как агент его перезапишет.
        """
        tick_id = self.agency_state.current_tick_id.get()
        if not tick_id:
            system_logger.warning(
                f"[Shadow Backup] Попытка изменения файла {target_absolute_path.name} вне контекста тика. Бэкап не создан."
            )
            return False

        # Бэкапим только если файл физически существует (агент его перезаписывает, а не создает с нуля)
        if not target_absolute_path.exists() or not target_absolute_path.is_file():
            return False

        tick_dir = self._get_tick_dir(tick_id)

        try:
            # Сохраняем структуру папок
            # Если меняем src/main.py, бэкап ляжет в shadow_backups/tick_42/src/main.py
            rel_path = target_absolute_path.relative_to(self.project_root)
        except ValueError:
            # Фолбэк на случай, если файл каким-то чудом оказался вне корня
            rel_path = Path(target_absolute_path.name)

        backup_path = tick_dir / rel_path

        # Если в рамках одного тика агент пишет в один и тот же файл 5 раз,
        # мы сохраняем только самую первую, ИСХОДНУЮ версию файла
        if not backup_path.exists():
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target_absolute_path, backup_path)
            system_logger.debug(f"[Shadow Backup] Создан бэкап: {rel_path} (Tick: {tick_id})")

        return True

    def commit_transaction(self, tick_id: int | str):
        """
        Удаляет папку с бэкапами, так как транзакция (ReAct-цикл) прошла успешно и система не упала.
        Вызывается Оркестратором в самом конце.
        """
        tick_dir = self._get_tick_dir(tick_id)
        if tick_dir.exists():
            try:
                shutil.rmtree(tick_dir)
                system_logger.debug(
                    f"[Shadow Backup] Транзакция {tick_id} успешна, временные бэкапы удалены."
                )
            except Exception as e:
                system_logger.error(
                    f"[Shadow Backup] Ошибка очистки бэкапов транзакции {tick_id}: {e}"
                )

    def rollback_transaction(self, tick_id: int | str):
        """
        Восстанавливает все файлы, измененные в рамках указанного тика, обратно в проект.
        Вызывается Watchdog'ом при старте системы, если прошлый запуск крашнулся.
        """
        tick_dir = self._get_tick_dir(tick_id)
        if not tick_dir.exists():
            system_logger.warning(f"[Shadow Backup] Нет данных для отката транзакции {tick_id}.")
            return

        system_logger.warning(f"[Shadow Backup] Аварийный откат транзакции {tick_id}.")

        try:
            # Ищем все файлы в папке бэкапа рекурсивно
            for backup_file in tick_dir.rglob("*"):
                if backup_file.is_file():
                    # Вычисляем оригинальный путь
                    rel_path = backup_file.relative_to(tick_dir)
                    original_path = self.project_root / rel_path

                    # Восстанавливаем файл (с перезаписью)
                    original_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, original_path)
                    system_logger.info(f"[Shadow Backup] Восстановлен файл: {rel_path}")

            # После успешного отката удаляем следы
            shutil.rmtree(tick_dir)
            system_logger.info(
                f"[Shadow Backup] Откат транзакции {tick_id} успешно завершен. Система в безопасности."
            )

        except Exception as e:
            system_logger.error(
                f"[Shadow Backup] Критическая ошибка отката транзакции {tick_id}: {e}"
            )
