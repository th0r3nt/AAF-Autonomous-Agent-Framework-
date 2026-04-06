from datetime import datetime
from telethon import TelegramClient

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.telegram.telethon.instruments._helpers import clean_peer_id
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class TelethonMessages(BaseInstrument):
    """Сервис для удобной работы с сообщениями в Telegram."""

    def __init__(self, client: TelegramClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.client = client

    async def _mark_as_read(self, chat_id: int | str):
        """
        Внутренний метод для пометки чата прочитанным.
        Вызывается после отправки сообщения, чтобы убрать уведомление о новом сообщении для бота.
        """
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
        """
        Отправляет сообщение и помечает чат прочитанным.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            msg = await self.client.send_message(
                chat_id, text, reply_to=topic_id, silent=silent, schedule=schedule_date
            )

            if not schedule_date:
                await self._mark_as_read(chat_id)
                return ToolResult.ok(msg=f"Сообщение успешно отправлено. ID: {msg.id}", data=msg)

            return ToolResult.ok(msg="Сообщение успешно добавлено в отложенные.", data=msg)

        except Exception as e:
            system_logger.error(f"[Telegram] Ошибка отправки сообщения в {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка отправки: {e}", error=str(e))

    @skill()
    async def reply_to_message(self, chat_id: str | int, message_id: int, text: str) -> ToolResult:
        """
        Отвечает на конкретное сообщение и помечает чат прочитанным.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            msg = await self.client.send_message(chat_id, text, reply_to=message_id)
            await self._mark_as_read(chat_id)
            return ToolResult.ok(msg="Ответ успешно отправлен.", data=msg)

        except Exception as e:
            system_logger.error(
                f"[Telegram] Ошибка ответа на сообщение {message_id} в {chat_id}: {e}"
            )
            return ToolResult.fail(msg=f"Ошибка ответа: {e}", error=str(e))

    @skill()
    async def delete_message(self, chat_id: str | int, message_id: int) -> ToolResult:
        """
        Удаляет сообщение.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            await self.client.delete_messages(chat_id, [message_id])
            return ToolResult.ok(
                msg=f"Сообщение ID {message_id} успешно удалено.",
                data={"message_id": message_id},
            )

        except Exception as e:
            system_logger.error(f"[Telegram] Ошибка удаления сообщения {message_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при удалении сообщения: {e}", error=str(e))

    @skill()
    async def forward_message(
        self, from_chat: str | int, message_id: int, to_chat: str | int
    ) -> ToolResult:
        """
        Пересылает сообщение из одного чата в другой.
        """
        from_chat = clean_peer_id(from_chat)
        to_chat = clean_peer_id(to_chat)
        try:
            msg = await self.client.forward_messages(
                to_chat, messages=message_id, from_peer=from_chat
            )
            return ToolResult.ok(
                msg=f"Сообщение успешно переслано. Новый ID в целевом чате: {msg.id}",
                data=msg,
            )

        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка пересылки сообщения {message_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при пересылке: {e}", error=str(e))

    @skill()
    async def edit_message(self, chat_id: str | int, message_id: int, new_text: str) -> ToolResult:
        """
        Редактирует сообщение/пост.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            msg = await self.client.edit_message(chat_id, message_id, new_text)
            return ToolResult.ok(
                msg=f"Сообщение ID {message_id} успешно отредактировано.", data=msg
            )
        except Exception as e:
            system_logger.error(
                f"[Telegram Tools] Ошибка редактирования сообщения {message_id}: {e}"
            )
            return ToolResult.fail(msg=f"Ошибка редактирования: {e}", error=str(e))

    @skill()
    async def pin_message(self, chat_id: str | int, message_id: int) -> ToolResult:
        """
        Закрепляет сообщение в чате/канале.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            await self.client.pin_message(chat_id, message_id, notify=True)
            return ToolResult.ok(
                msg=f"Сообщение ID {message_id} успешно закреплено.",
                data={"message_id": message_id},
            )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка закрепления сообщения {message_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка закрепления: {e}", error=str(e))
