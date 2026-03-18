import re
import asyncio
from telethon import TelegramClient, types
from telethon.tl.functions.messages import InstallStickerSetRequest
from telethon.tl.types import InputStickerSetShortName

from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog_decorator import watchdog_decorator
from src.layer00_utils.watchdog.watchdog import userbot_telethon_module
from src.layer00_utils.workspace import workspace_manager
from src.layer00_utils.audio_tools import process_audio_for_llm
from src.layer00_utils.image_tools import compress_and_encode_image
from src.layer03_brain.llm.multimodality import describe_image, transcribe_audio
from src.layer02_sensors.telegram.shared_tools._helpers import clean_peer_id

@watchdog_decorator(userbot_telethon_module)
async def tg_get_media(client: TelegramClient, chat_id: str | int, message_id: int) -> str:
    """Универсальный загрузчик: фото, ГС, кружочки, стикеры, миниатюры видео"""
    chat_id = clean_peer_id(chat_id)
    try:
        messages = await client.get_messages(chat_id, ids=[message_id])
        if not messages or not messages[0].media:
            return "В этом сообщении нет поддерживаемых медиафайлов."
        
        msg = messages[0]
        
        # 1. Фотографии
        if msg.photo:
            img_path = workspace_manager.get_temp_file(prefix="vision_", extension=".jpg")
            await client.download_media(msg, file=str(img_path))
            b64_string = await asyncio.to_thread(compress_and_encode_image, str(img_path))
            description = await describe_image(b64_string)
            return description
            
        # 2. Стикеры и Видео (Достаем миниатюру)
        elif msg.document:
            is_sticker = any(isinstance(attr, types.DocumentAttributeSticker) for attr in msg.document.attributes)
            is_video = any(isinstance(attr, types.DocumentAttributeVideo) for attr in msg.document.attributes)
            
            if is_sticker or is_video:
                img_path = workspace_manager.get_temp_file(prefix="thumb_", extension=".jpg")
                downloaded = await client.download_media(msg, file=str(img_path), thumb=-1)
                if not downloaded:
                    downloaded = await client.download_media(msg, file=str(img_path))
                    
                if downloaded:
                    b64_string = await asyncio.to_thread(compress_and_encode_image, str(downloaded))
                    description = await describe_image(b64_string)
                    return description
                return "Не удалось извлечь изображение или миниатюру из файла."
                    
            return f"Это файл/документ: {msg.file.name}. Это НЕ медиа. Используйте сооветствующий инструмент для скачивания файлов/документов."

        # 3. Голосовые сообщения
        elif msg.voice or msg.video_note:
            temp_path = workspace_manager.get_temp_file(prefix="audio_", extension=".ogg")
            await client.download_media(msg, file=str(temp_path))
            b64_data = await asyncio.to_thread(process_audio_for_llm, str(temp_path))
            transcription = await transcribe_audio(b64_data)
            return transcription
            
        return "Неизвестный тип медиа."
    except Exception as e:
        system_logger.error(f"[Telegram Tools] Ошибка получения медиа из {chat_id}: {e}")
        return f"Ошибка при получении медиа: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_send_file(client: TelegramClient, chat_id: str | int, file_path: str, caption: str = "") -> str:
    """Отправляет локальный файл как документ в Telegram"""
    chat_id = clean_peer_id(chat_id)
    try:
        msg = await client.send_file(chat_id, file=file_path, caption=caption)
        await client.send_read_acknowledge(chat_id, clear_mentions=True)
        return f"Файл успешно отправлен. ID сообщения: {msg.id}"
    except Exception as e:
        system_logger.error(f"[Telegram Tools] Ошибка отправки файла в {chat_id}: {e}")
        return f"Ошибка при отправке файла: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_download_file(client: TelegramClient, chat_id: str | int, message_id: int) -> str:
    """Скачивает файл из сообщения в песочницу"""
    chat_id = clean_peer_id(chat_id)
    try:
        messages = await client.get_messages(chat_id, ids=[message_id])
        if not messages or not messages[0].media:
            return "Ошибка: Сообщение не найдено или не содержит медиа/файлов."
        
        msg = messages[0]
        filename = "downloaded_file"
        if msg.document:
            for attr in msg.document.attributes:
                if isinstance(attr, types.DocumentAttributeFilename):
                    filename = attr.file_name
                    break
                    
        clean_filename = re.sub(r'[\\/*?:"<>|]', "", filename)
        if not clean_filename:
            clean_filename = f"file_{message_id}.bin"
            
        target_path = workspace_manager.get_sandbox_file(clean_filename)
        await client.download_media(msg, file=str(target_path))
        return f"Файл '{clean_filename}' успешно скачан в песочницу."
    except Exception as e:
        system_logger.error(f"[Telegram Tools] Ошибка скачивания файла {message_id}: {e}")
        return f"Ошибка при скачивании файла: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_send_sticker(client: TelegramClient, chat_id: str | int, emoji: str) -> str:
    """Отправляет стикер через встроенного инлайн-бота @sticker"""
    chat_id = clean_peer_id(chat_id)
    try:
        results = await client.inline_query('sticker', emoji)
        if results:
            msg = await results[0].click(chat_id)
            await client.send_read_acknowledge(chat_id, clear_mentions=True)
            return f"Стикер для эмодзи '{emoji}' успешно отправлен. ID: {msg.id}"
        return f"Не удалось найти стикер для эмодзи '{emoji}'."
    except Exception as e:
        system_logger.error(f"[Telegram Tools] Ошибка отправки стикера в {chat_id}: {e}")
        return f"Ошибка при отправке стикера: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_save_sticker_set(client: TelegramClient, stickerset_shortname: str) -> str:
    """Добавляет стикерпак к себе в коллекцию"""
    try:
        if "addstickers/" in stickerset_shortname:
            stickerset_shortname = stickerset_shortname.split("addstickers/")[1].split("/")[0]

        await client(InstallStickerSetRequest(
            stickerset=InputStickerSetShortName(short_name=stickerset_shortname),
            archived=False
        ))
        return f"Стикерпак '{stickerset_shortname}' успешно добавлен в вашу коллекцию."
    except Exception as e:
        system_logger.error(f"[Telegram Tools] Ошибка сохранения стикеров: {e}")
        return f"Ошибка добавления стикерпака: {e}"