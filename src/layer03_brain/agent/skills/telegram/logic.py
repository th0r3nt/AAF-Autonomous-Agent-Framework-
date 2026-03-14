from datetime import datetime, timedelta
import os
from src.layer00_utils.config_manager import config
from src.layer00_utils.workspace import (workspace_manager)
from src.layer01_datastate.sql_db.management.dialogue import create_dialogue_entry
from src.layer02_sensors.telegram.agent_account.client import agent_client

from src.layer02_sensors.telegram.shared_tools.telethon_tools import (
    tg_send_message, tg_reply_to_message, tg_get_recent_messages, 
    tg_get_dialogs, tg_get_channel_posts, tg_get_chat_info,
    tg_mark_as_read, tg_set_reaction, tg_search_channels, 
    tg_join_channel, tg_comment_on_post, tg_get_unread_chats_summary,
    tg_delete_message, tg_forward_message, tg_create_poll,
    tg_get_post_comments, tg_change_bio, tg_get_poll_results,
    tg_ban_user, tg_save_sticker_set, tg_unban_user, tg_get_banned_users,
    tg_create_channel_post, tg_edit_message, tg_pin_message, tg_vote_in_poll,
    tg_get_channel_subscribers, tg_check_user_in_chat, tg_send_voice_message,
    tg_get_media, tg_send_sticker, tg_change_avatar, tg_create_channel, 
    tg_update_channel_info, tg_set_channel_username, tg_promote_to_admin,
    tg_change_account_name, tg_change_account_username, tg_create_discussion_group,
    tg_set_typing_status, tg_leave_chat, tg_archive_chat, tg_create_supergroup, 
    tg_invite_to_chat, tg_add_to_contacts, tg_get_chat_admins, tg_send_file,
    tg_unarchive_chat, tg_search_chat_messages, tg_download_file, tg_change_channel_avatar
)

def _format_chat_source(chat_id: str | int, topic_id: int = None) -> str:
    """Вспомогательная функция: очищает ID и формирует тег источника для БД"""
    clean_id = str(chat_id).replace('@', '')
    topic_str = f" [Топик ID: {topic_id}]" if topic_id else ""
    if clean_id.startswith('-'):
        return f"tg_agent_group_({clean_id}){topic_str}"
    return f"tg_agent_chat_({clean_id}){topic_str}"

# НАВЫКИ

async def send_message_as_agent(chat_id: str, text: str, topic_id: int = None, silent: bool = False, delay_seconds: int = 0) -> str:
    """Обертка: отправляет сообщение (с поддержкой silent и отложки)"""
    schedule_date = None
    if delay_seconds > 0:
        schedule_date = datetime.now() + timedelta(seconds=delay_seconds)
        
    result = await tg_send_message(agent_client, chat_id, text, topic_id, silent, schedule_date)
    
    chat_source = _format_chat_source(chat_id, topic_id)
    delay_str = f" [Отложено на {delay_seconds} сек]" if delay_seconds > 0 else ""
    silent_str = " [Без звука]" if silent else ""
    
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"{silent_str}{delay_str} {text}".strip(), source=chat_source)
    return result

async def set_chat_typing_status_as_agent(chat_id: str, action: str = "typing") -> str:
    """Обертка: Отправляет статус 'Печатает...' или 'Записывает аудио...' (длится ~5 секунд)"""
    return await tg_set_typing_status(agent_client, chat_id, action)

async def leave_chat_as_agent(chat_id: str) -> str:
    """Обертка: покидает Telegram-чат"""
    return await tg_leave_chat(agent_client, chat_id)

async def archive_chat_as_agent(chat_id: str) -> str:
    """Обертка: архивирует Telegram-чат"""
    return await tg_archive_chat(agent_client, chat_id)

async def read_chat_as_agent(chat_id: str, limit: int = 50, topic_id: int = None) -> str:
    """Обертка: читает последние n сообщений с чата"""
    return await tg_get_recent_messages(agent_client, chat_id, limit, topic_id)

async def get_dialogs_as_agent(limit: int = 30) -> str:
    """Обертка: получает список последних диалогов/групп"""
    return await tg_get_dialogs(agent_client, limit)

async def reply_to_message_as_agent(chat_id: str, message_id: int, text: str) -> str:
    """Обертка: отвечает на конкретное сообщение"""
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=text, source=chat_source)
    return await tg_reply_to_message(agent_client, chat_id, message_id, text)

async def get_channel_posts_as_agent(channel_name: str, limit: int = 10) -> str:
    """Обертка: получает последние посты из канала"""
    return await tg_get_channel_posts(agent_client, channel_name, limit)

async def get_chat_info_as_agent(chat_id: str) -> str:
    """Обертка: получает полную информацию (Bio, участники) о чате/юзере"""
    return await tg_get_chat_info(agent_client, chat_id)

async def mark_chat_as_read_as_agent(chat_id: str) -> str:
    """Обертка: помечает чат как прочитанный"""
    return await tg_mark_as_read(agent_client, chat_id)

async def set_message_reaction_as_agent(chat_id: str, message_id: int, emoticon: str) -> str:
    """Обертка: ставит реакцию на сообщение"""
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Поставлена реакция {emoticon} на сообщение ID {message_id}]", source=chat_source)
    return await tg_set_reaction(agent_client, chat_id, message_id, emoticon)

async def search_telegram_channels_as_agent(query: str, limit: int = 5) -> str:
    """Обертка: ищет каналы в ТГ"""
    return await tg_search_channels(agent_client, query, limit)

async def join_telegram_channel_as_agent(link_or_username: str) -> str:
    """Обертка: вступает в канал"""
    return await tg_join_channel(agent_client, link_or_username)

async def comment_on_post_as_agent(channel_id: str, message_id: int, text: str) -> str:
    """Обертка: оставляет комментарий под постом в канале"""
    chat_source = _format_chat_source(channel_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Комментарий к посту {message_id}]: {text}", source=chat_source)
    return await tg_comment_on_post(agent_client, channel_id, message_id, text)

async def get_unread_tg_summary() -> str:
    """Вспомогательная функция для контекста: возвращает список чатов с непрочитанными сообщениями"""
    return await tg_get_unread_chats_summary(agent_client)

async def delete_message_as_agent(chat_id: str, message_id: int) -> str:
    """Обертка: удаляет сообщение"""
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Удаление своего сообщения ID {message_id}]", source=chat_source)
    return await tg_delete_message(agent_client, chat_id, message_id)

async def forward_message_as_agent(from_chat: str, message_id: int, to_chat: str) -> str:
    """Обертка: пересылает сообщение"""
    chat_source = _format_chat_source(to_chat) # Логируем туда, КУДА переслали
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Пересылка сообщения ID {message_id} из чата {from_chat}]", source=chat_source)
    return await tg_forward_message(agent_client, from_chat, message_id, to_chat)

async def create_poll_as_agent(chat_id: str, question: str, options: list) -> str:
    """Обертка: создает опрос"""
    return await tg_create_poll(agent_client, chat_id, question, options)

async def get_post_comments_as_agent(channel_name: str, message_id: int, limit: int = 20) -> str:
    """Обертка: читает комментарии"""
    return await tg_get_post_comments(agent_client, channel_name, message_id, limit)

async def change_my_bio_as_agent(new_bio: str) -> str:
    """Обертка: меняет био"""
    return await tg_change_bio(agent_client, new_bio)

async def get_poll_results_as_agent(chat_id: str, message_id: int) -> str:
    """Обертка: результаты опроса"""
    return await tg_get_poll_results(agent_client, chat_id, message_id)

async def ban_user_as_agent(chat_id: str, user_id: str, reason: str = "Нарушение правил") -> str:
    """Обертка: бан пользователя"""
    return await tg_ban_user(agent_client, chat_id, user_id, reason)

async def save_sticker_pack_as_agent(short_name: str) -> str:
    """Обертка: сохранение стикеров"""
    return await tg_save_sticker_set(agent_client, short_name)

async def unban_user_as_agent(chat_id: str, user_id: str) -> str:
    """Обертка: разбан пользователя"""
    return await tg_unban_user(agent_client, chat_id, user_id)

async def get_banned_users_as_agent(chat_id: str, limit: int = 50) -> str:
    """Обертка: просмотр забаненных"""
    return await tg_get_banned_users(agent_client, chat_id, limit)

async def create_channel_post_as_agent(channel_id: str, text: str) -> str:
    """Обертка: публикует пост в канал"""
    chat_source = _format_chat_source(channel_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Опубликован пост]: {text}", source=chat_source)
    return await tg_create_channel_post(agent_client, channel_id, text)

async def edit_message_as_agent(chat_id: str, message_id: int, new_text: str) -> str:
    """Обертка: редактирует сообщение/пост"""
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Редактирование сообщения ID {message_id}]: {new_text}", source=chat_source)
    return await tg_edit_message(agent_client, chat_id, message_id, new_text)

async def pin_message_as_agent(chat_id: str, message_id: int) -> str:
    """Обертка: закрепляет сообщение"""
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Закрепление сообщения ID {message_id}]", source=chat_source)
    return await tg_pin_message(agent_client, chat_id, message_id)

async def vote_in_poll_as_agent(chat_id: str, message_id: int, options: list) -> str:
    """Обертка: голосует в опросе"""
    return await tg_vote_in_poll(agent_client, chat_id, message_id, options)

async def get_channel_subscribers_as_agent(chat_id: str, limit: int = 50) -> str:
    """Обертка: получает список подписчиков"""
    return await tg_get_channel_subscribers(agent_client, chat_id, limit)

async def check_user_in_chat_as_agent(chat_id: str, query: str) -> str:
    """Обертка: проверяет наличие юзера в чате"""
    return await tg_check_user_in_chat(agent_client, chat_id, query)

async def send_voice_message_as_agent(chat_id: str, text: str) -> str:
    """Обертка: отправляет голосовое сообщение в чат"""
    result = await tg_send_voice_message(agent_client, chat_id, text)
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Голосовое сообщение]: {text}", source=chat_source)
    return result

async def get_tg_media_as_agent(chat_id: str, message_id: int) -> dict | str:
    """Обертка: скачивает медиа (фото, гс, кружок, стикер, превью видео) и кидает в ReAct цикл"""
    result = await tg_get_media(agent_client, chat_id, message_id)
    return result

async def send_tg_sticker_as_agent(chat_id: str, emoji: str) -> str:
    """Обертка: отправляет стикер по эмодзи"""
    result = await tg_send_sticker(agent_client, chat_id, emoji)
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Отправлен стикер, соответствующий эмодзи: {emoji}]", source=chat_source)
    return result

async def change_tg_avatar_as_agent(image_path: str) -> str:
    """Обертка: меняет аватарку профиля"""
    return await tg_change_avatar(agent_client, image_path)

async def create_telegram_channel_as_agent(title: str, about: str = "") -> str:
    """Обертка: создает канал"""
    result = await tg_create_channel(agent_client, title, about)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Создан новый канал '{title}']", source="system")
    return result

async def update_channel_info_as_agent(channel_id: str, new_title: str = None, new_about: str = None) -> str:
    """Обертка: обновляет инфу канала"""
    return await tg_update_channel_info(agent_client, channel_id, new_title, new_about)

async def set_channel_username_as_agent(channel_id: str, username: str) -> str:
    """Обертка: ставит публичный юзернейм"""
    return await tg_set_channel_username(agent_client, channel_id, username)

async def promote_user_to_admin_as_agent(channel_id: str, user_id: str) -> str:
    """Обертка: выдает права админа"""
    return await tg_promote_to_admin(agent_client, channel_id, user_id)

async def change_account_name_as_agent(first_name: str, last_name: str = "") -> str:
    """Обертка: меняет имя аккаунта"""
    return await tg_change_account_name(agent_client, first_name, last_name)

async def change_account_username_as_agent(username: str) -> str:
    """Обертка: меняет юзернейм аккаунта"""
    return await tg_change_account_username(agent_client, username)

async def create_discussion_group_as_agent(channel_id: str, group_title: str) -> str:
    """Обертка: создает привязанную группу для комментариев"""
    return await tg_create_discussion_group(agent_client, channel_id, group_title)

async def create_supergroup_as_agent(title: str, about: str = "") -> str:
    return await tg_create_supergroup(agent_client, title, about)

async def invite_user_to_chat_as_agent(chat_id: str, user_id: str) -> str:
    return await tg_invite_to_chat(agent_client, chat_id, user_id)

async def add_user_to_contacts_as_agent(user_id: str, first_name: str, last_name: str = "") -> str:
    return await tg_add_to_contacts(agent_client, user_id, first_name, last_name)

async def get_chat_admins_as_agent(chat_id: str) -> str:
    return await tg_get_chat_admins(agent_client, chat_id)

async def send_file_to_tg_chat_as_agent(chat_id: str, filename: str, caption: str = "") -> str:
    """Обертка: отправляет файл из песочницы в Telegram"""
    try:
        clean_filename = os.path.basename(filename.replace("file:///", "").replace("/app/", ""))
        filepath = workspace_manager.get_sandbox_file(clean_filename)
        
        if not filepath.exists() or not filepath.is_file():
            return f"Ошибка: Файл '{clean_filename}' не найден в песочнице."
        
        result = await tg_send_file(agent_client, chat_id, str(filepath), caption)
        
        chat_source = _format_chat_source(chat_id)
        await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Отправлен файл: {clean_filename}] {caption}".strip(), source=chat_source)
        return result
    except Exception as e:
        return f"Системная ошибка при отправке файла: {e}"
    
async def unarchive_tg_chat_as_agent(chat_id: str) -> str:
    """Обертка: возвращает чат из архива"""
    return await tg_unarchive_chat(agent_client, chat_id)

async def search_chat_messages_as_agent(chat_id: str, query: str = None, from_user: str = None, limit: int = 20) -> str:
    """Обертка: ищет сообщения в чате по тексту или автору"""
    return await tg_search_chat_messages(agent_client, chat_id, query, from_user, limit)

async def download_file_from_tg_as_agent(chat_id: str, message_id: int) -> str:
    """Обертка: скачивает файл из ТГ в песочницу"""
    result = await tg_download_file(agent_client, chat_id, message_id)
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Скачивание файла из сообщения ID {message_id}]", source=chat_source)
    return result

async def change_channel_avatar_as_agent(channel_id: str, filename: str) -> str:
    """Обертка: меняет аватарку канала"""
    try:
        clean_filename = os.path.basename(filename.replace("file:///", "").replace("/app/", ""))
        filepath = workspace_manager.get_sandbox_file(clean_filename)
        
        result = await tg_change_channel_avatar(agent_client, channel_id, str(filepath))
        chat_source = _format_chat_source(channel_id)
        await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Обновлена аватарка канала файлом {clean_filename}]", source=chat_source)
        return result
    except Exception as e:
        return f"Ошибка обработки пути к файлу: {e}"

TELEGRAM_REGISTRY = {
    # Работа сообщениями
    "send_message_as_agent": send_message_as_agent,
    "reply_to_message_as_agent": reply_to_message_as_agent,
    "delete_message_as_agent": delete_message_as_agent,
    "forward_message_as_agent": forward_message_as_agent,
    "edit_message_as_agent": edit_message_as_agent,
    "pin_message_as_agent": pin_message_as_agent,

    # Медиа (изображение, аудио, видео, файлы)
    "get_tg_media_as_agent": get_tg_media_as_agent,
    "send_voice_message_as_agent": send_voice_message_as_agent,
    "send_file_to_tg_chat_as_agent": send_file_to_tg_chat_as_agent,
    "download_file_from_tg_as_agent": download_file_from_tg_as_agent,
    "change_channel_avatar_as_agent": change_channel_avatar_as_agent,

    # Реакции
    "set_message_reaction_as_agent": set_message_reaction_as_agent,

    # Чаты
    "read_chat_as_agent": read_chat_as_agent,
    "get_dialogs_as_agent": get_dialogs_as_agent,
    "get_chat_info_as_agent": get_chat_info_as_agent,
    "mark_chat_as_read_as_agent": mark_chat_as_read_as_agent,
    "set_chat_typing_status_as_agent": set_chat_typing_status_as_agent,
    "leave_chat_as_agent": leave_chat_as_agent,
    "archive_chat_as_agent": archive_chat_as_agent,
    "unarchive_tg_chat_as_agent": unarchive_tg_chat_as_agent,
    "search_chat_messages_as_agent": search_chat_messages_as_agent,

    # Работа с каналами
    "get_channel_posts_as_agent": get_channel_posts_as_agent,
    "search_telegram_channels_as_agent": search_telegram_channels_as_agent,
    "join_telegram_channel_as_agent": join_telegram_channel_as_agent,
    "comment_on_post_as_agent": comment_on_post_as_agent,
    "get_post_comments_as_agent": get_post_comments_as_agent,
    "create_channel_post_as_agent": create_channel_post_as_agent,
    "create_telegram_channel_as_agent": create_telegram_channel_as_agent,
    "update_channel_info_as_agent": update_channel_info_as_agent,
    "set_channel_username_as_agent": set_channel_username_as_agent,
    "promote_user_to_admin_as_agent": promote_user_to_admin_as_agent,
    "create_discussion_group_as_agent": create_discussion_group_as_agent,
    "get_chat_admins_as_agent": get_chat_admins_as_agent,

    # Работа с группами
    "create_supergroup_as_agent": create_supergroup_as_agent,

    # Работа с подписчиками
    "get_channel_subscribers_as_agent": get_channel_subscribers_as_agent,
    "check_user_in_chat_as_agent": check_user_in_chat_as_agent,

    # Работа с опросами
    "create_poll_as_agent": create_poll_as_agent,
    "get_poll_results_as_agent": get_poll_results_as_agent,
    "vote_in_poll_as_agent": vote_in_poll_as_agent,
    
    # Изменение статуса/Bio
    "change_my_bio_as_agent": change_my_bio_as_agent,

    # Работа с ЧС/банами
    "ban_user_as_agent": ban_user_as_agent,
    "unban_user_as_agent": unban_user_as_agent,
    "get_banned_users_as_agent": get_banned_users_as_agent,

    # Стикеры
    "save_sticker_pack_as_agent": save_sticker_pack_as_agent,
    "send_tg_sticker_as_agent": send_tg_sticker_as_agent,

    # Свой аккаунт
    "change_tg_avatar_as_agent": change_tg_avatar_as_agent,
    "change_account_name_as_agent": change_account_name_as_agent,
    "change_account_username_as_agent": change_account_username_as_agent,
    "invite_user_to_chat_as_agent": invite_user_to_chat_as_agent,
    "add_user_to_contacts_as_agent": add_user_to_contacts_as_agent,
}