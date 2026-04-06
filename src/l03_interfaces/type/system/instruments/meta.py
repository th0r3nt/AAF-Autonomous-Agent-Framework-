from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.system.client import SystemClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class SystemMeta(BaseInstrument):
    """Инструменты для управления собственными настройками агента в рантайме."""

    def __init__(self, client: SystemClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.state_manager = client.global_state.settings_state

    @skill()
    async def change_proactivity_interval(self, seconds: int) -> ToolResult:
        """
        Изменяет базовый интервал между циклами проактивности.
        Минимальное значение: 30 (чтобы не сжечь лимиты API).
        """
        if seconds < 30:
            return ToolResult.fail(
                msg="Ошибка: Интервал проактивности не может быть меньше 30 секунд."
            )

        success = self.state_manager.update("rhythms.proactivity_interval_sec", seconds)
        if success:
            system_logger.info(f"[System Meta] Интервал проактивности изменен на {seconds} сек.")
            return ToolResult.ok(msg=f"Интервал проактивности успешно изменен на {seconds} секунд.")

        return ToolResult.fail(msg="Ошибка изменения интервала проактивности.")

    @skill()
    async def change_consolidation_interval(self, seconds: int) -> ToolResult:
        """
        Изменяет интервал между циклами консолидации памяти (в секундах).
        Минимальное значение: 30.
        """
        if seconds < 30:
            return ToolResult.fail(
                msg="Ошибка: Интервал консолидации не может быть меньше 30 секунд."
            )

        success = self.state_manager.update("rhythms.consolidation_interval_sec", seconds)
        if success:
            system_logger.info(f"[System Meta] Интервал консолидации изменен на {seconds} сек.")
            return ToolResult.ok(msg=f"Интервал консолидации успешно изменен на {seconds} секунд.")

        return ToolResult.fail(msg="Ошибка изменения интервала консолидации.")

    @skill()
    async def toggle_proactivity(self, is_enabled: bool) -> ToolResult:
        """
        Включает или выключает циклы проактивности агента.
        Если False, агент будет реагировать только на входящие события (сообщения).
        """
        success = self.state_manager.update("system.flags.enable_proactivity", is_enabled)
        if success:
            status = "включена" if is_enabled else "выключена"
            system_logger.warning(f"[System Meta] Проактивность {status}.")
            return ToolResult.ok(msg=f"Проактивность успешно {status}.")

        return ToolResult.fail(msg="Ошибка переключения проактивности.")

    @skill()
    async def toggle_consolidation(self, is_enabled: bool) -> ToolResult:
        """
        Включает или выключает циклы автоматической консолидации (очистки) памяти.
        """
        success = self.state_manager.update("system.flags.enable_consolidation", is_enabled)
        if success:
            status = "включена" if is_enabled else "выключена"
            system_logger.warning(f"[System Meta] Консолидация памяти {status}.")
            return ToolResult.ok(msg=f"Консолидация памяти успешно {status}.")

        return ToolResult.fail(msg="Ошибка переключения консолидации.")

    @skill()
    async def change_llm_temperature(self, temp: float) -> ToolResult:
        """
        Изменяет температуру (креативность) LLM модели.
        Диапазон: от 0.0 (строгая логика) до 1.0 (креативность).
        """
        if not (0.0 <= temp <= 1.0):
            return ToolResult.fail(msg="Ошибка: Температура должна быть в диапазоне от 0.0 до 1.0.")

        success = self.state_manager.update("llm.temperature", temp)
        if success:
            system_logger.info(f"[System Meta] Температура LLM изменена на {temp}.")
            return ToolResult.ok(msg=f"Температура LLM успешно изменена на {temp}.")

        return ToolResult.fail(msg="Ошибка изменения температуры LLM.")

    @skill()
    async def switch_llm_model(self, model_name: str) -> ToolResult:
        """
        Переключает основную LLM модель (например, с gpt-4 на claude-3).
        """
        # Сначала проверим, поддерживается ли такая модель
        current_state = self.state_manager.get_state()
        available_models = current_state.get("llm", {}).get("available_models", [])

        if model_name not in available_models:
            models_str = ", ".join(available_models)
            return ToolResult.fail(
                msg=f"Ошибка: Модель '{model_name}' не поддерживается. Доступные варианты: {models_str}"
            )

        success = self.state_manager.update("llm.model_name", model_name)
        if success:
            system_logger.info(f"[System Meta] Основная модель переключена на {model_name}.")

            # Заглушка: тут нужно будет кидать ивент в EventBus, чтобы LLM Client
            # пересоздал свою сессию с новым ключом API, если поменялся провайдер.
            # await self.client.event_bus.publish(Events.SYSTEM_MODEL_SWITCHED, model=model_name)

            return ToolResult.ok(
                msg=f"Основная модель успешно переключена на '{model_name}'. Изменения применятся со следующего ReAct тика."
            )

        return ToolResult.fail(msg="Ошибка переключения модели LLM.")

    @skill()
    async def set_logging_level(self, level: str) -> ToolResult:
        """
        Изменяет уровень логирования системы в консоль и файл.
        Доступные значения: DEBUG, INFO, WARNING, ERROR.
        """
        level = level.upper()
        if level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            return ToolResult.fail(
                msg="Ошибка: Уровень должен быть DEBUG, INFO, WARNING или ERROR."
            )

        success = self.state_manager.update("system.logging_level", level)
        if success:
            system_logger.info(f"[System Meta] Уровень логирования изменен на {level}.")

            # Применяем уровень логирования динамически к текущему логгеру
            import logging

            numeric_level = getattr(logging, level)
            system_logger.setLevel(numeric_level)

            return ToolResult.ok(msg=f"Уровень системного логирования изменен на {level}.")

        return ToolResult.fail(msg="Ошибка изменения уровня логирования.")
