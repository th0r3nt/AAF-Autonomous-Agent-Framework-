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