from telethon import TelegramClient
from telethon import functions, types
from telethon.tl.types import ChannelParticipantsAdmins
from telethon.tl.types import ChannelParticipantsSearch

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.telegram.telethon.instruments._helpers import clean_peer_id
from src.l03_interfaces.type.base import BaseInstrument
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill


class TelethonChats(BaseInstrument):
    """Сервис для удобной работы с чатами в Telegram."""

    def __init__(self, client: TelegramClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.client = client

    @skill()
    async def get_chat_info(self, chat_id: str | int) -> ToolResult:
        """
        Получает полную информацию (Bio, участники) о чате/юзере.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            entity = await self.client.get_entity(chat_id)
            if isinstance(entity, types.Channel) or isinstance(entity, types.Chat):
                return ToolResult.ok(
                    msg=f"Название: {entity.title}, Тип: Группа/Канал, ID: {entity.id}",
                    data=entity,
                )
            elif isinstance(entity, types.User):
                full_user = await self.client(functions.users.GetFullUserRequest(id=entity))
                bio = full_user.full_user.about or "Bio отсутствует"
                username = f"@{entity.username}" if entity.username else "No Username"
                return ToolResult.ok(
                    msg=f"Имя: {entity.first_name}, Username: {username}, Bio: {bio}",
                    data=full_user,
                )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка получения инфо о {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка получения инфо: {e}", error=str(e))

    @skill()
    async def check_user_in_chat(self, chat_id: str | int, query: str) -> ToolResult:
        """
        Проверяет, есть ли конкретный пользователь в канале/группе.
        query может быть ID, username или частью имени.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            found_users = []
            async for user in self.client.iter_participants(
                chat_id, search=query, filter=ChannelParticipantsSearch
            ):
                name = getattr(user, "first_name", "Unknown")
                username = (
                    f"@{user.username}" if getattr(user, "username", None) else "без_юзернейма"
                )
                found_users.append(f"ID: {user.id} | {name} ({username})")
            return (
                ToolResult.ok(
                    msg="Найдены совпадения:\n" + "\n".join(found_users),
                    data=found_users,
                )
                if found_users
                else ToolResult.fail(msg=f"Пользователь '{query}' не найден.")
            )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка поиска юзера в {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при поиске пользователя: {e}", error=str(e))

    @skill()
    async def leave_chat(self, chat_id: str | int) -> ToolResult:
        """
        Выходит из канала или группы.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            entity = await self.client.get_input_entity(chat_id)
            await self.client(functions.channels.LeaveChannelRequest(channel=entity))
            return ToolResult.ok(msg="Успешно покинули чат/канал.")
        except Exception as e:
            try:
                await self.client(
                    functions.messages.DeleteChatUserRequest(chat_id=chat_id, user_id="me")
                )
                return ToolResult.ok(msg="Успешно покинули базовую группу.")
            except Exception as e2:
                system_logger.error(f"[Telegram Tools] Ошибка выхода из {chat_id}: {e} | {e2}")
                return ToolResult.fail(
                    msg=f"Ошибка при выходе из чата: {e} | {e2}", error=f"{e} | {e2}"
                )

    @skill()
    async def archive_chat(self, chat_id: str | int) -> ToolResult:
        """
        Отправляет чат в архив
        """
        chat_id = clean_peer_id(chat_id)
        try:
            entity = await self.client.get_input_entity(chat_id)
            await self.client(
                functions.folders.EditPeerFoldersRequest(
                    folder_peers=[types.InputFolderPeer(peer=entity, folder_id=1)]
                )
            )
            return ToolResult.ok(msg="Чат успешно отправлен в архив.")
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка архивации {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при архивации чата: {e}", error=str(e))

    @skill()
    async def unarchive_chat(self, chat_id: str | int) -> ToolResult:
        """
        Возвращает чат из архива.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            entity = await self.client.get_input_entity(chat_id)
            await self.client(
                functions.folders.EditPeerFoldersRequest(
                    folder_peers=[types.InputFolderPeer(peer=entity, folder_id=0)]
                )
            )
            return ToolResult.ok(msg="Чат успешно возвращен из архива.")
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка разархивации {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при возврате чата из архива: {e}", error=str(e))

    @skill()
    async def create_supergroup(self, title: str, about: str = "") -> ToolResult:
        """
        Создает новую супергруппу.
        """
        try:
            result = await self.client(
                functions.channels.CreateChannelRequest(title=title, about=about, megagroup=True)
            )
            return ToolResult.ok(
                msg=f"Группа '{title}' успешно создана. ID: {result.chats[0].id}",
                data=result.chats[0].id,
            )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка создания группы: {e}")
            return ToolResult.fail(msg=f"Ошибка при создании группы: {e}", error=str(e))

    @skill()
    async def invite_to_chat(self, chat_id: str | int, user_id: str | int) -> ToolResult:
        """
        Приглашает пользователя в группу/канал.
        """
        chat_id = clean_peer_id(chat_id)
        user_id = clean_peer_id(user_id)
        try:
            chat_entity = await self.client.get_input_entity(chat_id)
            user_entity = await self.client.get_input_entity(user_id)
            await self.client(
                functions.channels.InviteToChannelRequest(channel=chat_entity, users=[user_entity])
            )
            return ToolResult.ok(msg=f"Пользователь {user_id} приглашен в чат {chat_id}.")
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка инвайта {user_id} в {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при приглашении: {e}", error=str(e))

    @skill()
    async def get_chat_admins(self, chat_id: str | int) -> ToolResult:
        """
        Получает список администраторов чата/канала.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            admins = []
            async for admin in self.client.iter_participants(
                chat_id, filter=ChannelParticipantsAdmins
            ):
                name = getattr(admin, "first_name", "Unknown")
                username = (
                    f"@{admin.username}" if getattr(admin, "username", None) else "без_юзернейма"
                )
                admins.append(f"- ID: {admin.id} | {name} ({username})")
            return (
                ToolResult.ok(
                    msg=f"Администраторы чата {chat_id}:\n" + "\n".join(admins),
                    data=admins,
                )
                if admins
                else ToolResult.fail(msg="Не удалось найти администраторов.")
            )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка получения админов {chat_id}: {e}")
            return ToolResult.fail(
                msg=f"Ошибка при получении списка администраторов: {e}", error=str(e)
            )
