import asyncio 
import shutil
import re
from pathlib import Path
from src.layer00_utils.workspace import workspace_manager
from src.layer03_brain.agent.skills.auto_schema import llm_skill
from src.layer00_utils.config_manager import config

@llm_skill(
    description="Читает любой файл. Можно использовать и абсолютные, и относительные пути. Автоматически определяет кодировку.",
    parameters={"filepath": "Абсолютный или относительный VFS путь к файлу."}
)
def read_file(filepath: str) -> str:
    try:
        target_path = workspace_manager.resolve_vfs_path(filepath, mode='read')
        if not target_path.exists() or not target_path.is_file():
            return f"Ошибка: Файл '{filepath}' не найден."

        content = None
        for enc in ['utf-8', 'utf-16', 'windows-1251', 'latin-1']:
            try:
                with open(target_path, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return "Ошибка: Файл является бинарным или имеет неизвестную кодировку."

        MAX_CHARS = config.llm.limits.max_file_read_chars
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS] + "\n\n... [ОСТАЛЬНАЯ ЧАСТЬ ФАЙЛА ОБРЕЗАНА ИЗ-ЗА ЛИМИТОВ ТОКЕНОВ]"
        return f"Содержимое файла '{filepath}':\n\n{content}"
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Ошибка при чтении файла: {e}"

@llm_skill(
    description="[Работает только в sandbox/] Создает или перезаписывает файл. Автоматически создает все нужные папки на пути.",
    parameters={
        "filepath": "VFS путь (например: 'sandbox/api/server.py')",
        "content": "Текстовое содержимое файла"
    }
)
async def write_file(filepath: str, content: str) -> str:
    try:
        # Защита от дурака (нейросети): Очистка Markdown-блоков для файлов кода
        if filepath.endswith(('.py', '.json', '.yaml', '.yml', '.sh', '.txt', '.md')):
            # Ищем паттерн ```python ... ``` или просто ``` ... ```
            md_pattern = re.compile(r'^```[a-zA-Z]*\n(.*?)\n```$', re.DOTALL)
            match = md_pattern.search(content.strip())
            if match:
                content = match.group(1)

        target_path = workspace_manager.resolve_vfs_path(filepath, mode='write')
        
        def _write():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
        await asyncio.to_thread(_write)
        return f"Файл успешно сохранен/перезаписан: {filepath}"
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Ошибка при записи файла: {e}"

@llm_skill(
    description="[Работает только в sandbox/] Удаляет файл.",
    parameters={"filepath": "VFS путь к файлу (например: 'sandbox/temp.txt')"}
)
async def delete_file(filepath: str) -> str:
    try:
        target_path = workspace_manager.resolve_vfs_path(filepath, mode='delete')
        if not target_path.exists() or not target_path.is_file():
            return f"Ошибка: Файл '{filepath}' не найден."
        await asyncio.to_thread(target_path.unlink)
        return f"Файл '{filepath}' успешно удален."
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Ошибка при удалении файла: {e}"

@llm_skill(
    description="Архитектурная карта. Возвращает структуру любой директории.",
    parameters={"path": "VFS путь к директории (например: 'sandbox/projects/', 'src/layer03_brain/')"}
)
def get_tree(path: str) -> str:
    try:
        target_path = workspace_manager.resolve_vfs_path(path, mode='read')
        if not target_path.exists() or not target_path.is_dir():
            return f"Ошибка: Директория '{path}' не существует."

        EXCLUDE_DIRS = {'__pycache__', '.git', '.idea', '.vscode', 'venv', '.venv', 'blobs', 'snapshots'}
        
        def build_tree(dir_path: Path, prefix: str = "") -> str:
            tree_str = f"{prefix}📂 {dir_path.name}/\n"
            try:
                items = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError:
                return tree_str
                
            items = [item for item in items if item.name not in EXCLUDE_DIRS]
            
            for i, item in enumerate(items):
                is_last = (i == len(items) - 1)
                connector = "└── " if is_last else "├── "
                if item.is_dir():
                    tree_str += build_tree(item, prefix + ("    " if is_last else "│   "))
                else:
                    tree_str += f"{prefix}{connector}📄 {item.name}\n"
            return tree_str

        return f"Структура директории '{path}':\n\n{build_tree(target_path)}"
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Ошибка генерации дерева: {e}"

@llm_skill(
    description="[Работает только в sandbox/] Создает пустую директорию. Автоматически создает промежуточные папки.",
    parameters={"path": "VFS путь (например: 'sandbox/projects/new_app/')"}
)
async def make_dir(path: str) -> str:
    try:
        target_path = workspace_manager.resolve_vfs_path(path, mode='write')
        await asyncio.to_thread(target_path.mkdir, parents=True, exist_ok=True)
        return f"Директория успешно создана: {path}"
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Ошибка создания директории: {e}"

@llm_skill(
    description="[Работает только в sandbox/] Рекурсивное удаление папки со всем содержимым.",
    parameters={"path": "VFS путь к удаляемой папке (например: 'sandbox/projects/old_app/')"}
)
async def remove_dir(path: str) -> str:
    try:
        clean_path = path.replace("\\", "/").strip("/")
        if clean_path == "sandbox":
            return "Критическая ошибка безопасности: Запрещено удалять корень песочницы целиком!"
            
        target_path = workspace_manager.resolve_vfs_path(path, mode='delete')
        if not target_path.exists() or not target_path.is_dir():
            return f"Ошибка: Директория '{path}' не найдена."
            
        await asyncio.to_thread(shutil.rmtree, target_path)
        return f"Директория '{path}' и всё её содержимое успешно удалены."
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Ошибка удаления директории: {e}"

@llm_skill(
    description="[Работает только в sandbox/] Универсальное перемещение и переименование файлов/папок.",
    parameters={"src": "VFS путь исходника", "dest": "VFS путь назначения (только 'sandbox/')"}
)
async def move_rename(src: str, dest: str) -> str:
    try:
        src_path = workspace_manager.resolve_vfs_path(src, mode='read')
        dest_path = workspace_manager.resolve_vfs_path(dest, mode='write')
        
        if not src_path.exists():
            return f"Ошибка: Источник '{src}' не найден."
            
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.move, str(src_path), str(dest_path))
        return f"Успешно перемещено/переименовано: '{src}' -> '{dest}'"
    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Ошибка при перемещении: {e}"