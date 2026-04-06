from telethon import TelegramClient
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.functions.contacts import (
    BlockRequest,
    UnblockRequest,
    GetBlockedRequest,
)
from telethon.tl.types import ChatBannedRights, ChannelParticipantsKicked

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.telegram.telethon.instruments._helpers import clean_peer_id
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class TelethonModeration(BaseInstrument):
    """Сервис для удобной работы с модерацией в Telegram."""

    def __init__(self, client: TelegramClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.client = client

    @skill()
    async def ban_user(
        self, chat_id: str | int, user_id: str | int, reason: str = "Ban"
    ) -> ToolResult:
        """
        Банит пользователя в группе/канале ИЛИ глобально.
        """
        user_id = clean_peer_id(user_id)
        try:
            try:
                user = await self.client.get_entity(user_id)
            except ValueError:
                return ToolResult.fail(
                    msg=f"Ошибка Telethon: Невозможно найти пользователя '{user_id}'. Передайте @username.",
                    error="UserNotFound",
                )

            if str(chat_id).lower() in ["global", "me", "личные", "pm"] or str(chat_id) == str(
                user_id
            ):
                await self.client(BlockRequest(id=user))
                return ToolResult.ok(
                    msg=f"Пользователь {user.id} успешно добавлен в глобальный ЧС.",
                    data={"user_id": user.id},
                )

            chat_id = clean_peer_id(chat_id)
            rights = ChatBannedRights(
                until_date=None,
                view_messages=True,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                embed_links=True,
            )
            await self.client(
                EditBannedRequest(channel=chat_id, participant=user, banned_rights=rights)
            )
            return ToolResult.ok(
                msg=f"Пользователь {user.id} забанен в чате {chat_id}. Причина: {reason}",
                data={"user_id": user.id, "chat_id": chat_id},
            )

        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка бана {user_id} в {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при бане пользователя: {e}", error=str(e))

    @skill()
    async def unban_user(self, chat_id: str | int, user_id: str | int) -> ToolResult:
        """
        Разбанивает пользователя.
        """
        user_id = clean_peer_id(user_id)
        try:
            user = await self.client.get_entity(user_id)
            if str(chat_id).lower() in ["global", "me", "личные", "pm"] or str(chat_id) == str(
                user_id
            ):
                await self.client(UnblockRequest(id=user))
                return ToolResult.ok(
                    msg=f"Пользователь {user.id} удален из глобального ЧС.",
                    data={"user_id": user.id},
                )

            chat_id = clean_peer_id(chat_id)
            rights = ChatBannedRights(until_date=None)
            await self.client(
                EditBannedRequest(channel=chat_id, participant=user, banned_rights=rights)
            )
            return ToolResult.ok(
                msg=f"Пользователь {user.id} разбанен в чате {chat_id}.",
                data={"user_id": user.id, "chat_id": chat_id},
            )

        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка разбана {user_id} в {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при разбане пользователя: {e}", error=str(e))

    @skill()
    async def get_banned_users(self, chat_id: str | int, limit: int = 50) -> ToolResult:
        """
        Возвращает список забаненных пользователей.
        """

        try:
            banned_list = []
            if str(chat_id).lower() in ["global", "me", "личные", "pm"]:
                result = await self.client(GetBlockedRequest(offset=0, limit=limit))
                for user in result.users:
                    name = getattr(user, "first_name", "Unknown")
                    username = (
                        f"@{user.username}" if getattr(user, "username", None) else "No_username"
                    )
                    banned_list.append(f"- ID: {user.id} | {name} ({username})")

                return (
                    ToolResult.ok(
                        msg="Глобальный ЧС:\n" + "\n".join(banned_list),
                        data=result.users,
                    )
                    if banned_list
                    else ToolResult.ok(msg="Глобальный ЧС пуст.", data=[])
                )

            chat_id = clean_peer_id(chat_id)
            async for user in self.client.iter_participants(
                chat_id, filter=ChannelParticipantsKicked, limit=limit
            ):
                name = getattr(user, "first_name", "Unknown")
                username = f"@{user.username}" if getattr(user, "username", None) else "No_username"
                banned_list.append(f"- ID: {user.id} | {name} ({username})")

            return (
                ToolResult.ok(
                    msg=f"Забаненные в чате {chat_id}:\n" + "\n".join(banned_list),
                    data=banned_list,
                )
                if banned_list
                else ToolResult.ok(msg="Список забаненных пуст.", data=[])
            )

        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка получения бан-листа {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при получении списка забаненных: {e}", error=str(e))
