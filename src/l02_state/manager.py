import yaml

from src.l02_state.system.agency import AgencyState
from src.l02_state.system.yaml.interfaces import InterfacesState
from src.l02_state.system.yaml.settings import SettingsState


class GlobalState:
    def __init__(
        self,
        agency_state: AgencyState,
        interfaces_state: InterfacesState,
        settings_state: SettingsState,
    ):
        self.agency_state = agency_state
        self.interfaces_state = interfaces_state
        self.settings_state = settings_state

    def get_state(self, state_name: str):
        if state_name == "agency":
            return self.agency_state.get_state()

        elif state_name == "interfaces":
            return self.interfaces_state.get_state()

        elif state_name == "settings":
            return self.settings_state.get_state()

        elif state_name == "all":
            return {
                "agency": self.agency_state.get_state(),
                "interfaces": self.interfaces_state.get_state(),
                "settings": self.settings_state.get_state(),
            }

        else:
            raise ValueError(f"Unknown state name: {state_name}")

    # =====================================================================
    # ФОРМАТИРОВАНИЕ ДЛЯ LLM (MARKDOWN)
    # =====================================================================

    def _format_subagents_group(self, group_dict: dict, empty_msg: str) -> str:
        """Форматирует группу субагентов (Daemons/Workers) в список."""
        if not group_dict:
            return f"  - {empty_msg}"

        return "\n".join(
            f"  - `{name}` | Status: {info['status']} | Task: {info['task']}"
            for name, info in group_dict.items()
        )

    def _format_interfaces(self, interfaces: dict) -> str:
        """Форматирует интерфейсы, расставляя статусы и индикаторы."""
        lines = []
        for name, info in sorted(interfaces.items()):
            if not info.get("enabled"):
                status = "⚪️ DISABLED"
            else:
                status = "🟢 ONLINE" if info.get("runtime_status") else "🔴 OFFLINE"

            lines.append(f"- {name.upper()}: {status}")

        return "\n".join(lines) or "- Нет доступных интерфейсов."

    def get_markdown(self, settings: bool) -> str:
        """
        Собирает слепок системы и возвращает чистый Markdown для системного промпта LLM.
        """
        agency = self.agency_state.get_state()
        main_agent = agency["main_agent"]
        subagents = agency["subagents"]

        # 1. Форматируем списки через хэлперы
        daemons_str = self._format_subagents_group(
            subagents.get("daemons"), "Нет активных Daemons."
        )
        workers_str = self._format_subagents_group(
            subagents.get("workers"), "Нет активных Workers."
        )
        interfaces_str = self._format_interfaces(self.interfaces_state.get_state())

        # 2. Сериализуем настройки в YAML
        settings_yaml = yaml.dump(
            self.settings_state.get_state(), allow_unicode=True, sort_keys=False
        ).strip()

        # 3. Собираем итоговый шаблон
        return f"""
## [SYSTEM STATE]

[MAIN AGENT]
- Status: `{main_agent.get('status', 'unknown')}`
- Current Cycle: `{main_agent.get('current_cycle', 'unknown')}`

[SUBAGENTS]
Daemons:
{daemons_str}
Workers:
{workers_str}

[SETTINGS]
```yaml
{settings_yaml if settings else ""}
```

[INTERFACES]
{interfaces_str}
"""
