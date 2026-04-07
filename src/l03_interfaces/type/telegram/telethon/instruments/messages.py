from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.l03_interfaces.type.telegram.telethon.client import TelethonClient

from src.l03_interfaces.type.telegram.telethon.instruments._helpers import clean_peer_id
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument
from src.l04_agency.skills.registry import skill


class TelethonMessages(BaseInstrument):
    """Сервис для удобной работы с сообщениями в Telegram."""

    def __init__(self, client: "TelethonClient"):
        super().__init__()
        self.agent_client = client  # Для записи логов в recent_activity
        self.client = client.client  # Оригинальный Telethon клиент для API запросов

    async def _mark_as_read(self, chat_id: int | str):
        await self.client.send_read_acknowledge(chat_id)
        await self.client.send_read_acknowledge(chat_id, clear_mentions=True)

    @skill()
    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        topic_id: int = None,
        silent: bool = False,
        schedule_date: datetime = None,
    ) -> ToolResult:
        chat_id = clean_peer_id(chat_id)
        try:
            msg = await self.client.send_message(
                chat_id, text, reply_to=topic_id, silent=silent, schedule=schedule_date
            )

            # Логгирование
            time_str = datetime.now().strftime("%H:%M")
            clean_text = text.replace("\n", " ")
            self.agent_client.recent_activity.append(
                f"[{time_str}] Agent sent to {chat_id}: {clean_text[:300]}..."
            )

            if not schedule_date:
                await self._mark_as_read(chat_id)
                return ToolResult.ok(
                    msg=f"Сообщение успешно отправлено. ID: {msg.id}", data=msg
                )
            return ToolResult.ok(msg="Сообщение успешно добавлено в отложенные.", data=msg)
        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка отправки: {e}", error=str(e))

    @skill()
    async def reply_to_message(
        self, chat_id: str | int, message_id: int, text: str
    ) -> ToolResult:
        chat_id = clean_peer_id(chat_id)
        try:
            msg = await self.client.send_message(chat_id, text, reply_to=message_id)
            await self._mark_as_read(chat_id)

            # Логгирование
            time_str = datetime.now().strftime("%H:%M")
            clean_text = text.replace("\n", " ")
            self.agent_client.recent_activity.append(
                f"[{time_str}] Agent replied to msg {message_id}: {clean_text[:300]}..."
            )

            return ToolResult.ok(msg="Ответ успешно отправлен.", data=msg)
        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка ответа: {e}", error=str(e))

    @skill()
    async def delete_message(self, chat_id: str | int, message_id: int) -> ToolResult:
        chat_id = clean_peer_id(chat_id)
        try:
            await self.client.delete_messages(chat_id, [message_id])

            # Логгирование
            time_str = datetime.now().strftime("%H:%M")
            self.agent_client.recent_activity.append(
                f"[{time_str}] Agent deleted msg {message_id}"
            )

            return ToolResult.ok(msg=f"Сообщение ID {message_id} успешно удалено.")
        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка при удалении сообщения: {e}", error=str(e))

    @skill()
    async def forward_message(
        self, from_chat: str | int, message_id: int, to_chat: str | int
    ) -> ToolResult:
        from_chat = clean_peer_id(from_chat)
        to_chat = clean_peer_id(to_chat)
        try:
            msg = await self.client.forward_messages(
                to_chat, messages=message_id, from_peer=from_chat
            )
            time_str = datetime.now().strftime("%H:%M")
            self.agent_client.recent_activity.append(
                f"[{time_str}] Agent forwarded msg {message_id} to {to_chat}"
            )
            return ToolResult.ok(
                msg=f"Сообщение успешно переслано. Новый ID: {msg.id}", data=msg
            )
        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка при пересылке: {e}", error=str(e))

    @skill()
    async def edit_message(
        self, chat_id: str | int, message_id: int, new_text: str
    ) -> ToolResult:
        chat_id = clean_peer_id(chat_id)
        try:
            msg = await self.client.edit_message(chat_id, message_id, new_text)

            time_str = datetime.now().strftime("%H:%M")
            clean_text = new_text.replace("\n", " ")
            self.agent_client.recent_activity.append(
                f"[{time_str}] Agent edited msg {message_id}: {clean_text[:100]}..."
            )

            return ToolResult.ok(
                msg=f"Сообщение ID {message_id} успешно отредактировано.", data=msg
            )
        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка редактирования: {e}", error=str(e))

    @skill()
    async def pin_message(self, chat_id: str | int, message_id: int) -> ToolResult:
        chat_id = clean_peer_id(chat_id)
        try:
            await self.client.pin_message(chat_id, message_id, notify=True)
            time_str = datetime.now().strftime("%H:%M")
            self.agent_client.recent_activity.append(
                f"[{time_str}] Agent pinned msg {message_id}"
            )
            return ToolResult.ok(msg=f"Сообщение ID {message_id} успешно закреплено.")
        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка закрепления: {e}", error=str(e))
