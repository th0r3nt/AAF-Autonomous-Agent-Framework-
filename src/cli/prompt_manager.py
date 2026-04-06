import shutil
from pathlib import Path
from src.cli import ui

current_dir = Path(__file__).resolve()
# Указываем на папку agent/prompt
prompt_dir = current_dir.parents[3] / "agent" / "prompt"

FILES_TO_CHECK = [
    ("SOUL.md", "SOUL.example.md"),
    ("EXAMPLES_OF_STYLE.md", "EXAMPLES_OF_STYLE.example.md"),
]

def run_personality_checks():
    """Проверяет наличие файлов личности. Если их нет - копирует из .example.md"""
    ui.info("Проверка файлов личности агента (Personality).")
    prompt_dir.mkdir(parents=True, exist_ok=True)
    
    is_new = False

    for target_file, example_file in FILES_TO_CHECK:
        target_path = prompt_dir / target_file
        example_path = prompt_dir / example_file

        if not target_path.exists():
            if example_path.exists():
                shutil.copy(example_path, target_path)
                is_new = True
            else:
                ui.warning(f"Шаблон {example_file} не найден. Восстановите его из репозитория.")

    if is_new:
        ui.success("Созданы базовые файлы личности в 'agent/prompt/'.")
        ui.console.print(
            "[dim cyan]💡 Совет: Вы можете изменить характер агента, отредактировав файлы SOUL.md и EXAMPLES_OF_STYLE.md в папке agent/prompt/.[/dim cyan]"
        )
    else:
        ui.success("Файлы личности найдены.")