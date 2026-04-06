import asyncio
import os
from typing import List

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.event_bus import EventBus
from src.app import AgentSystem

# LLM Client
all_keys = [
    value.strip()
    for key, value in os.environ.items()
    if key.startswith("LLM_API_KEY_") and value.strip()
]
api_url = os.getenv("LLM_API_URL")

async def main(api_url: str, all_keys: List[str]) -> None:
    event_bus = EventBus()
    agent_system = AgentSystem(event_bus, api_url, all_keys)
    stop_event = asyncio.Event()

    try:
        await agent_system.startup()
        await stop_event.wait()
    except KeyboardInterrupt:
        system_logger.info("[System] Получен сигнал прерывания (Ctrl+C).")
    except Exception as e:
        system_logger.critical(f"[System] Критическое падение: {e}")
    finally:
        await agent_system.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main(api_url=api_url, all_keys=all_keys))
    except KeyboardInterrupt:
        pass