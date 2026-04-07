import yaml
from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings


class InterfacesState:
    def __init__(self, interfaces_path: str):  # Путь к interfaces.yaml
        self.interfaces_path = interfaces_path

        # При старте класс проходится по agent/config/interfaces.yaml и строит текущий статус интерфейсов
        self.interfaces = {
            # "interface_name": {"enabled": True/False, "agent_account": True/False, "runtime_status": True/False},
        }

        # Где физически лежит интерфейс в yaml конфиге (например: {"github": ["api", "github"]})
        self._yaml_paths = {}

        # Автоматически собираем плоский словарь интерфейсов из конфига
        raw_interfaces = settings.interfaces.model_dump()
        self._flatten_config(raw_interfaces, [])

    def _flatten_config(self, data: dict, current_path: list):
        """
        Ищет все существующие интерфейсы.
        Рекурсивно обходит конфиг.
        Если находит ключ 'enabled' -> значит, это интерфейс -> забирает в плоский список.
        """
        if isinstance(data, dict):
            if "enabled" in data:
                interface_name = current_path[-1]  # Имя узла (github, browser, userbot)

                # Добавляем в реестр интерфейсов
                self.interfaces[interface_name] = {
                    "enabled": data["enabled"],
                    "agent_account": data.get("agent_account", False),
                    "runtime_status": False,  # При старте ОС все интерфейсы по умолчанию выключены/мертвы
                }
                # Запоминаем путь, чтобы потом уметь сохранять изменения в YAML
                self._yaml_paths[interface_name] = current_path

            else:
                # Если 'enabled' нет, копаем глубже (например, заходим в 'api' или 'web')
                for key, value in data.items():
                    self._flatten_config(value, current_path + [key])

    def get_state(self) -> dict:
        """Возвращает плоский словарь всех интерфейсов для агента."""
        return self.interfaces

    def set_runtime(self, interface: str, is_alive: bool):
        """Обновляет текущий статус интерфейса (живой/не живой)."""
        if interface in self.interfaces:
            self.interfaces[interface]["runtime_status"] = is_alive

    def update(self, interface: str, enabled: bool) -> bool:
        """
        Меняет настройку 'enabled' (включает/выключает интерфейс).
        Изменяет в памяти агента, Pydantic и физическом YAML файле.
        """
        if interface not in self.interfaces:
            system_logger.error(
                f"[Interfaces] Попытка обновить неизвестный интерфейс: {interface}"
            )
            return False

        try:
            # Обновляем локальный плоский словарь для контекста LLM
            self.interfaces[interface]["enabled"] = enabled

            # Обновляем Pydantic-модель в оперативной памяти
            path_keys = self._yaml_paths[interface]
            current_obj = settings.interfaces
            
            for key in path_keys:
                current_obj = getattr(current_obj, key)
            current_obj.enabled = enabled

            # Дамп в interfaces.yaml
            # Берем только секцию интерфейсов, уважаем алиасы
            yaml_data = settings.interfaces.model_dump(by_alias=True)

            with open(self.interfaces_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    yaml_data,
                    f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                )

            action = "включен" if enabled else "выключен"
            system_logger.info(f"[Interfaces] Интерфейс '{interface}' {action}.")
            return True

        except Exception as e:
            system_logger.error(f"[Interfaces] Ошибка при обновлении '{interface}': {e}")
            return False