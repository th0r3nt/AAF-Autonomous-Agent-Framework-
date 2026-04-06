from telethon import TelegramClient, functions

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class TelethonGroups(BaseInstrument):
    """Сервис для удобной работы с группами в Telegram."""

    def __init__(self, client: TelegramClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.client = client

    @skill()
    async def create_supergroup(self, title: str, about: str = "") -> ToolResult:
        """
        Создает новую супергруппу
        """
        try:
            result = await self.client(
                functions.channels.CreateChannelRequest(title=title, about=about, megagroup=True)
            )
            return ToolResult.ok(
                msg=f"Группа '{title}' успешно создана. ID: {result.chats[0].id}",
                data=result.chats[0].id,
            )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка создания группы: {e}")
            return ToolResult.fail(msg=f"Ошибка при создании группы: {e}", error=str(e))
