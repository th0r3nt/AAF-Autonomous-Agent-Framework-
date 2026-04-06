import os
import asyncio
from pathlib import Path

from src.l00_utils.managers.logger import system_logger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.vfs.client import VFSClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill

# Список директорий, которые лучше не показывать LLM, чтобы не тратить токены на мусор
IGNORED_DIRS = {".git", "__pycache__", "venv", "node_modules", ".idea"}


class FilesSearch(BaseInstrument):
    """
    Gоиск по файловой системе (Grep и Tree).
    """

    def __init__(self, client: 'VFSClient'):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.vfs_client = client

    # ==========================================
    # ПОИСК ПО СОДЕРЖИМОМУ (GREP)
    # ==========================================

    def _sync_search_content(self, query: str, dirpath: str, file_extension: str) -> ToolResult:
        if not query:
            return ToolResult.fail(msg="Ошибка: Строка для поиска (query) не может быть пустой.")

        # Если dirpath пустой, ищем по всей песочнице
        abs_path = (
            self.vfs_client.get_secure_path(dirpath) if dirpath else self.vfs_client.sandbox_path
        )

        if not abs_path:
            return ToolResult.fail(msg=f"Ошибка безопасности: Путь '{dirpath}' недопустим.")
        if not abs_path.exists() or not abs_path.is_dir():
            return ToolResult.fail(msg=f"Ошибка: Директория '{dirpath}' не найдена.")

        matches = []
        max_matches = 100  # Защита от переполнения контекста

        try:
            # Обходим дерево файлов
            for root, dirs, files in os.walk(abs_path):
                # Игнорируем мусорные директории
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

                for file in files:
                    if file_extension and not file.endswith(file_extension):
                        continue

                    file_path = Path(root) / file
                    # Получаем красивый относительный путь для вывода
                    rel_path = file_path.relative_to(self.vfs_client.sandbox_path).as_posix()

                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            for line_num, line in enumerate(f, 1):
                                if query in line:
                                    clean_line = line.strip()
                                    # Ограничиваем длину одной строки (вдруг там минифицированный JS на 10к символов)
                                    if len(clean_line) > 500:
                                        clean_line = clean_line[:497] + "..."

                                    matches.append(f"{rel_path}:{line_num}: {clean_line}")

                                    if len(matches) >= max_matches:
                                        matches.append(
                                            f"\n...[ПОИСК ОСТАНОВЛЕН: Найдено более {max_matches} совпадений]..."
                                        )
                                        return self._format_grep_result(query, matches)
                    except UnicodeDecodeError:
                        # Пропускаем бинарники (картинки, архивы, скомпилированные файлы)
                        continue

            if not matches:
                ext_info = f" (с расширением '{file_extension}')" if file_extension else ""
                return ToolResult.fail(
                    msg=f"По запросу '{query}' ничего не найдено в директории '{dirpath or 'sandbox/'}'{ext_info}."
                )

            return self._format_grep_result(query, matches)

        except Exception as e:
            system_logger.error(f"[VFS Search] Ошибка поиска текста: {e}")
            return ToolResult.fail(msg=f"Ошибка при выполнении поиска: {e}", error=str(e))

    def _format_grep_result(self, query: str, matches: list[str]) -> ToolResult:
        """
        Форматирует результат для красивой отдачи LLM.
        """
        res = [f"--- Результаты поиска по запросу '{query}' ---"]
        res.extend(matches)
        return ToolResult.ok(msg="\n".join(res), data=matches)

    # ==========================================
    # ДЕРЕВО ФАЙЛОВ
    # ==========================================

    def _sync_get_file_tree(self, dirpath: str, max_depth: int) -> ToolResult:
        abs_path = (
            self.vfs_client.get_secure_path(dirpath) if dirpath else self.vfs_client.sandbox_path
        )

        if not abs_path:
            return ToolResult.fail(msg="Ошибка безопасности.")
        if not abs_path.exists() or not abs_path.is_dir():
            return ToolResult.fail(msg=f"Ошибка: Директория '{dirpath}' не найдена.")

        tree_lines = [f"📁 {dirpath or 'sandbox'}/"]
        self._build_tree(
            abs_path,
            prefix="",
            tree_lines=tree_lines,
            current_depth=0,
            max_depth=max_depth,
        )

        result = "\n".join(tree_lines)

        # Защита: если файлов миллион, режем итоговую строку
        if len(result) > 20000:
            result = result[:19997] + "...\n[ДЕРЕВО ОБРЕЗАНО ИЗ-ЗА ПРЕВЫШЕНИЯ ЛИМИТА]"

        return ToolResult.ok(msg=result, data=tree_lines)

    def _build_tree(
        self,
        current_path: Path,
        prefix: str,
        tree_lines: list,
        current_depth: int,
        max_depth: int,
    ):
        if current_depth >= max_depth:
            tree_lines.append(
                f"{prefix}└── ...[Скрыто: превышена максимальная глубина {max_depth}]"
            )
            return

        try:
            # Получаем список файлов и папок, фильтруем скрытые и игнорируемые
            items = [
                item
                for item in current_path.iterdir()
                if item.name not in IGNORED_DIRS and not item.name.startswith(".")
            ]

            # Сортируем: сначала директории, потом файлы, по алфавиту
            items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

            count = len(items)
            for i, item in enumerate(items):
                is_last = i == count - 1
                connector = "└── " if is_last else "├── "

                if item.is_dir():
                    tree_lines.append(f"{prefix}{connector}📁 {item.name}/")
                    # Рекурсивно идем внутрь
                    extension = "    " if is_last else "│   "
                    self._build_tree(
                        item,
                        prefix + extension,
                        tree_lines,
                        current_depth + 1,
                        max_depth,
                    )
                else:
                    tree_lines.append(f"{prefix}{connector}📄 {item.name}")

                # Защита от бесконечного дерева, прерываем рекурсию, если накопили слишком много строк
                if len(tree_lines) > 300:
                    if not tree_lines[-1].endswith("[ЛИМИТ ФАЙЛОВ]"):
                        tree_lines.append(
                            f"{prefix}    └── ...[Дерево слишком большое, показаны первые n элементов]"
                        )
                    return

        except PermissionError:
            tree_lines.append(f"{prefix}└── [Отказано в доступе]")

    # ==========================================
    # АСИНХРОННЫЕ ФАСАДЫ
    # ==========================================

    @skill()
    async def search_content(
        self, query: str, dirpath: str = "", file_extension: str = None
    ) -> ToolResult:
        """
        Ищет текстовую строку во всех файлах внутри директории.
        Аналог линуксовой команды grep -r.
        """
        return await asyncio.to_thread(self._sync_search_content, query, dirpath, file_extension)

    @skill()
    async def get_file_tree(self, dirpath: str = "", max_depth: int = 10) -> ToolResult:
        """
        Возвращает визуальное дерево директорий и файлов.
        Полезно для оценки структуры проекта перед началом работы.
        """
        return await asyncio.to_thread(self._sync_get_file_tree, dirpath, max_depth)
