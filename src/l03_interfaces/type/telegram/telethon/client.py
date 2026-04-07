from collections import deque
import os
import asyncio
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.errors import AuthKeyUnregisteredError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest

from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings

# Родители
from src.l03_interfaces.type.base import BaseClient

# Поллинг
from src.l03_interfaces.type.telegram.telethon.events import TelethonEvents

# Инструменты
from src.l03_interfaces.type.telegram.telethon.instruments.account import TelethonAccount
from src.l03_interfaces.type.telegram.telethon.instruments.channels import TelethonChannels
from src.l03_interfaces.type.telegram.telethon.instruments.chats import TelethonChats
from src.l03_interfaces.type.telegram.telethon.instruments.groups import TelethonGroups
from src.l03_interfaces.type.telegram.telethon.instruments.history import TelethonHistory
from src.l03_interfaces.type.telegram.telethon.instruments.media import TelethonMedia
from src.l03_interfaces.type.telegram.telethon.instruments.messages import TelethonMessages
from src.l03_interfaces.type.telegram.telethon.instruments.moderation import TelethonModeration
from src.l03_interfaces.type.telegram.telethon.instruments.polls import TelethonPolls
from src.l03_interfaces.type.telegram.telethon.instruments.reactions import TelethonReactions

load_dotenv()


class TelethonClient(BaseClient):
    """Асинхронный клиент (Userbot) для Telegram API на базе Telethon."""

    name = "userbot"  # Имя для маппинга

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        api_id_str = os.getenv("TELEGRAM_API_ID")
        self.api_id = int(api_id_str) if api_id_str else 0
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        self.session_name = "agent"

        self.is_ready = bool(self.api_id and self.api_hash)
        self.client: Optional[TelegramClient] = None

        # Храним последние 50 входящих/исходящих сообщений
        self.recent_activity = deque(maxlen=50)

        if not self.is_ready:
            system_logger.info("[Telethon] API ID или API Hash не заданы. Клиент отключен.")
            return

        resolved_session_dir = self._resolve_session_dir()
        resolved_session_dir.mkdir(parents=True, exist_ok=True)
        session_path = str(resolved_session_dir / self.session_name)

        self.client = TelegramClient(
            session_path,
            self.api_id,
            self.api_hash,
            system_version="AAF Agent",
            device_model="Agent Server",
        )

    def get_passive_context(self) -> dict:
        """Мгновенно отдает контекст из ОЗУ для Снабженца."""
        status = "🟢 ONLINE" if (self.client and self.client.is_connected()) else "🔴 OFFLINE"

        return {
            "name": self.name,
            "status": status,
            "recent_activity": list(self.recent_activity),
        }

    def register_instruments(self):
        if not self.is_ready:
            return
        TelethonAccount(self)
        TelethonChannels(self)
        TelethonChats(self)
        TelethonGroups(self)
        TelethonHistory(self)
        TelethonMedia(self)
        TelethonMessages(self)
        TelethonModeration(self)
        TelethonPolls(self)
        TelethonReactions(self)
        system_logger.debug("[Telethon] Инструменты юзербота успешно зарегистрированы.")

    async def start_background_polling(self) -> None:
        if not self.is_ready or not self.client:
            return

        events = TelethonEvents(self.event_bus, self.client, ignored_users=[])
        events.register_handlers()

        system_logger.info("[Telethon] Запуск фонового прослушивания событий.")
        await self._update_status_tag(is_online=True)
        asyncio.create_task(self.client.run_until_disconnected())

    async def check_connection(self) -> bool:
        if not self.is_ready or not self.client:
            return False
        try:
            if not self.client.is_connected():
                await self.client.connect()
            if not await self.client.is_user_authorized():
                system_logger.error(
                    "[Telethon] Сессия не авторизована. Требуется ручной логин (код из SMS)."
                )
                return False
            me = await self.client.get_me()
            username = f"@{me.username}" if me.username else me.first_name
            system_logger.info(
                f"[Telethon] Авторизация успешна. Подключен как (Userbot): {username}"
            )
            return True
        except AuthKeyUnregisteredError:
            system_logger.error("[Telethon] Сессия была завершена с другого устройства.")
            return False
        except Exception as e:
            system_logger.error(f"[Telethon] Ошибка проверки пульса: {e}")
            return False

    async def close(self):
        if self.client and self.client.is_connected():
            await self._update_status_tag(is_online=False)
            await self.client.disconnect()
            system_logger.info("[Telethon] Сессия закрыта.")

    # =======================================================================
    # СЛУЖЕБНЫЕ МЕТОДЫ
    # =======================================================================

    def _resolve_session_dir(self) -> Path:
        current_dir = Path(__file__).resolve()
        for parent in current_dir.parents:
            if (parent / "src").exists():
                return parent / "agent" / "data" / "telegram_sessions"
        return Path.cwd() / "agent" / "data" / "telegram_sessions"

    async def _update_status_tag(self, is_online: bool):
        tag_loc = settings.interfaces.telegram.userbot.status_tag.lower()
        if tag_loc not in ["name", "bio"] or not self.client or not self.client.is_connected():
            return
        try:
            me = await self.client.get_me()
            if not me:
                return
            tag = "[online]" if is_online else "[offline]"

            if tag_loc == "name":
                first = me.first_name or ""
                last = (
                    (me.last_name or "")
                    .replace(" [online]", "")
                    .replace(" [offline]", "")
                    .replace("[online]", "")
                    .replace("[offline]", "")
                    .strip()
                )
                new_last = f"{last} {tag}".strip() if last else tag
                await self.client(UpdateProfileRequest(first_name=first, last_name=new_last))

            elif tag_loc == "bio":
                full_user = await self.client(GetFullUserRequest(me))
                bio = (
                    (full_user.full_user.about or "")
                    .replace(" [online]", "")
                    .replace(" [offline]", "")
                    .replace("[online]", "")
                    .replace("[offline]", "")
                    .strip()
                )
                new_bio = f"{bio} {tag}".strip()
                if len(new_bio) > 70:
                    new_bio = bio[: 70 - len(tag) - 1].strip() + f" {tag}"
                await self.client(UpdateProfileRequest(about=new_bio))

        except Exception as e:
            system_logger.warning(f"[Telethon] Не удалось обновить статус-тег: {e}")
