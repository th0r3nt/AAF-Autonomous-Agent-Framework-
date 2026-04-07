import yaml
from typing import Any
from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings


class SettingsState:
    def __init__(self, config_path: str):  # Путь к settings.yaml
        self.config_path = config_path

    def get_state(self) -> dict:
        """
        Возвращает все текущие настройки системы.
        """
        # Pydantic v2 позволяет легко получить словарь всех данных
        full_dump = settings.model_dump(
            exclude={"interfaces"}
        )  # Исключаем "interfaces", так как за них отвечает отдельный класс InterfacesState
        return full_dump

    def update(self, setting_path: str, value: Any) -> bool:
        """
        Динамически обновляет любую настройку по пути.
        (например, "llm.temperature" или "system.flags.dump_llm_context").
        """
        keys = setting_path.split(".")

        # ====================================================
        # Обновление в Pydantic
        # ====================================================

        current_obj = settings

        # Спускаемся вглубь объектов Pydantic
        for key in keys[:-1]:
            if not hasattr(current_obj, key):
                system_logger.error(
                    f"[SettingsState] Ошибка: Секция '{key}' не найдена в настройках."
                )
                return False
            current_obj = getattr(current_obj, key)

        if not hasattr(current_obj, keys[-1]):
            system_logger.error(f"[SettingsState] Ошибка: Параметр '{keys[-1]}' не найден.")
            return False

        # Устанавливаем новое значение. Pydantic автоматически проверит типы!
        try:
            setattr(current_obj, keys[-1], value)
        except Exception as e:
            system_logger.error(
                f"[SettingsState] Ошибка валидации Pydantic при установке {setting_path}={value}: {e}"
            )
            return False

        # ====================================================
        # Дамп в settings.yaml
        # ====================================================

        try:
            # Выгружаем чистый словарь
            # by_alias=True возвращает ключи из YAML (например, max_react_steps вместо max_react_ticks)
            yaml_data = settings.model_dump(exclude={"interfaces"}, by_alias=True)

            # Перезаписываем файл целиком
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    yaml_data,
                    f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                )

            system_logger.info(
                f"[SettingsState] Настройка '{setting_path}' успешно изменена на {value}."
            )
            return True

        except Exception as e:
            system_logger.error(
                f"[SettingsState] Ошибка при дампе в файл {self.config_path}: {e}"
            )
            return False
