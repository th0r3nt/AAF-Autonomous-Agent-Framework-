from collections import deque
import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.managers.logger import system_logger

# Родители
from src.l03_interfaces.type.base import BaseClient

# Поллинг
from src.l03_interfaces.type.telegram.aiogram.events import AiogramEvents

# Инструменты
from src.l03_interfaces.type.telegram.aiogram.instruments.keyboards import AiogramKeyboards
from src.l03_interfaces.type.telegram.aiogram.instruments.bot_manage import AiogramBotManage
from src.l03_interfaces.type.telegram.aiogram.instruments.callbacks import AiogramCallbacks
from src.l03_interfaces.type.telegram.aiogram.instruments.messages import AiogramMessages
from src.l03_interfaces.type.telegram.aiogram.instruments.moderation import AiogramModeration

load_dotenv()


class AiogramClient(BaseClient):
    """Асинхронный клиент для Telegram Bot API на базе Aiogram 3."""

    name = "telegram bot"

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.is_ready = bool(self.token)

        if not self.is_ready:
            system_logger.warning("[Telegram Bot] Токен не найден. Интерфейс отключен.")
            self.bot = None
            self.dp = None
            return

        self.bot = Bot(
            token=self.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self.dp = Dispatcher()

        self.recent_activity = deque(maxlen=50)

    def register_instruments(self):
        if not self.is_ready:
            return
        keyboards = AiogramKeyboards()
        AiogramBotManage(self)
        AiogramCallbacks(self, keyboards)
        AiogramMessages(self)
        AiogramModeration(self)
        system_logger.debug("[Telegram Bot] Инструменты бота успешно зарегистрированы.")

    async def start_background_polling(self) -> None:
        if not self.is_ready:
            return
        try:
            # Регистрируем роутеры перед стартом
            events = AiogramEvents(event_bus=self.event_bus, client=self)
            events.register_bot_events()

            system_logger.info("[Telegram Bot] Запуск polling-цикла.")
            await self.bot.delete_webhook(drop_pending_updates=True)
            # Aiogram polling блокирует поток, поэтому запускаем как таску
            asyncio.create_task(self.dp.start_polling(self.bot))

        except Exception as e:
            system_logger.error(f"[Telegram Bot] Критическая ошибка polling-цикла: {e}")

    def get_passive_context(self) -> dict:
        status = "🟢 ONLINE" if self.is_ready else "🔴 OFFLINE"
        return {
            "name": "telegram_bot",
            "status": status,
            "recent_activity": list(self.recent_activity)
        }

    async def check_connection(self) -> bool:
        if not self.is_ready:
            return False
        try:
            me = await self.bot.get_me()
            system_logger.info(
                f"[Telegram Bot] Авторизация успешна. UI Агента подключен как: @{me.username}"
            )
            return True
        except Exception as e:
            system_logger.error(f"[Telegram Bot] Ошибка авторизации: {e}")
            self.is_ready = False
            return False

    async def close(self):
        if self.bot:
            await self.bot.session.close()
            system_logger.info("[Telegram Bot] Сессия закрыта.")
