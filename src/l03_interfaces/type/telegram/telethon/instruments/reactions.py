from telethon import TelegramClient
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.telegram.telethon.instruments._helpers import clean_peer_id
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class TelethonReactions(BaseInstrument):
    """Сервис для удобной работы с реакциями в Telegram."""

    def __init__(self, client: TelegramClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.client = client

    @skill()
    async def set_reaction(self, chat_id: str | int, message_id: int, emoticon: str) -> ToolResult:
        """
        Ставит реакцию на сообщение.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            await self.client(
                SendReactionRequest(
                    peer=chat_id,
                    msg_id=message_id,
                    reaction=[ReactionEmoji(emoticon=emoticon)],
                )
            )
            return ToolResult.ok(
                msg=f"Реакция '{emoticon}' успешно поставлена.",
                data={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "emoticon": emoticon,
                },
            )

        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка реакции на {message_id} в {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка установки реакции: {e}", error=str(e))
