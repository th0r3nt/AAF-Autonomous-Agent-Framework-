# Файл: src/layer03_brain/llm/prompt/prompt_manager.py

from pathlib import Path
from src.layer00_utils.logger import system_logger
from src.layer00_utils.env_manager import AGENT_NAME

# Импортируем наш сгенерированный L0 справочник
from src.layer03_brain.agent.skills.registry import l0_manifest

class PromptManager:
    """Хранилище и сборка общих промптов из .md файлов и динамических манифестов"""
    def __init__(self):
        self.system_dir = Path(__file__).resolve().parent
        self.project_root = self.system_dir.parents[3]
        self.personality_dir = self.project_root / "Agents" / AGENT_NAME / "config" / "personality"

        self.SOUL = self._load_file(self.personality_dir / "SOUL.md")
        self.COMMUNICATION_STYLE = self._load_file(self.personality_dir / "COMMUNICATION_STYLE.md")
        self.EXAMPLES_OF_STYLE = self._load_file(self.personality_dir / "EXAMPLES_OF_STYLE.md")

        self.SYSTEM_INSTRUCTIONS = self._load_file(self.system_dir / "system" / "SYSTEM_INSTRUCTIONS.md")
        self.PROACTIVITY_INSTRUCTIONS = self._load_file(self.system_dir / "system" / "PROACTIVITY_INSTRUCTIONS.md")
        self.THOUGHTS_INSTRUCTIONS = self._load_file(self.system_dir / "system" / "THOUGHTS_INSTRUCTIONS.md")

    def _load_file(self, full_path: Path) -> str:
        try:
            with open(full_path, 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            system_logger.error(f"Ошибка: Файл промпта не найден -> {full_path}")
            return f"[Ошибка: Файл {full_path.name} не найден]"
        except Exception as e:
            system_logger.error(f"Ошибка при чтении {full_path}: {e}")
            return f"[Ошибка чтения файла: {full_path.name}]"

    def _get_l0_manifest_text(self) -> str:
        """Динамически собирает Markdown-справочник всех инструментов из кода"""
        if not l0_manifest:
            return "## L0 SKILL LIBRARY\n[Ошибка: Библиотека навыков пуста или не загружена.]"

        lines = ["## L0 SKILL LIBRARY (Библиотека навыков)"]

        # Группируем навыки по категориям (memory, telegram, system и т.д.)
        for category, skills in l0_manifest.items():
            lines.append(f"### [{category}]")
            for skill in skills:
                lines.append(skill)
            lines.append("") # Пустая строка для читаемости

        return "\n".join(lines).strip()

    def build_event_driven_prompt(self, dynamic_traits: str) -> str:
        PERSONALITY_PARAMETERS = f"## DYNAMIC PERSONALITY PARAMETERS (Твои приобретенные привычки и правила)\n{dynamic_traits}" if dynamic_traits else ""
        
        prompt_parts = [
            self.SOUL,
            PERSONALITY_PARAMETERS,
            self.SYSTEM_INSTRUCTIONS,
            self._get_l0_manifest_text(), 
            self.COMMUNICATION_STYLE,
            self.EXAMPLES_OF_STYLE
        ]
        return "\n\n".join(filter(None, prompt_parts))
    
    def build_proactivity_prompt(self, dynamic_traits: str) -> str:
        PERSONALITY_PARAMETERS = f"## DYNAMIC PERSONALITY PARAMETERS (Твои приобретенные привычки и правила)\n{dynamic_traits}" if dynamic_traits else ""
        
        prompt_parts = [
            self.SOUL,
            PERSONALITY_PARAMETERS,
            self.SYSTEM_INSTRUCTIONS,       
            self._get_l0_manifest_text(), 
            self.COMMUNICATION_STYLE,       
            self.PROACTIVITY_INSTRUCTIONS
        ]
        return "\n\n".join(filter(None, prompt_parts))
    
    def build_thoughts_prompt(self, dynamic_traits: str) -> str:
        PERSONALITY_PARAMETERS = f"## DYNAMIC PERSONALITY PARAMETERS (Твои приобретенные привычки и правила)\n{dynamic_traits}" if dynamic_traits else ""
        
        prompt_parts = [
            self.SOUL,
            PERSONALITY_PARAMETERS,
            self.SYSTEM_INSTRUCTIONS, 
            self._get_l0_manifest_text(), 
            self.THOUGHTS_INSTRUCTIONS
        ]
        return "\n\n".join(filter(None, prompt_parts))

prompt_manager = PromptManager()