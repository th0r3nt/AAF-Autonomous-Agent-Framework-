from config.config_manager import config
from src.layer01_datastate.sql_db.management.dialogue import create_dialogue_entry

async def terminal_output(text: str) -> None:
    """Печатает в терминал любой текст"""
    print(text)

    await create_dialogue_entry(
        actor=config.identity.agent_name, 
        message=text, 
        source="terminal"
    )