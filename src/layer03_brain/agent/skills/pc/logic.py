import platform
import ctypes
import ast
import asyncio 
import os
from pathlib import Path

from src.layer00_utils.config_manager import config
from src.layer00_utils.image_tools import compress_and_encode_image
from src.layer00_utils.workspace import workspace_manager
from src.layer00_utils._tools import make_screenshot
from src.layer02_sensors.pc.terminal.output import terminal_output
from src.layer02_sensors.pc.voice.tts import generate_voice
from src.layer02_sensors.pc.windows_control import show_windows_notification
from src.layer03_brain.agent.skills.auto_schema import llm_skill

@llm_skill(
    description="Блокирует рабочую станцию Windows"
)
def lock_pc() -> str:
    if config.system.flags.headless_mode or platform.system() != "Windows":
        return "Ошибка: Данное действие недоступно."
    try:
        ctypes.windll.user32.LockWorkStation()
        return "Рабочая станция Windows заблокирована."
    except Exception as e:
        return f"Ошибка: {e}"

@llm_skill(
    description="Выводит сообщение в терминал основного ПК. Важно: запрещено писать сюда просто одно слово 'OK'", 
    parameters={
        "text": "Текст ответа"
    }
)
async def print_to_terminal(text: str) -> str:
    await terminal_output(text)
    return "Сообщение успешно выведено в терминал."

@llm_skill(
    description="Озвучивает текст через динамики основного ПК.", 
    parameters={
        "text": "Текст для озвучки."
    }
)
async def speak_text(text: str) -> str:
    asyncio.create_task(generate_voice(text))
    return "Процесс генерации голоса и озвучки запущен в фоновом режиме."

@llm_skill(
    description="Показывает список файлов и папок в указанной локальной директории на основном ПК.", 
    parameters={
        "path": "Путь к директории (например: '.', 'src/')"
    }
)
def list_local_directory(path: str = ".") -> str:
    try:
        clean_path = path.replace("\\", "/").strip("/")
        
        # Умный резолв пути: перехватываем обращения к песочнице
        if clean_path.startswith("workspace"):
            target_path = (workspace_manager.workspace_dir.parent / clean_path).resolve()
        else:
            target_path = (workspace_manager.project_root / clean_path).resolve()

        # Жесткая защита от выхода за пределы проекта
        if not str(target_path).startswith(str(workspace_manager.project_root)):
            return "Ошибка безопасности: Доступ за пределы корневой папки проекта запрещен."

        if not target_path.exists(): 
            return f"Ошибка: Директория '{path}' не существует."
        
        if not target_path.is_dir(): 
            return f"Ошибка: '{path}' не является директорией."
        
        items = os.listdir(target_path)
        dirs = sorted([d for d in items if (target_path / d).is_dir()])
        files = sorted([f for f in items if (target_path / f).is_file()])
        result = f"Содержимое директории '{target_path}':\nПапки:\n" + ("\n".join([f" - {d}/" for d in dirs]) if dirs else " (нет)") + "\n"
        result += "Файлы:\n" + ("\n".join([f" - {f}" for f in files]) if files else " (нет)")

        return result
    except Exception as e:
        return f"Ошибка при чтении директории: {e}"

@llm_skill(
    description="Читает текстовое содержимое исходного кода твоей системы (папка src/). Используй ЭТОТ инструмент для анализа системных файлов.", 
    parameters={
        "filepath": "Имя файла или путь к нему (например: 'main.py')"
    }
)
def read_local_system_file(filepath: str) -> str:
    try:
        clean_path = filepath.strip().replace("file:///", "", 1).replace("/app/", "", 1)
        current_dir = Path(__file__).resolve()
        src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
        project_root = src_dir.parent if src_dir else current_dir.parents[5]
        requested_path = Path(clean_path)
        target_path = (project_root / requested_path).resolve()

        if not str(target_path).startswith(str(project_root)): 
            return "Ошибка безопасности: Доступ запрещен."
        
        if "workspace" in target_path.parts and "sandbox" in target_path.parts: 
            return "Используй 'read_sandbox_file'."

        if not target_path.exists():
            filename = requested_path.name
            exclude_dirs = {'.venv', 'venv', 'env', '__pycache__', '.git', '.idea', 'build'}
            matches = [p for p in project_root.rglob(filename) if p.is_file() and not any(part in p.parts for part in exclude_dirs)]

            if not matches: 
                return f"Файл '{filename}' не найден."
            
            if len(matches) > 1: 
                return "Найдено несколько файлов. Уточните:\n" + "\n".join([f"- {m.relative_to(project_root).as_posix()}" for m in matches])
            
            target_path = matches[0]

        if target_path.name == ".env" or target_path.suffix == ".env": 
            return "В доступе отказано."
        
        if target_path.suffix == ".log": 
            return "Используй 'read_recent_logs'."
        
        if not target_path.is_file(): 
            return f"'{target_path}' не является файлом."

        content = None
        for enc in ['utf-8', 'utf-16', 'windows-1251', 'latin-1']:
            try:
                with open(target_path, 'r', encoding=enc) as f: 
                    content = f.read()
                break
            except UnicodeDecodeError: 
                continue
                
        if content is None: 
            return "Невозможно прочитать файл."
        
        display_path = target_path.relative_to(project_root).as_posix()
        MAX_CHARS = config.llm.limits.max_file_read_chars

        if len(content) > MAX_CHARS:
            return f"Содержимое '{display_path}' (Обрезано):\n\n{content[:MAX_CHARS]}\n\n... [ОСТАЛЬНАЯ ЧАСТЬ ФАЙЛА ОБРЕЗАНА]"
        
        return f"Содержимое файла '{display_path}':\n\n{content}"
    except Exception as e:
        return f"Ошибка при чтении файла: {e}"
    
@llm_skill(
    description="Читает файлы ИСКЛЮЧИТЕЛЬНО из твоей песочницы (workspace/sandbox/). Полезно, чтобы читать отчеты субагентов.", 
    parameters={
        "filename": "Имя файла в песочнице."
    }
)
def read_sandbox_file(filename: str) -> str:
    try:
        clean_filename = os.path.basename(filename.replace("file:///", "").replace("/app/", ""))
        filepath = workspace_manager.get_sandbox_file(clean_filename)

        if not filepath.exists() or not filepath.is_file(): 
            return f"Файл '{clean_filename}' не найден."
            
        content = None
        for enc in ['utf-8', 'utf-16', 'windows-1251', 'latin-1']:
            try:
                with open(filepath, 'r', encoding=enc) as f: 
                    content = f.read()
                break
            except UnicodeDecodeError: 
                continue
                
        if content is None: 
            return "Файл является бинарным или имеет неизвестную кодировку."
        
        if len(content) > 80000: 
            content = content[:80000] + "\n\n... [ОСТАЛЬНАЯ ЧАСТЬ ФАЙЛА ОБРЕЗАНА ИЗ-ЗА ЛИМИТОВ]"
        return f"Содержимое файла '{clean_filename}':\n\n{content}"
    except Exception as e:
        return f"Ошибка: {e}"

@llm_skill(
    description="Возвращает полное дерево файловой системы твоего проекта (папки src/) на основном ПК."
)
def get_system_architecture_map() -> str:
    try:
        current_dir = Path(__file__).resolve()
        src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
        if not src_dir: 
            return "Ошибка: Не удалось найти корневую директорию проекта."
        project_root = src_dir.parent
                
        EXCLUDE_DIRS = {'venv', '.venv', 'env', '__pycache__', '.git', '.idea', '.vscode', 'build', 'dist', '.pytest_cache', 'BAAI--bge-m3', 'vosk_model', 'chroma_db', 'telegram_sessions', 'embedding_model', 'phrases', 'logs'}
        ALLOWED_EXTENSIONS = {'.py', '.md', '.yaml', '.json', '.txt'}
        
        def build_tree(dir_path: Path, prefix: str = "") -> str:
            tree_str = ""
            docstring = ""
            init_file = dir_path / "__init__.py"
            if init_file.exists() and init_file.is_file():
                try:
                    with open(init_file, 'r', encoding='utf-8') as f:
                        module = ast.parse(f.read())
                        doc = ast.get_docstring(module)
                        if doc: 
                            first_line = doc.split('\n')[0].strip()
                            docstring = f"  # {first_line}"
                except Exception: 
                    pass

            tree_str += f"{prefix}📂 {dir_path.name}/{docstring}\n"
            try: 
                items = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError: 
                return tree_str
                
            items = [item for item in items if item.name not in EXCLUDE_DIRS]
            filtered_items = [item for item in items if item.is_dir() or (item.is_file() and item.suffix in ALLOWED_EXTENSIONS)]

            for i, item in enumerate(filtered_items):
                is_last = (i == len(filtered_items) - 1)
                connector = "└── " if is_last else "├── "
                if item.is_dir():
                    tree_str += build_tree(item, prefix + ("    " if is_last else "│   "))
                else:
                    tree_str += f"{prefix}{connector}📄 {item.name}\n"
            return tree_str

        return f"Архитектурная карта проекта:\n\n{build_tree(project_root)}"
    except Exception as e:
        return f"Ошибка при генерации карты проекта: {e}"

@llm_skill(
    description="Полностью очищает твою папку временных файлов (workspace/temp/)."
)
def clean_temp_workspace() -> str:
    return workspace_manager.clean_temp_workspace()

@llm_skill(
    description="Отправляет системное push-уведомление Windows на экран основного ПК.",
    parameters={
        "title": "Заголовок уведомления", "text": "Текст уведомления."
    }
)
async def send_windows_notification(title: str, text: str) -> str:
    return await asyncio.to_thread(show_windows_notification, title, text)

@llm_skill(
    description="Делает снимок (скриншот) всех мониторов основного ПК и мгновенно загружает его в контекст."
)
async def look_at_screen() -> dict | str:
    try:
        filepath = await make_screenshot()
        b64_string = await asyncio.to_thread(compress_and_encode_image, filepath)
        return {"__image_base64__": b64_string}
    except Exception as e:
        return f"Не удалось получить изображение с экрана: {e}"

@llm_skill(
    description="Создает или перезаписывает текстовый файл в твоей изолированной директории (workspace/sandbox/).", 
    parameters={
        "filename": "Имя файла с расширением (например: 'plan.md').", "content": "Текстовое содержимое."
    }
)
async def write_local_file(filename: str, content: str) -> str:
    try:
        clean_filename = os.path.basename(filename) 
        filepath = workspace_manager.get_sandbox_file(clean_filename)
        def _write():        
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        await asyncio.to_thread(_write)
        return f"Файл успешно сохранен/перезаписан по пути: {filepath}"
    except Exception as e:
        return f"Ошибка при записи файла: {e}"