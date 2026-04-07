import aiofiles
from pathlib import Path
from src.l00_utils.managers.logger import system_logger

class PromptBuilder:
    """
    Отвечает за физическое чтение .md файлов и сборку системного промпта.
    """
    def __init__(self):
        # Текущая директория (src/l04_agency/main_agent/prompt/)
        current_dir = Path(__file__).resolve().parent
        project_root = current_dir.parents[3] # Корень проекта
        self.system_dir = current_dir / "system" # Системные промпты неизменяемы
        self.personality_dir = project_root / "agent" / "prompt" # Промпты личности берутся из папки пользователя

    async def _read_md(self, filepath: Path) -> str:
        """Асинхронно читает файл. Если файла нет - возвращает пустоту и ругается в лог."""
        if not filepath.exists():
            system_logger.error(f"[PromptBuilder] Файл промпта не найден: {filepath.name}")
            return "[ФАЙЛ ПРОМПТА НЕ НАЙДЕН]"
        
        try:
            async with aiofiles.open(filepath, mode="r", encoding="utf-8") as f:
                content = await f.read()
                return content.strip() + "\n\n"
        except Exception as e:
            system_logger.error(f"[PromptBuilder] Ошибка чтения {filepath.name}: {e}")
            return ""

    async def build_prompt(self, cycle_type: str) -> str:
        """
        Собирает франкенштейна из .md файлов в зависимости от типа цикла.
        """
        # Базовые файлы, которые нужны всегда
        soul = await self._read_md(self.personality_dir / "SOUL.md") # Личность
        instructions = await self._read_md(self.system_dir / "INSTRUCTIONS.md") # Системные инструкции

        full_prompt = soul + instructions

        # Добавляем специфичные файлы в зависимости от цикла
        if cycle_type == "event_driven":
            examples_of_style = await self._read_md(self.personality_dir / "EXAMPLES_OF_STYLE.md")
            event_driven_rules = await self._read_md(self.system_dir / "EVENT_DRIVEN.md")
            full_prompt += examples_of_style + event_driven_rules

        elif cycle_type == "proactivity":
            examples_of_style = await self._read_md(self.personality_dir / "EXAMPLES_OF_STYLE.md")
            proactivity_rules = await self._read_md(self.system_dir / "PROACTIVITY.md")
            full_prompt += examples_of_style + proactivity_rules

        elif cycle_type == "consolidation":
            consolidation_rules = await self._read_md(self.system_dir / "CONSOLIDATION.md")
            full_prompt += consolidation_rules

        else:
            # Фолбэк на случай неизвестного цикла
            system_logger.warning(f"[PromptBuilder] Неизвестный тип цикла: '{cycle_type}'. Собран базовый промпт.")
            full_prompt += instructions

        return full_prompt.strip()