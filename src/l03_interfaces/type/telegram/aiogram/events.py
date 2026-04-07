from aiogram import Router
from aiogram.types import Message, CallbackQuery
import datetime

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.event.registry import Events

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.l03_interfaces.type.telegram.aiogram.client import AiogramClient

# Создаем роутер маршрутизатор, который будет обрабатывать все входящие обновления
bot_router = Router()


class AiogramEvents:
    def __init__(self, event_bus: EventBus, client: "AiogramClient"):
        self.event_bus = event_bus
        self.dp = client.dp
        self.client = client

    async def handle_bot_message(self, message: Message):
        """
        Ловит абсолютно все сообщения, отправленные боту:
        текст, команды (например, /start), фото, файлы.
        """
        user = message.from_user
        chat = message.chat

        # Игнорируем сообщения без отправителя (иногда бывает в системных уведомлениях)
        if not user:
            return

        username = user.username or str(user.id)
        chat_id = str(chat.id)
        message_id = message.message_id

        # Aiogram удобно парсит текст или подпись (caption) к медиафайлам
        raw_text = message.text or message.caption or ""

        # Определяем тип медиа для LLM
        media_prefix = ""
        if message.photo:
            media_prefix = "[Фотография] "
        elif message.document:
            media_prefix = f"[Документ: {message.document.file_name}] "
        elif message.voice:
            media_prefix = "[Голосовое сообщение] "
        elif message.video:
            media_prefix = "[Видео] "

        text = (media_prefix + raw_text).strip()

        chat_source = f"tg_bot_chat_({chat_id})"

        # Если бот добавлен в группу, проверяем, упомянули ли его
        is_private = chat.type == "private"
        is_mention = False

        if not is_private:
            # Если это команда для бота (начинается с /) или реплай на сообщение бота
            if text.startswith("/") or (
                message.reply_to_message
                and message.reply_to_message.from_user.id == message.bot.id
            ):
                is_mention = True

        time_str = datetime.datetime.now().strftime("%H:%M")
        log_str = f"[{time_str}] @{username} (Bot Chat): {text[:1000]}"
        self.client.recent_activity.append(log_str)

        try:
            # Отправляем в системную шину агента
            if is_private:
                system_logger.debug(f"[Telegram Bot] Получено ЛС от @{username}: {text[:50]}")
                await self.event_bus.publish(
                    Events.TELEGRAM_MESSAGE_INCOMING,
                    username=username,
                    chat_id=chat_id,
                    text=text,
                    chat_source=chat_source,
                    message_id=message_id,
                    via_bot=True,  # Метка для агента, чтобы он отвечал тоже через бота
                )
            elif is_mention:
                system_logger.debug(
                    f"[Telegram Bot] Бот упомянут в чате {chat.title} юзером @{username}"
                )
                await self.event_bus.publish(
                    Events.TELEGRAM_GROUP_MENTION,
                    chat_title=chat.title,
                    chat_id=chat_id,
                    username=username,
                    text=text,
                    chat_source=chat_source,
                    message_id=message_id,
                    via_bot=True,
                )
        except Exception as e:
            system_logger.error(f"[Telegram Bot] Ошибка маршрутизации сообщения: {e}")

    async def handle_bot_callback(self, callback: CallbackQuery):
        """
        Ловит нажатия на Inline-кнопки (под сообщениями бота).
        """
        user = callback.from_user
        username = user.username or str(user.id)

        # Извлекаем скрытую дату, зашитую в кнопку
        callback_data = callback.data

        message = callback.message
        chat_id = str(message.chat.id) if message else "Unknown"
        message_id = message.message_id if message else None

        system_logger.info(
            f"[Telegram Bot] Нажата кнопка '{callback_data}' от @{username} в чате {chat_id}"
        )

        time_str = datetime.datetime.now().strftime("%H:%M")
        log_str = f"[{time_str}] @{username} (Bot Callback): pressing '{callback_data}'"
        self.client.recent_activity.append(log_str)

        try:
            await self.event_bus.publish(
                Events.TELEGRAM_BOT_CALLBACK,
                username=username,
                chat_id=chat_id,
                callback_data=callback_data,
                message_id=message_id,
            )
        except Exception as e:
            system_logger.error(f"[Telegram Bot] Ошибка маршрутизации callback: {e}")
        finally:
            # Отвечаем телеграму, что мы обработали нажатие
            # Иначе часики на кнопке у пользователя будут бесконечно крутиться
            await callback.answer()

    def register_bot_events(self):
        """
        Функция для подключения роутера к главному диспетчеру.
        Регистрируем методы объекта напрямую, чтобы не ломался 'self'.
        """
        # Регистрируем обработчик сообщений
        bot_router.message.register(self.handle_bot_message)

        # Регистрируем обработчик инлайн-кнопок
        bot_router.callback_query.register(self.handle_bot_callback)

        self.dp.include_router(bot_router)
        system_logger.debug("[Telegram Bot] Обработчики событий успешно зарегистрированы.")
