from aiogram.exceptions import TelegramAPIError

from src.l03_interfaces.type.telegram.aiogram.client import AiogramClient
from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.base import BaseInstrument
from src.l03_interfaces.type.telegram.aiogram.instruments.keyboards import (
    AiogramKeyboards,
)
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill


class AiogramCallbacks(BaseInstrument):
    """Сервис для обработки нажатий Inline-кнопок (Callback Queries) и динамического обновления UI."""

    def __init__(self, client: AiogramClient, keyboards: AiogramKeyboards):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.bot = client.bot
        self.keyboards = keyboards

    @skill()
    async def bot_answer_callback(
        self, callback_query_id: str, text: str = None, show_alert: bool = False
    ) -> ToolResult:
        """
        Завершает обработку нажатия кнопки (убирает "часики" загрузки на кнопке).
        Опционально может показать всплывающее уведомление (Toast) или Alert (модальное окно с кнопкой 'ОK').

        :param callback_query_id: ID коллбэка, полученный из события.
        :param text: Текст уведомления (до 200 символов).
        :param show_alert: True - модальное окно по центру экрана, False - уведомление-тост сверху.
        """
        try:
            if text and len(text) > 200:
                text = text[:197] + "..."

            await self.bot.answer_callback_query(
                callback_query_id=callback_query_id, text=text, show_alert=show_alert
            )

            if text:
                return ToolResult.ok(
                    msg=f"Уведомление '{text}' успешно показано, кнопка отжата.",
                    data={"callback_query_id": callback_query_id},
                )
            return ToolResult.ok(
                msg="Часы на кнопке успешно скрыты (без уведомления).",
                data={"callback_query_id": callback_query_id},
            )

        except TelegramAPIError as e:
            system_logger.error(
                f"[Telegram Bot] Ошибка ответа на callback {callback_query_id}: {e}"
            )
            return ToolResult.fail(msg=f"Ошибка при ответе на нажатие кнопки: {e}", error=str(e))

    @skill()
    async def bot_update_menu(
        self,
        chat_id: str | int,
        message_id: int,
        callback_query_id: str,
        new_text: str,
        new_buttons: list[list[dict]] = None,
        alert_text: str = None,
        show_alert: bool = False,
    ) -> ToolResult:
        """
        [Комбинированный метод]
        Используется ТОЛЬКО в ответ на событие нажатия кнопки (TELEGRAM_BOT_CALLBACK).
        Обновляет текст сообщения, меняет кнопки и ОДНОВРЕМЕННО завершает нажатие (убирает загрузку).
        Экономит шаги и токены агента.
        """
        try:
            # Сначала скрываем часики загрузки на кнопке (и показываем алерт, если нужно)
            if alert_text and len(alert_text) > 200:
                alert_text = alert_text[:197] + "..."

            await self.bot.answer_callback_query(
                callback_query_id=callback_query_id,
                text=alert_text,
                show_alert=show_alert,
            )

            # Обновляем само сообщение
            reply_markup = self.keyboards.build_inline_keyboard(new_buttons)

            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=new_text,
                reply_markup=reply_markup,
            )

            alert_status = f" с уведомлением '{alert_text}'" if alert_text else ""
            system_logger.info(
                f"[Telegram Bot] Меню (сообщение {message_id}) в чате {chat_id} обновлено."
            )
            return ToolResult.ok(
                msg=f"Меню (сообщение {message_id}) успешно обновлено{alert_status}.",
                data={"chat_id": chat_id, "message_id": message_id},
            )

        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка обновления меню {message_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при обновлении меню: {e}", error=str(e))
