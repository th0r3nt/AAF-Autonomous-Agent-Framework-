from telethon import TelegramClient
from telethon import functions
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    EditTitleRequest,
    EditAdminRequest,
    UpdateUsernameRequest,
)
from telethon.tl.functions.messages import EditChatAboutRequest
from telethon.tl.types import ChannelParticipantsRecent, ChatAdminRights

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.telegram.telethon.instruments._helpers import clean_peer_id
from src.l03_interfaces.type.base import BaseInstrument
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill


class TelethonChannels(BaseInstrument):
    """Сервис для удобной работы с каналами в Telegram."""

    def __init__(self, client: TelegramClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.client = client

    @skill()
    async def comment_on_post(
        self, channel_id: str | int, message_id: int, text: str
    ) -> ToolResult:
        """
        Оставляет комментарий под постом в канале.
        """
        channel_id = clean_peer_id(channel_id)
        try:
            msg = await self.client.send_message(channel_id, text, comment_to=message_id)
            return ToolResult.ok(msg=f"Комментарий успешно оставлен. ID: {msg.id}", data=msg)
        except Exception as e:
            system_logger.error(
                f"[Telegram Tools] Ошибка комментария к {message_id} в {channel_id}: {e}"
            )
            return ToolResult.fail(msg=f"Ошибка при отправке комментария: {e}", error=str(e))

    @skill()
    async def search_channels(self, query: str, limit: int = 5) -> ToolResult:
        """
        Ищет публичные каналы и группы в глобальном поиске Telegram
        """
        try:
            result = await self.client(functions.contacts.SearchRequest(q=query, limit=limit))
            chats = []
            for chat in result.chats:
                chat_type = "Канал" if getattr(chat, "broadcast", False) else "Группа"
                username = (
                    f"@{chat.username}" if getattr(chat, "username", None) else "Без_юзернейма"
                )
                title = getattr(chat, "title", "Без названия")
                about = "Нет описания"
                participants_count = "Неизвестно"

                try:
                    full_chat = await self.client(
                        functions.channels.GetFullChannelRequest(channel=chat)
                    )
                    about = full_chat.full_chat.about or "Нет описания"
                    participants_count = full_chat.full_chat.participants_count or "Неизвестно"
                except Exception:
                    pass

                if len(about) > 150:
                    about = about[:147] + "..."

                chats.append(
                    f"[{chat_type}] {title} ({username}) | ID: {chat.id}\n   Подписчиков: {participants_count} | Описание: {about}"
                )

            return (
                ToolResult.ok(msg="\n\n".join(chats), data=result.chats)
                if chats
                else ToolResult.fail(msg=f"По запросу '{query}' ничего не найдено.")
            )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка поиска каналов: {e}")
            return ToolResult.fail(msg=f"Ошибка при поиске: {e}", error=str(e))

    @skill()
    async def join_channel(self, link_or_username: str) -> ToolResult:
        """
        Вступает в канал или группу.
        """
        try:
            target = link_or_username.strip()
            if "t.me/+" in target or "t.me/joinchat/" in target:
                if "t.me/+" in target:
                    invite_hash = target.split("t.me/+")[1].split("/")[0].split("?")[0]
                else:
                    invite_hash = target.split("t.me/joinchat/")[1].split("/")[0].split("?")[0]
                await self.client(functions.messages.ImportChatInviteRequest(invite_hash))
                return ToolResult.ok(msg="Успешное присоединение по приватной ссылке.")
            else:
                await self.client(functions.channels.JoinChannelRequest(channel=target))
                return ToolResult.ok(msg=f"Успешное присоединение к {target}.")
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка вступления в {link_or_username}: {e}")
            return ToolResult.fail(msg=f"Ошибка при вступлении в канал: {e}", error=str(e))

    @skill()
    async def create_channel_post(self, channel_id: str | int, text: str) -> ToolResult:
        """
        Отправляет новый пост в Telegram-канал.
        """
        channel_id = clean_peer_id(channel_id)
        try:
            msg = await self.client.send_message(channel_id, text)
            return ToolResult.ok(
                msg=f"Пост успешно опубликован в канале. ID поста: {msg.id}", data=msg
            )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка публикации в канал {channel_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка публикации поста: {e}", error=str(e))

    @skill()
    async def get_channel_subscribers(self, chat_id: str | int, limit: int = 50) -> ToolResult:
        """
        Получает список подписчиков канала или группы.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            subscribers = []
            async for user in self.client.iter_participants(
                chat_id, limit=limit, filter=ChannelParticipantsRecent
            ):
                name = getattr(user, "first_name", "Unknown")
                username = (
                    f"@{user.username}" if getattr(user, "username", None) else "без_юзернейма"
                )
                subscribers.append(f"- ID: {user.id} | {name} ({username})")
            return (
                ToolResult.ok(
                    msg="Список подписчиков:\n" + "\n".join(subscribers),
                    data=subscribers,
                )
                if subscribers
                else ToolResult.fail(msg="Список пуст или нет прав.")
            )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка получения подписчиков {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при получении подписчиков: {e}", error=str(e))

    @skill()
    async def create_channel(self, title: str, about: str = "") -> ToolResult:
        """
        Создает новый Telegram-канал.
        """
        try:
            result = await self.client(
                CreateChannelRequest(title=title, about=about, megagroup=False)
            )
            channel_id = result.chats[0].id
            return ToolResult.ok(
                msg=f"Канал '{title}' успешно создан. ID: {channel_id}.",
                data=result.chats[0],
            )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка создания канала: {e}")
            return ToolResult.fail(msg=f"Ошибка при создании канала: {e}", error=str(e))

    @skill()
    async def update_channel_info(
        self, channel_id: str | int, new_title: str = None, new_about: str = None
    ) -> ToolResult:
        """
        Изменяет название и/или описание канала.
        """
        channel_id = clean_peer_id(channel_id)
        try:
            entity = await self.client.get_input_entity(channel_id)
            res_msg = []
            if new_title:
                await self.client(EditTitleRequest(channel=entity, title=new_title))
                res_msg.append("Название обновлено.")
            if new_about:
                await self.client(EditChatAboutRequest(peer=entity, about=new_about))
                res_msg.append("Описание обновлено.")
            return (
                ToolResult.ok(msg=" ".join(res_msg))
                if res_msg
                else ToolResult.fail(msg="Нет данных для обновления.")
            )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка обновления канала {channel_id}: {e}")
            return ToolResult.fail(
                msg=f"Ошибка при обновлении информации канала: {e}", error=str(e)
            )

    @skill()
    async def set_channel_username(self, channel_id: str | int, username: str) -> ToolResult:
        """
        Делает канал публичным.
        """
        channel_id = clean_peer_id(channel_id)
        try:
            entity = await self.client.get_input_entity(channel_id)
            clean_username = username.replace("@", "")
            await self.client(UpdateUsernameRequest(channel=entity, username=clean_username))
            return ToolResult.ok(msg=f"Канал стал публичным. Ссылка: t.me/{clean_username}")
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка установки юзернейма {channel_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка установки юзернейма: {e}", error=str(e))

    @skill()
    async def promote_to_admin(self, channel_id: str | int, user_id: str | int) -> ToolResult:
        """
        Выдает полные права администратора.
        """
        channel_id = clean_peer_id(channel_id)
        user_id = clean_peer_id(user_id)
        try:
            channel_entity = await self.client.get_input_entity(channel_id)
            user_entity = await self.client.get_input_entity(user_id)
            rights = ChatAdminRights(
                change_info=True,
                post_messages=True,
                edit_messages=True,
                delete_messages=True,
                ban_users=True,
                invite_users=True,
                pin_messages=True,
                add_admins=True,
                anonymous=False,
                manage_call=True,
            )
            await self.client(
                EditAdminRequest(
                    channel=channel_entity,
                    user_id=user_entity,
                    admin_rights=rights,
                    rank="Creator's Proxy",
                )
            )
            return ToolResult.ok(msg=f"Пользователь {user_id} назначен администратором.")
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка выдачи админки в {channel_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка выдачи прав: {e}", error=str(e))

    @skill()
    async def create_discussion_group(self, channel_id: str | int, group_title: str) -> ToolResult:
        """
        Создает супергруппу и привязывает её к каналу.
        """
        channel_id = clean_peer_id(channel_id)
        try:
            channel_entity = await self.client.get_input_entity(channel_id)
            created_group = await self.client(
                functions.channels.CreateChannelRequest(
                    title=group_title, about="Обсуждения", megagroup=True
                )
            )
            group_id = created_group.chats[0].id
            group_entity = await self.client.get_input_entity(group_id)
            await self.client(
                functions.channels.SetDiscussionGroupRequest(
                    broadcast=channel_entity, group=group_entity
                )
            )
            return ToolResult.ok(
                msg=f"Группа '{group_title}' привязана к каналу. ID: {group_id}",
                data=group_id,
            )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка привязки группы к {channel_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка создания группы обсуждений: {e}", error=str(e))
