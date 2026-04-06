from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.exceptions import TelegramAPIError

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.telegram.aiogram.client import AiogramClient
from src.l03_interfaces.type.base import BaseInstrument
from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill


class AiogramBotManage(BaseInstrument):
    """Сервис для управления профилем и настройками самого бота (Aiogram)."""

    def __init__(self, client: 'AiogramClient'):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.bot = client.bot

    @skill()
    async def set_bot_name(self, name: str) -> ToolResult:
        """
        Изменяет публичное имя бота (до 64 символов).
        """
        try:
            if len(name) > 64:
                return ToolResult.fail(
                    msg=f"Ошибка: Имя бота слишком длинное ({len(name)} символов). Максимум 64."
                )

            await self.bot.set_my_name(name=name)
            system_logger.info(f"[Telegram Bot] Имя бота успешно изменено на: '{name}'")
            return ToolResult.ok(msg=f"Имя бота успешно изменено на '{name}'.")

        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка изменения имени бота: {e}")
            return ToolResult.fail(msg=f"Ошибка при изменении имени бота: {e}", error=str(e))

    @skill()
    async def set_bot_description(self, description: str) -> ToolResult:
        """
        Изменяет описание бота (то, что пользователь видит при первом открытии пустого чата, до 512 символов).
        """
        try:
            if len(description) > 512:
                description = description[:509] + "..."

            await self.bot.set_my_description(description=description)
            system_logger.info("[Telegram Bot] Описание бота обновлено.")
            return ToolResult.ok(msg="Описание бота для новых чатов успешно обновлено.")

        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка изменения описания: {e}")
            return ToolResult.fail(msg=f"Ошибка при изменении описания бота: {e}", error=str(e))

    @skill()
    async def set_bot_short_description(self, short_description: str) -> ToolResult:
        """
        Изменяет короткое описание бота (то, что видно в профиле бота под именем, до 120 символов).
        """
        try:
            if len(short_description) > 120:
                short_description = short_description[:117] + "..."

            await self.bot.set_my_short_description(short_description=short_description)
            system_logger.info("[Telegram Bot] Короткое описание (Short Description) обновлено.")
            return ToolResult.ok(msg="Короткое описание (Bio) бота успешно обновлено.")

        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка изменения короткого описания: {e}")
            return ToolResult.fail(
                msg=f"Ошибка при изменении короткого описания: {e}", error=str(e)
            )

    @skill()
    async def set_bot_commands(self, commands: dict[str, str]) -> ToolResult:
        """
        Устанавливает список команд (меню по кнопке '/' слева от поля ввода).
        """
        try:
            if not commands:
                return await self.clear_bot_commands()

            bot_commands = []
            for cmd, desc in commands.items():
                clean_cmd = cmd.strip("/").lower().replace(" ", "_")
                clean_desc = desc[:256]
                bot_commands.append(BotCommand(command=clean_cmd, description=clean_desc))

            await self.bot.set_my_commands(commands=bot_commands, scope=BotCommandScopeDefault())

            cmds_str = ", ".join([f"/{c.command}" for c in bot_commands])
            system_logger.info(f"[Telegram Bot] Меню команд обновлено: {cmds_str}")
            return ToolResult.ok(msg=f"Список команд меню успешно обновлен: {cmds_str}.")

        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка установки команд бота: {e}")
            return ToolResult.fail(msg=f"Ошибка при установке меню команд: {e}", error=str(e))

    @skill()
    async def clear_bot_commands(self) -> ToolResult:
        """
        Удаляет все установленные команды бота (скрывает кнопку меню).
        """
        try:
            await self.bot.delete_my_commands(scope=BotCommandScopeDefault())
            system_logger.info("[Telegram Bot] Команды меню бота очищены.")
            return ToolResult.ok(msg="Список команд меню бота успешно очищен.")

        except TelegramAPIError as e:
            system_logger.error(f"[Telegram Bot] Ошибка очистки команд: {e}")
            return ToolResult.fail(msg=f"Ошибка при очистке меню команд: {e}", error=str(e))
