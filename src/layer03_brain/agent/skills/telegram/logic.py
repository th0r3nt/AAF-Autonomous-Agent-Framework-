from datetime import datetime, timedelta, timezone 
import os
from src.layer00_utils.config_manager import config
from src.layer00_utils.workspace import workspace_manager
from src.layer01_datastate.sql_db.management.dialogue import create_dialogue_entry
from src.layer02_sensors.telegram.agent_account.client import agent_client
from src.layer03_brain.agent.skills.auto_schema import llm_skill

from src.layer02_sensors.telegram.shared_tools.messages import (
    tg_send_message, tg_reply_to_message, tg_delete_message, tg_forward_message, 
    tg_edit_message, tg_pin_message, tg_set_typing_status
)
from src.layer02_sensors.telegram.shared_tools.history import (
    tg_get_recent_messages, tg_get_dialogs, tg_get_channel_posts, 
    tg_get_post_comments, tg_get_unread_chats_summary, tg_search_chat_messages, tg_mark_as_read
)
from src.layer02_sensors.telegram.shared_tools.media import (
    tg_get_media, tg_send_voice_message, tg_send_file, tg_download_file, 
    tg_send_sticker, tg_save_sticker_set
)
from src.layer02_sensors.telegram.shared_tools.management import (
    tg_get_chat_info, tg_search_channels, tg_join_channel, tg_ban_user, 
    tg_unban_user, tg_get_banned_users, tg_create_channel_post, 
    tg_get_channel_subscribers, tg_check_user_in_chat, tg_create_channel, 
    tg_update_channel_info, tg_set_channel_username, tg_promote_to_admin, 
    tg_create_discussion_group, tg_leave_chat, tg_archive_chat, 
    tg_unarchive_chat, tg_create_supergroup, tg_invite_to_chat, 
    tg_get_chat_admins, tg_change_channel_avatar
)
from src.layer02_sensors.telegram.shared_tools.account import (
    tg_change_bio, tg_change_avatar, tg_change_account_name, 
    tg_change_account_username, tg_add_to_contacts
)
from src.layer02_sensors.telegram.shared_tools.interact import (
    tg_set_reaction, tg_comment_on_post, tg_create_poll, 
    tg_get_poll_results, tg_vote_in_poll
)

def _format_chat_source(chat_id: str | int, topic_id: int = None) -> str:
    """Вспомогательная функция: очищает ID и формирует тег источника для БД"""
    clean_id = str(chat_id).replace('@', '')
    topic_str = f" [Топик ID: {topic_id}]" if topic_id else ""
    if clean_id.startswith('-'):
        return f"tg_agent_group_({clean_id}){topic_str}"
    return f"tg_agent_chat_({clean_id}){topic_str}"

# =====================================================================
# НАВЫКИ TELEGRAM
# =====================================================================

@llm_skill(
    description="Отправляет текстовое сообщение в Telegram чат/канал/ЛС.",
    parameters={
        "chat_id": "ID чата или @username.",
        "text": "Текст сообщения.",
        "topic_id": "(Опционально) ID топика в супергруппе.",
        "silent": "(Опционально) Отправить без звука (True/False).",
        "delay_seconds": "(Опционально) Отложить отправку на N секунд."
    }
)
async def send_message_as_agent(chat_id: str, text: str, topic_id: int = None, silent: bool = False, delay_seconds: int = 0) -> str:
    schedule_date = None
    if delay_seconds > 0:
        # Telethon требует строгий UTC для отложенных сообщений
        schedule_date = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        
    result = await tg_send_message(agent_client, chat_id, text, topic_id, silent, schedule_date)
    
    chat_source = _format_chat_source(chat_id, topic_id)
    delay_str = f" [Отложено на {delay_seconds} сек]" if delay_seconds > 0 else ""
    silent_str = " [Без звука]" if silent else ""
    
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"{silent_str}{delay_str} {text}".strip(), source=chat_source)
    return result

@llm_skill(
    description="Отправляет статус 'Печатает...' или 'Записывает аудио...' в чат (длится ~5 секунд).",
    parameters={
        "chat_id": "ID чата или @username.",
        "action": {"description": "Тип действия", "enum": ["typing", "record-audio"]}
    }
)
async def set_chat_typing_status_as_agent(chat_id: str, action: str = "typing") -> str:
    return await tg_set_typing_status(agent_client, chat_id, action)

@llm_skill(
    description="Покидает Telegram-чат или канал.",
    parameters={"chat_id": "ID чата или @username."}
)
async def leave_chat_as_agent(chat_id: str) -> str:
    return await tg_leave_chat(agent_client, chat_id)

@llm_skill(
    description="Отправляет чат в архив Telegram.",
    parameters={"chat_id": "ID чата или @username."}
)
async def archive_chat_as_agent(chat_id: str) -> str:
    return await tg_archive_chat(agent_client, chat_id)

@llm_skill(
    description="Читает последние сообщения из чата/топика.",
    parameters={
        "chat_id": "ID чата или @username.",
        "limit": "Количество сообщений (по умолчанию 50).",
        "topic_id": "(Опционально) ID топика."
    }
)
async def read_chat_as_agent(chat_id: str, limit: int = 50, topic_id: int = None) -> str:
    return await tg_get_recent_messages(agent_client, chat_id, limit, topic_id)

@llm_skill(
    description="Получает список последних диалогов/групп со статусами прочтения.",
    parameters={"limit": "Количество диалогов (по умолчанию 30)."}
)
async def get_dialogs_as_agent(limit: int = 30) -> str:
    return await tg_get_dialogs(agent_client, limit)

@llm_skill(
    description="Отвечает на конкретное сообщение в чате.",
    parameters={
        "chat_id": "ID чата или @username.",
        "message_id": "ID сообщения, на которое нужно ответить.",
        "text": "Текст ответа."
    }
)
async def reply_to_message_as_agent(chat_id: str, message_id: int, text: str) -> str:
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=text, source=chat_source)
    return await tg_reply_to_message(agent_client, chat_id, message_id, text)

@llm_skill(
    description="Получает последние посты из Telegram-канала.",
    parameters={
        "channel_name": "ID канала или @username.",
        "limit": "Количество постов (по умолчанию 10)."
    }
)
async def get_channel_posts_as_agent(channel_name: str, limit: int = 10) -> str:
    return await tg_get_channel_posts(agent_client, channel_name, limit)

@llm_skill(
    description="Получает полную информацию (Bio, участники) о чате или пользователе.",
    parameters={"chat_id": "ID чата/пользователя или @username."}
)
async def get_chat_info_as_agent(chat_id: str) -> str:
    return await tg_get_chat_info(agent_client, chat_id)

@llm_skill(
    description="Принудительно помечает чат как прочитанный.",
    parameters={"chat_id": "ID чата или @username."}
)
async def mark_chat_as_read_as_agent(chat_id: str) -> str:
    return await tg_mark_as_read(agent_client, chat_id)

@llm_skill(
    description="Ставит эмодзи-реакцию на сообщение.",
    parameters={
        "chat_id": "ID чата или @username.",
        "message_id": "ID сообщения.",
        "emoticon": "Сам эмодзи (например: '👍', '❤️', '🔥')."
    }
)
async def set_message_reaction_as_agent(chat_id: str, message_id: int, emoticon: str) -> str:
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Поставлена реакция {emoticon} на сообщение ID {message_id}]", source=chat_source)
    return await tg_set_reaction(agent_client, chat_id, message_id, emoticon)

@llm_skill(
    description="Ищет публичные каналы и группы в глобальном поиске Telegram.",
    parameters={
        "query": "Поисковый запрос.",
        "limit": "Количество результатов (по умолчанию 5)."
    }
)
async def search_telegram_channels_as_agent(query: str, limit: int = 5) -> str:
    return await tg_search_channels(agent_client, query, limit)

@llm_skill(
    description="Вступает в Telegram-канал или группу по ссылке или юзернейму.",
    parameters={"link_or_username": "Ссылка (t.me/...) или @username."}
)
async def join_telegram_channel_as_agent(link_or_username: str) -> str:
    return await tg_join_channel(agent_client, link_or_username)

@llm_skill(
    description="Оставляет комментарий под постом в канале.",
    parameters={
        "channel_id": "ID канала или @username.",
        "message_id": "ID поста.",
        "text": "Текст комментария."
    }
)
async def comment_on_post_as_agent(channel_id: str, message_id: int, text: str) -> str:
    chat_source = _format_chat_source(channel_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Комментарий к посту {message_id}]: {text}", source=chat_source)
    return await tg_comment_on_post(agent_client, channel_id, message_id, text)

@llm_skill(
    description="Возвращает список чатов ТОЛЬКО с непрочитанными сообщениями."
)
async def get_unread_tg_summary() -> str:
    return await tg_get_unread_chats_summary(agent_client)

@llm_skill(
    description="Удаляет сообщение в чате.",
    parameters={
        "chat_id": "ID чата или @username.",
        "message_id": "ID сообщения для удаления."
    }
)
async def delete_message_as_agent(chat_id: str, message_id: int) -> str:
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Удаление своего сообщения ID {message_id}]", source=chat_source)
    return await tg_delete_message(agent_client, chat_id, message_id)

@llm_skill(
    description="Пересылает сообщение из одного чата в другой.",
    parameters={
        "from_chat": "Откуда переслать (ID или @username).",
        "message_id": "ID сообщения.",
        "to_chat": "Куда переслать (ID или @username)."
    }
)
async def forward_message_as_agent(from_chat: str, message_id: int, to_chat: str) -> str:
    chat_source = _format_chat_source(to_chat)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Пересылка сообщения ID {message_id} из чата {from_chat}]", source=chat_source)
    return await tg_forward_message(agent_client, from_chat, message_id, to_chat)

@llm_skill(
    description="Создает опрос в чате/канале.",
    parameters={
        "chat_id": "ID чата или @username.",
        "question": "Вопрос опроса.",
        "options": "Список вариантов ответов."
    }
)
async def create_poll_as_agent(chat_id: str, question: str, options: list) -> str:
    return await tg_create_poll(agent_client, chat_id, question, options)

@llm_skill(
    description="Читает комментарии к конкретному посту в канале.",
    parameters={
        "channel_name": "ID канала или @username.",
        "message_id": "ID поста.",
        "limit": "Количество комментариев (по умолчанию 20)."
    }
)
async def get_post_comments_as_agent(channel_name: str, message_id: int, limit: int = 20) -> str:
    return await tg_get_post_comments(agent_client, channel_name, message_id, limit)

@llm_skill(
    description="Изменяет раздел 'О себе' (Bio) твоего профиля.",
    parameters={"new_bio": "Новый текст (максимум 70 символов)."}
)
async def change_my_bio_as_agent(new_bio: str) -> str:
    return await tg_change_bio(agent_client, new_bio)

@llm_skill(
    description="Получает текущие результаты опроса.",
    parameters={
        "chat_id": "ID чата или @username.",
        "message_id": "ID сообщения с опросом."
    }
)
async def get_poll_results_as_agent(chat_id: str, message_id: int) -> str:
    return await tg_get_poll_results(agent_client, chat_id, message_id)

@llm_skill(
    description="Банит пользователя в группе/канале ИЛИ добавляет в глобальный ЧС (если chat_id = 'global').",
    parameters={
        "chat_id": "ID чата или 'global'.",
        "user_id": "ID пользователя или @username.",
        "reason": "(Опционально) Причина бана."
    }
)
async def ban_user_as_agent(chat_id: str, user_id: str, reason: str = "Нарушение правил") -> str:
    return await tg_ban_user(agent_client, chat_id, user_id, reason)

@llm_skill(
    description="Добавляет стикерпак в твою коллекцию.",
    parameters={"short_name": "Короткое имя стикерпака или ссылка на него."}
)
async def save_sticker_pack_as_agent(short_name: str) -> str:
    return await tg_save_sticker_set(agent_client, short_name)

@llm_skill(
    description="Разбанивает пользователя.",
    parameters={
        "chat_id": "ID чата или 'global'.",
        "user_id": "ID пользователя или @username."
    }
)
async def unban_user_as_agent(chat_id: str, user_id: str) -> str:
    return await tg_unban_user(agent_client, chat_id, user_id)

@llm_skill(
    description="Возвращает список забаненных пользователей в чате или глобальном ЧС.",
    parameters={
        "chat_id": "ID чата или 'global'.",
        "limit": "Количество пользователей (по умолчанию 50)."
    }
)
async def get_banned_users_as_agent(chat_id: str, limit: int = 50) -> str:
    return await tg_get_banned_users(agent_client, chat_id, limit)

@llm_skill(
    description="Отправляет новый пост в твой Telegram-канал.",
    parameters={
        "channel_id": "ID канала или @username.",
        "text": "Текст поста."
    }
)
async def create_channel_post_as_agent(channel_id: str, text: str) -> str:
    chat_source = _format_chat_source(channel_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Опубликован пост]: {text}", source=chat_source)
    return await tg_create_channel_post(agent_client, channel_id, text)

@llm_skill(
    description="Редактирует отправленное сообщение или пост.",
    parameters={
        "chat_id": "ID чата или @username.",
        "message_id": "ID сообщения.",
        "new_text": "Новый текст сообщения."
    }
)
async def edit_message_as_agent(chat_id: str, message_id: int, new_text: str) -> str:
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Редактирование сообщения ID {message_id}]: {new_text}", source=chat_source)
    return await tg_edit_message(agent_client, chat_id, message_id, new_text)

@llm_skill(
    description="Закрепляет сообщение в чате/канале.",
    parameters={
        "chat_id": "ID чата или @username.",
        "message_id": "ID сообщения для закрепления."
    }
)
async def pin_message_as_agent(chat_id: str, message_id: int) -> str:
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Закрепление сообщения ID {message_id}]", source=chat_source)
    return await tg_pin_message(agent_client, chat_id, message_id)

@llm_skill(
    description="Голосует в опросе.",
    parameters={
        "chat_id": "ID чата или @username.",
        "message_id": "ID сообщения с опросом.",
        "options": "Список вариантов ответов, за которые нужно проголосовать."
    }
)
async def vote_in_poll_as_agent(chat_id: str, message_id: int, options: list) -> str:
    return await tg_vote_in_poll(agent_client, chat_id, message_id, options)

@llm_skill(
    description="Получает список подписчиков канала или группы.",
    parameters={
        "chat_id": "ID чата или @username.",
        "limit": "Количество подписчиков (по умолчанию 50)."
    }
)
async def get_channel_subscribers_as_agent(chat_id: str, limit: int = 50) -> str:
    return await tg_get_channel_subscribers(agent_client, chat_id, limit)

@llm_skill(
    description="Проверяет, есть ли конкретный пользователь в канале/группе.",
    parameters={
        "chat_id": "ID чата или @username.",
        "query": "Имя или юзернейм для поиска."
    }
)
async def check_user_in_chat_as_agent(chat_id: str, query: str) -> str:
    return await tg_check_user_in_chat(agent_client, chat_id, query)

@llm_skill(
    description="Генерирует аудио из текста и отправляет как голосовое сообщение.",
    parameters={
        "chat_id": "ID чата или @username.",
        "text": "Текст для озвучки и отправки."
    }
)
async def send_voice_message_as_agent(chat_id: str, text: str) -> str:
    result = await tg_send_voice_message(agent_client, chat_id, text)
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Голосовое сообщение]: {text}", source=chat_source)
    return result

@llm_skill(
    description="Скачивает медиа (фото, гс, кружок, стикер) из сообщения и возвращает его текстовое описание (Vision/Audio).",
    parameters={
        "chat_id": "ID чата или @username.",
        "message_id": "ID сообщения с медиа."
    }
)
async def get_tg_media_as_agent(chat_id: str, message_id: int) -> dict | str:
    result = await tg_get_media(agent_client, chat_id, message_id)
    return result

@llm_skill(
    description="Отправляет стикер, соответствующий переданному эмодзи.",
    parameters={
        "chat_id": "ID чата или @username.",
        "emoji": "Эмодзи (например, '👍')."
    }
)
async def send_tg_sticker_as_agent(chat_id: str, emoji: str) -> str:
    result = await tg_send_sticker(agent_client, chat_id, emoji)
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Отправлен стикер, соответствующий эмодзи: {emoji}]", source=chat_source)
    return result

@llm_skill(
    description="Меняет аватарку твоего профиля на локальный файл.",
    parameters={"image_path": "Путь к изображению."}
)
async def change_tg_avatar_as_agent(image_path: str) -> str:
    return await tg_change_avatar(agent_client, image_path)

@llm_skill(
    description="Создает новый Telegram-канал.",
    parameters={
        "title": "Название канала.",
        "about": "(Опционально) Описание канала."
    }
)
async def create_telegram_channel_as_agent(title: str, about: str = "") -> str:
    result = await tg_create_channel(agent_client, title, about)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Создан новый канал '{title}']", source="system")
    return result

@llm_skill(
    description="Изменяет название и/или описание канала.",
    parameters={
        "channel_id": "ID канала или @username.",
        "new_title": "(Опционально) Новое название.",
        "new_about": "(Опционально) Новое описание."
    }
)
async def update_channel_info_as_agent(channel_id: str, new_title: str = None, new_about: str = None) -> str:
    return await tg_update_channel_info(agent_client, channel_id, new_title, new_about)

@llm_skill(
    description="Устанавливает публичный юзернейм для канала (делает его публичным).",
    parameters={
        "channel_id": "ID канала.",
        "username": "Желаемый @username."
    }
)
async def set_channel_username_as_agent(channel_id: str, username: str) -> str:
    return await tg_set_channel_username(agent_client, channel_id, username)

@llm_skill(
    description="Выдает пользователю полные права администратора в канале/группе.",
    parameters={
        "channel_id": "ID канала/группы.",
        "user_id": "ID пользователя или @username."
    }
)
async def promote_user_to_admin_as_agent(channel_id: str, user_id: str) -> str:
    return await tg_promote_to_admin(agent_client, channel_id, user_id)

@llm_skill(
    description="Изменяет имя и фамилию твоего аккаунта.",
    parameters={
        "first_name": "Новое имя.",
        "last_name": "(Опционально) Новая фамилия."
    }
)
async def change_account_name_as_agent(first_name: str, last_name: str = "") -> str:
    return await tg_change_account_name(agent_client, first_name, last_name)

@llm_skill(
    description="Изменяет @username твоего аккаунта.",
    parameters={"username": "Новый @username."}
)
async def change_account_username_as_agent(username: str) -> str:
    return await tg_change_account_username(agent_client, username)

@llm_skill(
    description="Создает супергруппу и привязывает её к каналу для комментариев.",
    parameters={
        "channel_id": "ID канала или @username.",
        "group_title": "Название группы для комментариев."
    }
)
async def create_discussion_group_as_agent(channel_id: str, group_title: str) -> str:
    return await tg_create_discussion_group(agent_client, channel_id, group_title)

@llm_skill(
    description="Создает новую супергруппу.",
    parameters={
        "title": "Название супергруппы.",
        "about": "(Опционально) Описание."
    }
)
async def create_supergroup_as_agent(title: str, about: str = "") -> str:
    return await tg_create_supergroup(agent_client, title, about)

@llm_skill(
    description="Приглашает пользователя в группу/канал.",
    parameters={
        "chat_id": "ID чата или @username.",
        "user_id": "ID пользователя или @username."
    }
)
async def invite_user_to_chat_as_agent(chat_id: str, user_id: str) -> str:
    return await tg_invite_to_chat(agent_client, chat_id, user_id)

@llm_skill(
    description="Добавляет пользователя в контакты твоего аккаунта.",
    parameters={
        "user_id": "ID пользователя или @username.",
        "first_name": "Имя контакта.",
        "last_name": "(Опционально) Фамилия контакта."
    }
)
async def add_user_to_contacts_as_agent(user_id: str, first_name: str, last_name: str = "") -> str:
    return await tg_add_to_contacts(agent_client, user_id, first_name, last_name)

@llm_skill(
    description="Получает список администраторов чата/канала.",
    parameters={"chat_id": "ID чата или @username."}
)
async def get_chat_admins_as_agent(chat_id: str) -> str:
    return await tg_get_chat_admins(agent_client, chat_id)

@llm_skill(
    description="Отправляет файл из твоей песочницы в Telegram.",
    parameters={
        "chat_id": "ID чата или @username.",
        "filename": "Имя файла из песочницы.",
        "caption": "(Опционально) Подпись к файлу."
    }
)
async def send_file_to_tg_chat_as_agent(chat_id: str, filename: str, caption: str = "") -> str:
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
    
@llm_skill(
    description="Возвращает чат из архива.",
    parameters={"chat_id": "ID чата или @username."}
)
async def unarchive_tg_chat_as_agent(chat_id: str) -> str:
    return await tg_unarchive_chat(agent_client, chat_id)

@llm_skill(
    description="Ищет сообщения в чате по тексту или автору.",
    parameters={
        "chat_id": "ID чата или @username.",
        "query": "(Опционально) Текст для поиска.",
        "from_user": "(Опционально) ID пользователя или @username.",
        "limit": "Количество результатов (по умолчанию 20)."
    }
)
async def search_chat_messages_as_agent(chat_id: str, query: str = None, from_user: str = None, limit: int = 20) -> str:
    return await tg_search_chat_messages(agent_client, chat_id, query, from_user, limit)

@llm_skill(
    description="Скачивает файл/документ из сообщения Telegram в твою песочницу.",
    parameters={
        "chat_id": "ID чата или @username.",
        "message_id": "ID сообщения с файлом."
    }
)
async def download_file_from_tg_as_agent(chat_id: str, message_id: int) -> str:
    result = await tg_download_file(agent_client, chat_id, message_id)
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Скачивание файла из сообщения ID {message_id}]", source=chat_source)
    return result

@llm_skill(
    description="Меняет аватарку канала на файл из песочницы.",
    parameters={
        "channel_id": "ID канала или @username.",
        "filename": "Имя файла изображения из песочницы."
    }
)
async def change_channel_avatar_as_agent(channel_id: str, filename: str) -> str:
    try:
        clean_filename = os.path.basename(filename.replace("file:///", "").replace("/app/", ""))
        filepath = workspace_manager.get_sandbox_file(clean_filename)
        
        result = await tg_change_channel_avatar(agent_client, channel_id, str(filepath))
        chat_source = _format_chat_source(channel_id)
        await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Обновлена аватарка канала файлом {clean_filename}]", source=chat_source)
        return result
    except Exception as e:
        return f"Ошибка обработки пути к файлу: {e}"