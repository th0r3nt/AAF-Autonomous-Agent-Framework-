import os
import json
from pathlib import Path
from src.layer00_utils.logger import system_logger
from config.config_manager import config

class PromptManager:
    """Хранилище и сборка общих промптов из .md файлов"""
    def __init__(self):
        # Определяем абсолютный путь к папке prompt/ (здесь лежат системные инструкции)
        self.system_dir = Path(__file__).resolve().parent
        
        # Поднимаемся на 4 уровня вверх до корня проекта и идем в config/personality
        self.project_root = self.system_dir.parents[3]
        self.personality_dir = self.project_root / "config" / "personality"
        self.workspace_dir = self.project_root / "workspace"

        # Загружаем личность (из пользовательского конфига)
        self.SOUL = self._load_file(self.personality_dir / "SOUL.md")
        self.COMMUNICATION_STYLE = self._load_file(self.personality_dir / "COMMUNICATION_STYLE.md")
        self.EXAMPLES_OF_STYLE = self._load_file(self.personality_dir / "EXAMPLES_OF_STYLE.md")

        # Загружаем системные инструкции (из исходного кода)
        self.SYSTEM_INSTRUCTIONS = self._load_file(self.system_dir / "system" / "SYSTEM_INSTRUCTIONS.md")
        self.PROACTIVITY_INSTRUCTIONS = self._load_file(self.system_dir / "system" / "PROACTIVITY_INSTRUCTIONS.md")
        self.THOUGHTS_INSTRUCTIONS = self._load_file(self.system_dir / "system" / "THOUGHTS_INSTRUCTIONS.md")

        # Протокол пробуждения при первом запуске
        self.awakening_file = self.system_dir / "system" / "AWAKENING.md"
        self.awakening_state_file = self.workspace_dir / "awakening_state.json"
        
        if self.awakening_file.exists():
            self.AWAKENING = self._load_file(self.awakening_file)
        else:
            self.AWAKENING = None

    def _load_file(self, full_path: Path) -> str:
        """Читает .md файл как текст"""
        try:
            with open(full_path, 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            system_logger.error(f"Ошибка: Файл промпта не найден -> {full_path}")
            return f"[Ошибка: Файл {full_path.name} не найден]"
        except Exception as e:
            system_logger.error(f"Ошибка при чтении {full_path}: {e}")
            return f"[Ошибка чтения файла: {full_path.name}]"

    def _process_awakening(self) -> str:
        """Обрабатывает логику протокола пробуждения (счетчик и удаление)"""
        if not self.AWAKENING:
            return ""

        try:
            # Читаем или создаем стейт
            if self.awakening_state_file.exists():
                with open(self.awakening_state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
            else:
                self.workspace_dir.mkdir(parents=True, exist_ok=True)
                state = {"requests_left": 30}

            state["requests_left"] -= 1

            # Форматируем текст, подставляя имена из конфига
            formatted_text = self.AWAKENING.format(
                agent_name=config.identity.agent_name,
                admin_name=config.identity.admin_name,
                admin_tg_id=config.identity.admin_tg_id
            )

            if state["requests_left"] <= 0:
                # Уничтожаем следы (благодаря Docker volumes, файлы удалятся и на хосте)
                if self.awakening_file.exists():
                    os.remove(self.awakening_file)
                if self.awakening_state_file.exists():
                    os.remove(self.awakening_state_file)
                
                self.AWAKENING = None
                system_logger.info("[System] Процесс адаптации завершен. Протокол Awakening удален.")
            else:
                # Сохраняем обновленный стейт
                with open(self.awakening_state_file, 'w', encoding='utf-8') as f:
                    json.dump(state, f)

            return formatted_text

        except Exception as e:
            system_logger.error(f"Ошибка при обработке Awakening Protocol: {e}")
            return ""

    def build_event_driven_prompt(self, dynamic_traits: str) -> str:
        """Для обычного общения и прямого ответа на события (Event-Driven)"""
        awakening_block = self._process_awakening()
        PERSONALITY_PARAMETERS = f"## DYNAMIC PERSONALITY PARAMETERS (Твои приобретенные привычки и правила)\n{dynamic_traits}" if dynamic_traits else ""
        
        prompt_parts = [
            awakening_block,
            self.SOUL,
            PERSONALITY_PARAMETERS,
            self.SYSTEM_INSTRUCTIONS,
            self.COMMUNICATION_STYLE,
            self.EXAMPLES_OF_STYLE
        ]
        return "\n\n".join(filter(None, prompt_parts))
    
    def build_proactivity_prompt(self, dynamic_traits: str) -> str:
        """Для фоновой активности, выполнения задач и инициативы"""
        awakening_block = self._process_awakening()
        PERSONALITY_PARAMETERS = f"## DYNAMIC PERSONALITY PARAMETERS (Твои приобретенные привычки и правила)\n{dynamic_traits}" if dynamic_traits else ""
        
        prompt_parts = [
            awakening_block,
            self.SOUL,
            PERSONALITY_PARAMETERS,
            self.SYSTEM_INSTRUCTIONS,       
            self.COMMUNICATION_STYLE,       
            self.PROACTIVITY_INSTRUCTIONS
        ]
        return "\n\n".join(filter(None, prompt_parts))
    
    def build_thoughts_prompt(self, dynamic_traits: str) -> str:
        """Для рефлексии, анализа и заполнения векторных баз"""
        awakening_block = self._process_awakening()
        PERSONALITY_PARAMETERS = f"## DYNAMIC PERSONALITY PARAMETERS (Твои приобретенные привычки и правила)\n{dynamic_traits}" if dynamic_traits else ""
        
        prompt_parts = [
            awakening_block,
            self.SOUL,
            PERSONALITY_PARAMETERS,
            self.SYSTEM_INSTRUCTIONS, 
            self.THOUGHTS_INSTRUCTIONS
        ]
        return "\n\n".join(filter(None, prompt_parts))

prompt_manager = PromptManager()

if __name__ == "__main__":
    print(prompt_manager.build_proactivity_prompt(""))