import os
from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.base import BaseInstrument
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill


class TelethonAccount(BaseInstrument):
    """Сервис для удобной работы с аккаунтом в Telegram."""

    def __init__(self, client: TelegramClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.client = client

    @skill()
    async def change_bio(self, new_bio: str) -> ToolResult:
        """
        Меняет раздел 'О себе' в профиле.
        """
        try:
            if len(new_bio) > 70:
                return ToolResult.fail(
                    msg=f"Ошибка: Bio слишком длинное ({len(new_bio)} символов). Максимум 70.",
                    error="Validation error",
                )
            await self.client(UpdateProfileRequest(about=new_bio))
            return ToolResult.ok(
                msg=f"Статус (Bio) успешно изменен на: '{new_bio}'",
                data={"bio": new_bio},
            )
        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка смены Bio: {e}")
            return ToolResult.fail(msg=f"Ошибка смены Bio: {e}", error=str(e))

    @skill()
    async def change_avatar(self, image_path: str) -> ToolResult:
        """
        Меняет аватарку профиля.
        """
        try:
            if not os.path.exists(image_path):
                return ToolResult.fail(
                    msg=f"Ошибка: Файл '{image_path}' не найден.",
                    error="FileNotFoundError",
                )
            file = await self.client.upload_file(image_path)
            await self.client(UploadProfilePhotoRequest(file=file))

            return ToolResult.ok(
                msg="Аватарка профиля успешно обновлена.", data={"path": image_path}
            )

        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка смены аватарки профиля: {e}")
            return ToolResult.fail(msg=f"Ошибка при обновлении аватарки: {e}", error=str(e))

    @skill()
    async def change_account_name(self, first_name: str, last_name: str = "") -> ToolResult:
        """
        Меняет имя и фамилию профиля.
        """
        try:
            await self.client(UpdateProfileRequest(first_name=first_name, last_name=last_name))
            return ToolResult.ok(
                msg=f"Имя профиля успешно изменено на: {first_name} {last_name}",
                data={"first_name": first_name, "last_name": last_name},
            )

        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка смены имени: {e}")
            return ToolResult.fail(msg=f"Ошибка при смене имени: {e}", error=str(e))

    @skill()
    async def change_account_username(self, username: str) -> ToolResult:
        """
        Меняет @username профиля.
        """
        try:
            clean_username = username.replace("@", "")
            await self.client(UpdateUsernameRequest(username=clean_username))

            return ToolResult.ok(
                msg=f"Юзернейм успешно изменен на: @{clean_username}",
                data={"username": clean_username},
            )

        except Exception as e:
            system_logger.error(f"[Telegram Tools] Ошибка смены юзернейма: {e}")
            return ToolResult.fail(msg=f"Ошибка при смене юзернейма: {e}", error=str(e))
