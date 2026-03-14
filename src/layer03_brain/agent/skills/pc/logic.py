import platform
import ctypes
import ast
import asyncio 
import os
from pathlib import Path

from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer00_utils.image_tools import compress_and_encode_image

from src.layer00_utils.workspace import (
    workspace_manager
)
from src.layer00_utils._tools import (
    make_screenshot
)
from src.layer02_sensors.pc.terminal.output import (
    terminal_output
)
from src.layer02_sensors.pc.voice.tts import (
    generate_voice
)
from src.layer02_sensors.pc.windows_control import (
    show_windows_notification
)


def lock_pc():
    """Блокирует Windows"""
    if config.system.flags.headless_mode or platform.system() != "Windows":
        return "Ошибка: Данное действие недоступно в серверном (Headless) режиме."
    
    if platform.system() == "Windows":
        try:
            ctypes.windll.user32.LockWorkStation()
            system_logger.debug("Рабочая станция Windows заблокирована.")
            return "Рабочая станция Windows заблокирована."
        except Exception as e:
            return f"Ошибка при блокировке рабочей станции: {e}"
    else:
        return "Данная команда работает только в операционной системе Windows."

async def print_to_terminal(text: str) -> str:
    """Пишет в терминал основного ПК"""
    await terminal_output(text)
    return "Сообщение успешно выведено в терминал."

async def speak_text(text: str) -> str:
    """Озвучивает текст"""
    # Запускаем генерацию и озвучку как независимую фоновую задачу
    asyncio.create_task(generate_voice(text))
    return "Процесс генерации голоса и озвучки запущен в фоновом режиме."

def list_local_directory(path: str = ".") -> str:
    """Показывает содержимое директории"""
    try:
        # Resolve делает путь абсолютным и убирает всякие '../'
        target_path = Path(path).resolve()
        
        if not target_path.exists():
            return f"Ошибка: Директория '{path}' не существует."
        if not target_path.is_dir():
            return f"Ошибка: '{path}' не является директорией."

        items = os.listdir(target_path)
        dirs = [d for d in items if (target_path / d).is_dir()]
        files = [f for f in items if (target_path / f).is_file()]

        dirs.sort()
        files.sort()

        result = f"Содержимое директории '{target_path}':\n"
        result += "Папки:\n" + ("\n".join([f" - {d}/" for d in dirs]) if dirs else " (нет)") + "\n"
        result += "Файлы:\n" + ("\n".join([f" - {f}" for f in files]) if files else " (нет)")
        return result
    except Exception as e:
        return f"Ошибка при чтении директории: {e}"

def read_local_system_file(filepath: str) -> str:
    """Читает содержимое файла с умным поиском по проекту и защитой путей Docker"""
    try:
        # 1. Очистка пути от артефактов LLM и Docker
        clean_path = filepath.strip()
        if clean_path.startswith("file:///"):
            clean_path = clean_path.replace("file:///", "", 1)
        if clean_path.startswith("/app/"):
            clean_path = clean_path.replace("/app/", "", 1)
            
        # 2. Жестко определяем корень проекта 
        current_dir = Path(__file__).resolve()
        src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
        project_root = src_dir.parent if src_dir else current_dir.parents[5]
        
        requested_path = Path(clean_path)
        
        # 3. Сначала пробуем склеить корень проекта и запрошенный путь
        target_path = (project_root / requested_path).resolve()

        # Защита от выхода за пределы проекта 
        if not str(target_path).startswith(str(project_root)):
            system_logger.warning(f"[Security] Агент попытался выйти за пределы проекта: {target_path}")
            return "Ошибка безопасности: Доступ за пределы корневой директории проекта запрещен."

        # Защита от чтения песочницы через системный инструмент
        if "workspace" in target_path.parts and "sandbox" in target_path.parts:
            return "Ошибка: Для чтения файлов из песочницы (sandbox/отчеты субагентов) используй специализированный инструмент 'read_sandbox_file'."

        # 4. Если по прямому пути файла нет, включаем "Умный поиск"
        if not target_path.exists():
            filename = requested_path.name
            
            # Игнорируем виртуальные окружения, кэш, гит и ПЕСОЧНИЦУ
            exclude_dirs = {'.venv', 'venv', 'env', '__pycache__', '.git', '.idea', 'build'}
            
            matches = [
                p for p in project_root.rglob(filename)
                if p.is_file() and not any(part in p.parts for part in exclude_dirs)
            ]

            if not matches:
                return f"Ошибка: Файл '{filename}' не найден ни по указанному пути, ни где-либо еще в проекте."

            if len(matches) > 1:
                match_list = "\n".join([f"- {m.relative_to(project_root).as_posix()}" for m in matches])
                return f"Найдено несколько файлов с именем '{filename}'. Уточните путь, вызвав функцию еще раз с одним из этих путей:\n{match_list}"

            # Если нашли ровно один файл — берем его!
            target_path = matches[0]
            system_logger.debug(f"[Smart Search] Файл '{filename}' найден по пути: {target_path.relative_to(project_root)}")

        # 5. Секьюрити чек: жесткий блок на .env и .log
        if target_path.name == ".env" or target_path.suffix == ".env":
            system_logger.warning(f"[Security] Агент попытался прочитать файл конфигурации: {target_path}")
            return "Ошибка безопасности: В доступе отказано. Чтение файлов конфигурации (.env) строго запрещено."
        
        if target_path.suffix == ".log":
            return "Ошибка: Для чтения логов системы строго используй специализированный инструмент 'read_recent_logs'."

        if not target_path.is_file():
            return f"Ошибка: '{target_path.relative_to(project_root).as_posix()}' не является файлом."

        # 6. Читаем файл
        content = None
        encodings_to_try = ['utf-8', 'utf-16', 'windows-1251', 'latin-1']
        
        for enc in encodings_to_try:
            try:
                with open(target_path, 'r', encoding=enc) as f:
                    content = f.read()
                break # Если прочиталось без ошибок, выходим из цикла
            except UnicodeDecodeError:
                continue # Пробуем следующую кодировку
                
        if content is None:
            return f"Ошибка: Невозможно прочитать '{filepath}'. Похоже, это бинарный файл (или используется неизвестная кодировка)."

        display_path = target_path.relative_to(project_root).as_posix()

        # 7. Защита контекста LLM
        MAX_CHARS = config.llm.limits.max_file_read_chars
        if len(content) > MAX_CHARS:
            truncated_content = content[:MAX_CHARS]
            return f"Содержимое файла '{display_path}' (Обрезано, слишком большой):\n\n{truncated_content}\n\n... [ОСТАЛЬНАЯ ЧАСТЬ ФАЙЛА ОБРЕЗАНА]"
        
        return f"Содержимое файла '{display_path}':\n\n{content}"
        
    except Exception as e:
        return f"Ошибка при чтении файла: {e}"
    
def read_sandbox_file(filename: str) -> str:
    """Обертка: читает файл исключительно из песочницы (workspace/sandbox)"""
    try:
        # Убираем пути, оставляем только имя (защита)
        clean_filename = os.path.basename(filename.replace("file:///", "").replace("/app/", ""))
        
        filepath = workspace_manager.get_sandbox_file(clean_filename)
        
        if not filepath.exists() or not filepath.is_file():
            return f"Ошибка: Файл '{clean_filename}' не найден в песочнице (sandbox)."
            
        content = None
        for enc in ['utf-8', 'utf-16', 'windows-1251', 'latin-1']:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
                
        if content is None:
            return f"Ошибка: Файл '{clean_filename}' является бинарным или имеет неизвестную кодировку."
            
        # Лимит для песочницы
        if len(content) > 80000:
            content = content[:80000] + "\n\n... [ОСТАЛЬНАЯ ЧАСТЬ ФАЙЛА ОБРЕЗАНА ИЗ-ЗА ЛИМИТОВ]"
            
        return f"Содержимое файла '{clean_filename}' из песочницы:\n\n{content}"
    except Exception as e:
        return f"Ошибка при чтении файла из песочницы: {e}"
    

def get_system_architecture_map(*args, **kwargs) -> str:
    """Генерирует дерево проекта (корень + src/), показывая .py и .md файлы"""
    try:
        # 1. Находим корень проекта
        current_dir = Path(__file__).resolve()
        src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
        if src_dir:
            project_root = src_dir.parent
        else:
            return "Ошибка: Не удалось найти корневую директорию проекта."
                
        if not project_root.exists():
            return "Ошибка: Не удалось найти корневую директорию проекта."

        # Жесткий фильтр папок, куда вообще не надо лезть (экономим токены LLM)
        EXCLUDE_DIRS = {
            'venv', '.venv', 'env', '__pycache__', '.git', '.idea', '.vscode', 
            'build', 'dist', '.pytest_cache', 'BAAI--bge-m3', 'vosk_model',
            'chroma_db', 'telegram_sessions', 'embedding_model', 'phrases',
            'logs' # Логи тоже исключаем, там огромные файлы контекста
        }
        
        # Разрешенные файлы для отображения в дереве
        ALLOWED_EXTENSIONS = {'.py', '.md', '.yaml', '.json', '.txt'}
        
        def build_tree(dir_path: Path, prefix: str = "") -> str:
            tree_str = ""
            
            # Пытаемся прочитать docstring из __init__.py (если это Python-модуль)
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

            # Имя текущей папки + её описание
            tree_str += f"{prefix}📂 {dir_path.name}/{docstring}\n"
            
            try:
                items = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError:
                return tree_str
                
            # Фильтруем мусорные папки
            items = [item for item in items if item.name not in EXCLUDE_DIRS]
            
            # Оставляем только папки и разрешенные файлы (.py, .md)
            filtered_items = []
            for item in items:
                if item.is_dir():
                    filtered_items.append(item)
                elif item.is_file() and item.suffix in ALLOWED_EXTENSIONS:
                    filtered_items.append(item)

            for i, item in enumerate(filtered_items):
                is_last = (i == len(filtered_items) - 1)
                connector = "└── " if is_last else "├── "
                
                if item.is_dir():
                    extension = "    " if is_last else "│   "
                    tree_str += build_tree(item, prefix + extension)
                else:
                    tree_str += f"{prefix}{connector}📄 {item.name}\n"
                    
            return tree_str

        # Запускаем сборку дерева от корня проекта
        map_str = build_tree(project_root)
        system_logger.debug("[System Map] Сгенерирована архитектурная карта проекта (включая .md).")
        return f"Архитектурная карта проекта (корень '{project_root.name}'):\n\n{map_str}"

    except Exception as e:
        system_logger.error(f"Ошибка при генерации карты проекта: {e}")
        return f"Ошибка при генерации карты проекта: {e}"

def clean_temp_workspace() -> str:
    """Обертка: очищает временные файлы"""
    return workspace_manager.clean_temp_workspace()

async def send_windows_notification(title: str, text: str) -> str:
    """Обертка: отправляет push-уведомление Windows"""
    # Запускаем синхронную функцию в фоне, хотя win10toast и так юзает потоки,
    # это дополнительная страховка для asyncio
    return await asyncio.to_thread(show_windows_notification, title, text)

async def look_at_screen() -> dict | str:
    """Обертка: делает скриншот и передает его в контекст LLM"""
    try:
        filepath = await make_screenshot()
        b64_string = await asyncio.to_thread(compress_and_encode_image, filepath)
        # Магический словарь, который react.py превратит в картинку для Gemini
        return {"__image_base64__": b64_string}
    except Exception as e:
        return f"Не удалось получить изображение с экрана: {e}"


async def write_local_file(filename: str, content: str) -> str:
    """Обертка: пишет текстовый файл в изолированную песочницу (sandbox)"""
    try:
        # Очищаем путь, оставляя только имя файла (защита от двойных путей)
        clean_filename = os.path.basename(filename) 
        
        filepath = workspace_manager.get_sandbox_file(clean_filename)
        
        # Запускаем I/O операцию в отдельном потоке
        def _write():
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        await asyncio.to_thread(_write)
        return f"Файл успешно сохранен/перезаписан по пути: {filepath}"
    except Exception as e:
        return f"Ошибка при записи файла: {e}"
    
PC_REGISTRY = {
    "lock_pc": lock_pc,
    "print_to_terminal": print_to_terminal,
    "speak_text": speak_text,
    "list_local_directory": list_local_directory,
    "read_local_system_file": read_local_system_file,
    "read_sandbox_file": read_sandbox_file,
    "get_system_architecture_map": get_system_architecture_map,
    "clean_temp_workspace": clean_temp_workspace,
    "send_windows_notification": send_windows_notification,
    "look_at_screen": look_at_screen,
    "write_local_file": write_local_file,
}