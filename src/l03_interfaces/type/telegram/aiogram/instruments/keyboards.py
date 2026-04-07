from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

from src.l00_utils.managers.logger import system_logger


class AiogramKeyboards:
    """Сервис для сборки клавиатур (Inline и Reply) для бота Aiogram."""

    @staticmethod
    def build_inline_keyboard(
        buttons_data: list[list[dict]],
    ) -> InlineKeyboardMarkup | None:
        """
        Собирает Inline-клавиатуру (кнопки, прикрепленные под сообщением).

        Ожидает список рядов. Каждый ряд - список словарей.
        Пример:
        [[{"text": "Google", "url": "https://google.com"}, {"text": "Нажми меня", "callback_data": "btn_press"}]
        ]
        """
        if not buttons_data:
            return None

        inline_keyboard = []
        for row in buttons_data:
            btn_row = []
            for btn in row:
                text = str(btn.get("text", "Button"))
                url = btn.get("url")
                callback_data = btn.get("callback_data")

                if url:
                    # Если есть URL, это кнопка-ссылка (callback_data для нее не нужен)
                    btn_row.append(InlineKeyboardButton(text=text, url=url))
                else:
                    # По умолчанию ставим callback_data, даже если Агент забыл его передать
                    cb_data = str(callback_data or f"action_{text}")

                    # Ограничение Telegram - callback_data не может быть больше 64 байт
                    cb_bytes = cb_data.encode("utf-8")
                    if len(cb_bytes) > 64:
                        system_logger.warning(
                            f"[Telegram Bot] Агент сгенерировал слишком длинный callback_data ({len(cb_bytes)} байт). Обрезаем."
                        )
                        # Обрезаем так, чтобы точно влезло в 64 байта
                        cb_data = cb_bytes[:64].decode("utf-8", errors="ignore")

                    btn_row.append(InlineKeyboardButton(text=text, callback_data=cb_data))

            if btn_row:
                inline_keyboard.append(btn_row)

        return InlineKeyboardMarkup(inline_keyboard=inline_keyboard) if inline_keyboard else None

    @staticmethod
    def build_reply_keyboard(
        buttons_data: list[list[str]], resize: bool = True, one_time: bool = False
    ) -> ReplyKeyboardMarkup | None:
        """
        Собирает Reply-клавиатуру (кнопки вместо обычной клавиатуры ввода текста).

        Ожидает список рядов с текстом кнопок.
        Пример: [["Да", "Нет"], ["Главное меню"]]
        """
        if not buttons_data:
            return None

        reply_keyboard = []
        for row in buttons_data:
            # Создаем кнопки, отсеивая пустые строки
            btn_row = [KeyboardButton(text=str(text)) for text in row if text]
            if btn_row:
                reply_keyboard.append(btn_row)

        if not reply_keyboard:
            return None

        return (
            ReplyKeyboardMarkup(
                keyboard=reply_keyboard,
                resize_keyboard=resize,
                one_time_keyboard=one_time,
            )
            if reply_keyboard
            else None
        )

    @staticmethod
    def remove_reply_keyboard() -> ReplyKeyboardRemove:
        """Возвращает специальный объект, который заставляет Telegram скрыть Reply-клавиатуру у пользователя."""
        return ReplyKeyboardRemove()
