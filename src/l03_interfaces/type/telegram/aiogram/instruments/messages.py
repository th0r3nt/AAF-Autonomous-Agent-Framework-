from aiogram.exceptions import TelegramAPIError

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.telegram.aiogram.client import AiogramClient
from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.base import BaseInstrument
from src.l03_interfaces.type.telegram.aiogram.instruments.keyboards import (
    AiogramKeyboards,
)
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill


class AiogramMessages(BaseInstrument):
    """Сервис для отправки и управления сообщениями через Bot API (Aiogram)."""

    def __init__(self, client: 'AiogramClient'):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.bot = client.bot

    @skill()
    async def bot_send_message(
        self,
        chat_id: str | int,
        text: str,
        reply_to_message_id: int = None,
        silent: bool = False,
        inline_buttons: list = None,
    ) -> ToolResult:
        """
        Отправляет текстовое сообщение (с поддержкой HTML-тегов и кнопок).
        """
        try:
            reply_markup = AiogramKeyboards.build_inline_keyboard(inline_buttons)

            msg = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_to_message_id=reply_to_message_id,
                disable_notification=silent,
                reply_markup=reply_markup,
            )
            return ToolResult.ok(
                msg=f"Сообщение успешно отправлено через бота. ID: {msg.message_id}",
                data=msg,
            )

        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка отправки сообщения в {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка отправки сообщения: {e}", error=str(e))

    @skill()
    async def bot_edit_message(
        self,
        chat_id: str | int,
        message_id: int,
        new_text: str,
        inline_buttons: list = None,
    ) -> ToolResult:
        """
        Редактирует уже отправленное сообщение (изменяет текст или кнопки).
        Очень полезно для создания динамических меню (когда агент обновляет статус задачи прямо в сообщении).
        """
        try:
            reply_markup = AiogramKeyboards.build_inline_keyboard(inline_buttons)

            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=new_text,
                reply_markup=reply_markup,
            )
            return ToolResult.ok(
                msg=f"Сообщение ID {message_id} успешно отредактировано.",
                data={"message_id": message_id},
            )

        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка редактирования сообщения {message_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка редактирования сообщения: {e}", error=str(e))

    @skill()
    async def bot_delete_message(self, chat_id: str | int, message_id: int) -> ToolResult:
        """
        Удаляет сообщение.
        """
        try:
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            return ToolResult.ok(
                msg=f"Сообщение ID {message_id} успешно удалено.",
                data={"message_id": message_id},
            )
        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка удаления сообщения {message_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка удаления сообщения: {e}", error=str(e))

    @skill()
    async def bot_copy_message(
        self, chat_id: str | int, from_chat_id: str | int, message_id: int
    ) -> ToolResult:
        """
        Копирует сообщение (без пометки 'Переслано от...').
        """
        try:
            msg_id = await self.bot.copy_message(
                chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id
            )
            return ToolResult.ok(
                msg=f"Сообщение успешно скопировано. Новый ID: {msg_id.message_id}",
                data=msg_id,
            )
        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка копирования сообщения {message_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при копировании сообщения: {e}", error=str(e))
