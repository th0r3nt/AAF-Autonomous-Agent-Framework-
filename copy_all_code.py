from pathlib import Path
import ast

base_path = Path.cwd() 

# Конфигурация отображения
EXCLUDE_DIRS_MAP = {
    'venv', '.venv', 'env', '__pycache__', '.git', '.idea', '.vscode', 
    'build', 'dist', '.pytest_cache', 'BAAI--bge-m3', 'vosk_model',
    'chroma_db', 'telegram_sessions', 'embedding_model', 'phrases',
    'logs', 'workspace', 'temp'
}
EXCLUDE_DIRS_CODE = {
    "venv", ".venv", "env",            # Виртуальные окружения
    "__pycache__",                     # Кэш Python
    ".git", ".idea", ".vscode",        # Служебные папки Git и редакторов
    "build", "dist", ".pytest_cache",  # Папки сборки и тестов
    "BAAI--bge-m3", "vosk_model"

}

ALLOWED_EXTENSIONS_MAP = {'.py', '.md', '.yaml', '.yml', '.json', '.txt', '.dockerignore', 'Dockerfile', '.gitignore', '.env.example', '.example'}
ALLOWED_EXTENSIONS_CODE = {".md", ".py", ".yaml", ".html", ".css", ".js", ".yml", "Dockerfile", ".gitignore", ".dockerignore", ".env.example", "example"}  # Расширения, которые нужно добавить в хранилище (обязательно с точками)

# КАРТА

def get_project_structure():
    """Генерирует дерево проекта и выводит его в консоль"""
    try:
        # Находим корень (папка, где лежит этот скрипт)
        project_root = Path(__file__).resolve().parent
        
        def build_tree(dir_path: Path, prefix: str = "") -> str:
            tree_str = ""
            
            # Читаем описание из __init__.py для папок в src
            docstring = ""
            init_file = dir_path / "__init__.py"
            if init_file.exists():
                try:
                    with open(init_file, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                        doc = ast.get_docstring(tree)
                        if doc:
                            docstring = f"  # {doc.splitlines()[0]}"
                except Exception: 
                    pass

            # Имя текущей папки
            folder_icon = "📂" if dir_path != project_root else "🏠"
            tree_str += f"{prefix}{folder_icon} {dir_path.name}/{docstring}\n"
            
            try:
                # Получаем список всех элементов, сортируем: сначала папки, потом файлы
                items = sorted(list(dir_path.iterdir()), key=lambda x: (not x.is_dir(), x.name))
            except PermissionError:
                return tree_str

            # Фильтруем
            filtered_items = []
            for item in items:
                if item.is_dir():
                    if item.name not in EXCLUDE_DIRS_MAP and not item.name.startswith('.'):
                        filtered_items.append(item)
                else:
                    if item.suffix in ALLOWED_EXTENSIONS_MAP or item.name == "Dockerfile":
                        filtered_items.append(item)

            # Рекурсивный обход
            for i, item in enumerate(filtered_items):
                is_last = (i == len(filtered_items) - 1)
                connector = "└── " if is_last else "├── "
                
                if item.is_dir():
                    tree_str += build_tree(item, prefix + connector)
                else:
                    tree_str += f"{prefix}{connector}📄 {item.name}\n"
                    
            return tree_str
        
        # Добавляем краткую справку по Инстансам
        instances_dir = project_root / "Instances"
        if instances_dir.exists():
            agents = [d.name for d in instances_dir.iterdir() if d.is_dir() and d.name != "Template"]
            print(f"\n🤖 Активных инстансов: {len(agents)} {agents if agents else ''}")

        return build_tree(project_root)
        
    except Exception as e:
        print(f"❌ Ошибка при генерации карты: {e}")

if __name__ == "__main__":
    get_project_structure()


def get_all_code():
    all_code = []

    all_code.append(
"""
Привет. Я - разработчик на Python. Сейчас я скину тебе свой проект. 
Ты будешь помогать по нему как отдельный программист: у тебя может быть своё мнение. 
Ты выступаешь в роли эксперта по этому проекту, будешь помогать мне с ним работать, давать советы по структуре и улучшению.
Также ты обязан иметь своё мнение по архитектуре, структуре или стилю кода - ты можешь критиковать код и давать советы по улучшению.

Так как я - углеродная нейросеть, моя оперативная память в мозге ограничена. 
Поэтому не удивляйся, если я буду часто обращаться к тебе с просьбой напомнить структуру проекта и прочее.
Проект обладает довольно сложной архитектурой, и я могу забывать детали.

Для начала проведи брифинг: каков статус проекта/файлов, так как я к чертям забыл, на каком моменте остановился.
Вот структура текущего проекта и все основные файлы с кодом:
""")

    # КОД
    for file_path in base_path.rglob("*"):
        # Проверяем, нет ли в пути к файлу любой из запрещенных папок
        if any(excluded in file_path.parts for excluded in EXCLUDE_DIRS_CODE): # file_path.parts возвращает кортеж всех папок в пути
            continue

        # Пропускаем, если это папка или расширение не в списке
        if not file_path.is_file() or file_path.suffix not in ALLOWED_EXTENSIONS_CODE:
            continue
        
        # Также полезно пропустить сам файл-сборщик, если он .py, чтобы не копировать самого себя
        if file_path.name == "copy_all_code.py": # Заменить на имя этого скрипта
            continue

        try:
            code = file_path.read_text(encoding="utf-8")
            all_code.append(f"\n\n\n# Файл: {file_path} \n\n{code} \n\nКонец файла '{file_path}'\n\n\n")

        except Exception as e:
            print(f"Ошибка при чтении {file_path}: {e}")

    all_code = "".join(all_code)
    map = get_project_structure()
    return all_code + map





p = Path("all_code.txt")

result = get_all_code()
p.write_text(result, encoding="utf-8")
