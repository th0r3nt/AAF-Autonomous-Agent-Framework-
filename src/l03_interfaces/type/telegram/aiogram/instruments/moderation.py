from datetime import timedelta
from aiogram.types import ChatPermissions
from aiogram.exceptions import TelegramAPIError

from src.l00_utils.managers.logger import system_logger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.telegram.aiogram.client import AiogramClient
from src.l03_interfaces.type.base import BaseInstrument
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill


class AiogramModeration(BaseInstrument):
    """Сервис модерации для Telegram-бота (Aiogram). Управление банами, мутами и правами."""

    def __init__(self, client: 'AiogramClient'):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.bot = client.bot

    @skill()
    async def bot_ban_user(
        self, chat_id: str | int, user_id: int, revoke_messages: bool = False
    ) -> ToolResult:
        """
        Банит пользователя в группе или канале.
        :param revoke_messages: Если True, удаляет все сообщения пользователя в этом чате.
        """
        try:
            await self.bot.ban_chat_member(
                chat_id=chat_id, user_id=user_id, revoke_messages=revoke_messages
            )
            action = "забанен с удалением сообщений" if revoke_messages else "забанен"
            system_logger.info(f"[Telegram Bot] Пользователь {user_id} {action} в чате {chat_id}.")
            return ToolResult.ok(msg=f"Пользователь {user_id} успешно {action} в чате {chat_id}.")

        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка бана {user_id} в {chat_id}: {e}")
            return ToolResult.fail(
                msg=f"Ошибка при попытке забанить пользователя: {e}", error=str(e)
            )

    @skill()
    async def bot_unban_user(self, chat_id: str | int, user_id: int) -> ToolResult:
        """
        Разбанивает пользователя (удаляет из черного списка группы/канала).
        Пользователю нужно будет заново зайти по ссылке.
        """
        try:
            # only_if_banned=True гарантирует, что мы не кикнем пользователя, который сейчас в чате
            await self.bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)
            system_logger.info(f"[Telegram Bot] Пользователь {user_id} разбанен в {chat_id}.")
            return ToolResult.ok(msg=f"Пользователь {user_id} успешно разбанен.")

        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка разбана {user_id} в {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при разбане пользователя: {e}", error=str(e))

    @skill()
    async def bot_mute_user(
        self, chat_id: str | int, user_id: int, duration_minutes: int = 0
    ) -> ToolResult:
        """
        Запрещает пользователю писать сообщения (Read-Only).
        :param duration_minutes: Длительность мута в минутах. Если 0 - мут навсегда.
        """
        try:
            # Забираем права на отправку любых видов сообщений
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
            )

            # Если время указано (больше 0), конвертируем в timedelta
            # Важно: Telegram принимает муты от 30 секунд до 366 дней.
            until_date = timedelta(minutes=duration_minutes) if duration_minutes > 0 else None

            await self.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=permissions,
                until_date=until_date,
            )

            time_str = f"на {duration_minutes} минут" if duration_minutes > 0 else "навсегда"
            system_logger.info(
                f"[Telegram Bot] Пользователь {user_id} замучен {time_str} в {chat_id}."
            )
            return ToolResult.ok(
                msg=f"Пользователь {user_id} переведен в режим 'только чтение' {time_str}."
            )

        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка мута {user_id} в {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при выдаче мута: {e}", error=str(e))

    @skill()
    async def bot_unmute_user(self, chat_id: str | int, user_id: int) -> ToolResult:
        """
        Снимает мут с пользователя, возвращая базовые права на отправку текста и медиа.
        """
        try:
            # Возвращаем стандартные права группы (True разрешает действия)
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )

            await self.bot.restrict_chat_member(
                chat_id=chat_id, user_id=user_id, permissions=permissions
            )
            system_logger.info(f"[Telegram Bot] С пользователя {user_id} снят мут в {chat_id}.")
            return ToolResult.ok(
                msg=f"Мут снят. Пользователь {user_id} снова может писать сообщения."
            )

        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка снятия мута {user_id} в {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при снятии мута: {e}", error=str(e))

    @skill()
    async def bot_promote_to_admin(
        self, chat_id: str | int, user_id: int, title: str = ""
    ) -> ToolResult:
        """
        Выдает пользователю права модератора.
        """
        try:
            await self.bot.promote_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=False,  # Не даем права назначать других админов
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=True,
            )

            # Пытаемся установить кастомную плашку админа (работает только в супергруппах)
            try:
                await self.bot.set_chat_administrator_custom_title(
                    chat_id=chat_id, user_id=user_id, custom_title=title
                )
            except TelegramAPIError:
                pass  # Игнорируем, если не удалось поставить плашку

            system_logger.info(
                f"[Telegram Bot] Пользователь {user_id} назначен админом в {chat_id}."
            )
            return ToolResult.ok(msg=f"Пользователю {user_id} успешно выданы права модератора.")

        except TelegramAPIError as e:
            system_logger.error(
                f"[Telegram Bot] Ошибка назначения админа {user_id} в {chat_id}: {e}"
            )
            return ToolResult.fail(msg=f"Ошибка выдачи прав администратора: {e}", error=str(e))
