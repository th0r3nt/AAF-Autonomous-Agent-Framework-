from datetime import datetime
import random
import asyncio
import os
import re

from telethon import TelegramClient, types, functions, utils
from telethon.tl.functions.messages import SendReactionRequest, InstallStickerSetRequest, GetPeerDialogsRequest, SendVoteRequest, EditChatAboutRequest, SetTypingRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import EditBannedRequest, CreateChannelRequest, EditTitleRequest, EditAdminRequest, UpdateUsernameRequest, EditPhotoRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest, GetBlockedRequest
from telethon.tl.types import ReactionEmoji, ChatBannedRights, InputStickerSetShortName, ChannelParticipantsKicked, InputMediaPoll, Poll, PollAnswer, TextWithEntities, ChannelParticipantsRecent, ChannelParticipantsSearch, ChatAdminRights, SendMessageTypingAction, SendMessageRecordAudioAction, ChannelParticipantsAdmins
from telethon.tl.functions.photos import UploadProfilePhotoRequest

from src.layer00_utils.watchdog.watchdog_decorator import watchdog_decorator
from src.layer00_utils.watchdog.watchdog import userbot_telethon_module
from src.layer00_utils.workspace import workspace_manager
from src.layer00_utils.audio_tools import process_audio_for_llm
from src.layer00_utils.image_tools import compress_and_encode_image
from src.layer02_sensors.pc.voice.tts import tts
from src.layer03_brain.llm.multimodality import describe_image_with_vision_model, transcribe_audio_with_model

def _get_content(msg):
    """Вспомогательная функция для парсинга медиа/текста/пересылок и системных действий"""
    
    # Проверяем, переслано ли сообщение
    fwd_prefix = ""
    if msg.fwd_from:
        if msg.fwd_from.from_name:
            fwd_prefix = f"[Переслано от: {msg.fwd_from.from_name}] "
        else:
            fwd_prefix = "[Переслано] "

    content = ""
    
    # Сначала проверяем системные действия (вступление, выход, закрепление и т.д.)
    if msg.action:
        action_type = type(msg.action).__name__
        if action_type in ['MessageActionChatAddUser', 'MessageActionChatJoinedByLink']:
            content = "[Системное сообщение: Пользователь присоединился к чату]"
        elif action_type == 'MessageActionChatDeleteUser':
            content = "[Системное сообщение: Пользователь покинул чат / был исключен]"
        elif action_type == 'MessageActionPinMessage':
            content = "[Системное сообщение: Сообщение закреплено]"
        else:
            content = f"[Служебное действие: {action_type}]"
            
    # Если это обычное сообщение
    elif msg.text: 
        content = msg.text.replace('\n', ' ')
    elif msg.poll:
        question = getattr(msg.poll.poll.question, 'text', str(msg.poll.poll.question))
        content = f"[Опрос: {question}]"
    elif msg.photo: 
        content = "[Фото]"
    elif msg.video: 
        content = "[Видео]"
    elif msg.voice: 
        content = "[Голосовое сообщение]"
    elif msg.audio: 
        content = "[Аудиозапись]"
    elif msg.sticker: 
        content = "[Стикер]"
    elif msg.gif: 
        content = "[GIF]"
    elif msg.document: 
        content = f"[Файл: {msg.file.name or 'без названия'}]"
    else:
        content = "[Неизвестный формат/Медиа]"
        
    return fwd_prefix + content

@watchdog_decorator(userbot_telethon_module)
async def tg_send_message(client: TelegramClient, chat_id: str | int, text: str, topic_id: int = None, silent: bool = False, schedule_date: datetime = None) -> str:
    """Отправляет сообщение и помечает чат прочитанным"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        msg = await client.send_message(chat_id, text, reply_to=topic_id, silent=silent, schedule=schedule_date)
        
        # Если сообщение отложенное, не помечаем чат прочитанным (мы еще не ответили "здесь и сейчас")
        if not schedule_date:
            await client.send_read_acknowledge(chat_id)
            await client.send_read_acknowledge(chat_id, clear_mentions=True)
            return f"Сообщение успешно отправлено. ID: {msg.id}"
        else:
            return "Сообщение успешно добавлено в отложенные."
    except Exception as e:
        return f"Ошибка отправки: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_reply_to_message(client: TelegramClient, chat_id: str | int, message_id: int, text: str) -> str:
    """Отвечает на конкретное сообщение и помечает чат прочитанным"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        await client.send_message(chat_id, text, reply_to=message_id)
        # Автоматически помечаем прочитанным
        await client.send_read_acknowledge(chat_id) 
        await client.send_read_acknowledge(chat_id, clear_mentions=True)
        return "Ответ успешно отправлен."
    except Exception as e:
        return f"Ошибка ответа: {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_get_recent_messages(client: TelegramClient, chat_id: str | int, limit: int = 50, topic_id: int = None) -> str:
    """Получает историю сообщений чата (или конкретного топика)"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)

    all_messages = []
    try:
        entity = await client.get_input_entity(chat_id)
        dialogs_res = await client(GetPeerDialogsRequest(peers=[entity]))
        
        read_outbox_max_id = 0
        read_inbox_max_id = 0
        if dialogs_res.dialogs:
            read_outbox_max_id = dialogs_res.dialogs[0].read_outbox_max_id
            read_inbox_max_id = dialogs_res.dialogs[0].read_inbox_max_id

        # Добавляем reply_to=topic_id, чтобы читать только конкретную ветку
        async for message in client.iter_messages(chat_id, limit=limit, reply_to=topic_id):
            # Получаем локальную таймзону сервера
            local_tz = datetime.now().astimezone().tzinfo
            msg_time = message.date.astimezone(local_tz).strftime("%H:%M:%S")
            
            # Умное получение имени
            sender = await message.get_sender()
            if not sender:
                sender = await message.get_chat() # Фолбэк, если пишет от имени группы/канала
                
            first_name = utils.get_display_name(sender) if sender else "Unknown"
            username = f"@{sender.username}" if getattr(sender, 'username', None) else "No_Username"

            reply_info = ""
            if message.is_reply:
                reply_id = message.reply_to_msg_id
                reply_msg = await message.get_reply_message()
                
                if reply_msg:
                    orig_sender = await reply_msg.get_sender()
                    if not orig_sender:
                        orig_sender = await reply_msg.get_chat()
                        
                    orig_name = utils.get_display_name(orig_sender) if orig_sender else "Unknown"
                    orig_text = _get_content(reply_msg)
                    
                    # Обрезаем цитату, чтобы не засорять контекст
                    if len(orig_text) > 35:
                        orig_text = orig_text[:32] + "..."
                        
                    reply_info = f" [В ответ на ID {reply_id} от {orig_name}: '{orig_text}']"
                else:
                    # Если оригинальное сообщение удалено или недоступно
                    reply_info = f" [В ответ на недоступное сообщение ID {reply_id}]"
            # ==========================================

            text = _get_content(message)
            
            # Определяем статус прочтения 
            read_status = ""
            if message.out: # Сообщение отправлено агентом
                if message.id <= read_outbox_max_id:
                    read_status = " [Прочитано собеседником]"
                else:
                    read_status = " [Не прочитано собеседником]"
            else: # Сообщение от собеседника
                if message.id <= read_inbox_max_id:
                    read_status = " [Прочитано]"
                else:
                    read_status = " [Новое/Не прочитано]"

            all_messages.append(f"[{msg_time}] ID: {message.id}{read_status} | {first_name} ({username}){reply_info}: {text}")

        all_messages.reverse()
        return "\n".join(all_messages) if all_messages else "Чат пуст."
    except Exception as e:
        return f"Ошибка чтения чата: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_get_dialogs(client: TelegramClient, limit: int = 30) -> str:
    """Получает список последних диалогов/групп со статусами прочтения"""
    all_dialogs = []
    try:
        async for dialog in client.iter_dialogs(limit=limit):
            entity = dialog.entity
            if dialog.is_user:
                chat_type = "Пользователь"
            elif dialog.is_channel:
                chat_type = "Канал" if getattr(entity, 'broadcast', False) else "Супергруппа"
            else:
                chat_type = "Группа"
                
            display_name = getattr(entity, 'first_name', getattr(entity, 'title', dialog.name))
            username = f"@{entity.username}" if getattr(entity, 'username', None) else "No_Link"
            
            # Количество непрочитанных сообщений ОТ собеседника
            unread = f" [Новых сообщений вам: {dialog.unread_count}]" if dialog.unread_count > 0 else ""
            
            # Проверяем, прочитали ли наше последнее сообщение
            outbox_status = ""
            last_msg = dialog.message
            
            read_outbox_max_id = getattr(dialog.dialog, 'read_outbox_max_id', 0)
            
            if last_msg and last_msg.out:
                if last_msg.id <= read_outbox_max_id:
                    outbox_status = " | Ваш последний ответ: прочитан"
                else:
                    outbox_status = " | Ваш последний ответ: не прочитан"
            
            all_dialogs.append(f"ID: {dialog.id} | [{chat_type}] {display_name} ({username}){unread}{outbox_status}")
            
        return "\n".join(all_dialogs)
    except Exception as e:
        return f"Ошибка получения диалогов: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_get_channel_posts(client: TelegramClient, channel_name: str, limit: int = 10) -> str:
    """Получает последние посты из канала с количеством реакций и комментариев + ПОМЕЧАЕТ ПРОЧИТАННЫМ"""
    all_posts = []
    try:
        entity = await client.get_entity(channel_name)
        
        # Получаем сообщения
        messages = []
        async for message in client.iter_messages(entity, limit=limit):
            messages.append(message)
            
            # Получаем локальную таймзону сервера
            local_tz = datetime.now().astimezone().tzinfo
            post_time = message.date.astimezone(local_tz).strftime("%Y-%m-%d %H:%M")
            content = _get_content(message)
            views = f"Просмотры: {message.views}" if message.views is not None else ""
            
            # Считаем комментарии
            replies_cnt = 0
            if message.replies:
                replies_cnt = message.replies.replies
            comments_str = f"Комментарии: {replies_cnt}" if replies_cnt > 0 else ""

            # Считаем реакции
            reactions_str = ""
            if message.reactions and message.reactions.results:
                reacts = []
                for r in message.reactions.results:
                    emoji = getattr(r.reaction, 'emoticon', '?')
                    count = r.count
                    reacts.append(f"{emoji}{count}")
                if reacts:
                    reactions_str = f" {' '.join(reacts)}"

            meta = " | ".join(filter(None, [views, comments_str, reactions_str]))
            all_posts.append(f"[{post_time}] ID: {message.id} | {content}\n   Метрики: {meta}")

        # Помечаем прочитанным
        if messages:
            # Отправляем подтверждение чтения на самое свежее (верхнее) сообщение
            # Telethon автоматически пометит все предыдущие как прочитанные
            await client.send_read_acknowledge(entity, message=messages[0], clear_mentions=True)

        all_posts.reverse()
        return "\n\n".join(all_posts)
    except Exception as e:
        return f"Ошибка чтения канала: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_get_chat_info(client: TelegramClient, chat_id: str | int) -> str:
    """Получает полную информацию (Bio, участники) о чате/юзере"""

    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)

    try:
        entity = await client.get_entity(chat_id)
        if isinstance(entity, types.Channel) or isinstance(entity, types.Chat):
            # Упрощенно для групп/каналов
            return f"Название: {entity.title}, Тип: Группа/Канал, ID: {entity.id}"
        elif isinstance(entity, types.User):
            full_user = await client(functions.users.GetFullUserRequest(id=entity))
            bio = full_user.full_user.about or "Bio отсутствует"
            username = f"@{entity.username}" if entity.username else "No Username"
            return f"Имя: {entity.first_name}, Username: {username}, Bio: {bio}"
    except Exception as e:
        return f"Ошибка получения инфо: {e}"
    

@watchdog_decorator(userbot_telethon_module)
async def tg_mark_as_read(client: TelegramClient, chat_id: str | int) -> str:
    """Принудительно помечает чат как прочитанный"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        await client.send_read_acknowledge(chat_id)
        await client.send_read_acknowledge(chat_id, clear_mentions=True)
        return "Чат успешно помечен как прочитанный."
    except Exception as e:
        return f"Ошибка при пометке прочитанным: {e}"
    

@watchdog_decorator(userbot_telethon_module)
async def tg_set_reaction(client: TelegramClient, chat_id: str | int, message_id: int, emoticon: str) -> str:
    """Ставит реакцию на сообщение"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        await client(SendReactionRequest(
            peer=chat_id,
            msg_id=message_id,
            reaction=[ReactionEmoji(emoticon=emoticon)]
        ))
        return f"Реакция '{emoticon}' успешно поставлена на сообщение ID {message_id}."
    except Exception as e:
        return f"Ошибка установки реакции: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_search_channels(client: TelegramClient, query: str, limit: int = 5) -> str:
    """Ищет публичные каналы и группы в глобальном поиске Telegram с подробной информацией"""
    try:
        # Выполняем глобальный поиск
        result = await client(functions.contacts.SearchRequest(
            q=query,
            limit=limit
        ))
        
        chats =[]
        for chat in result.chats:
            chat_type = "Канал" if getattr(chat, 'broadcast', False) else "Группа"
            username = f"@{chat.username}" if getattr(chat, 'username', None) else "Без_юзернейма"
            title = getattr(chat, 'title', 'Без названия')
            
            # Пытаемся получить описание и количество подписчиков
            about = "Нет описания"
            participants_count = "Неизвестно"
            
            try:
                # Делаем дополнительный запрос на полную информацию о чате
                full_chat = await client(functions.channels.GetFullChannelRequest(channel=chat))
                about = full_chat.full_chat.about or "Нет описания"
                participants_count = full_chat.full_chat.participants_count or "Неизвестно"
            except Exception:
                # Если словили лимит или бан на запрос инфы — просто пропускаем детали
                pass
            
            # Слегка обрезаем описание, чтобы не перегружать контекст LLM
            if len(about) > 150:
                about = about[:147] + "..."
                
            # Собираем красивую строку
            chats.append(
                f"[{chat_type}] {title} ({username}) | ID: {chat.id}\n"
                f"   Подписчиков: {participants_count} | Описание: {about}"
            )
            
        if not chats:
            return f"По запросу '{query}' ничего не найдено."
            
        return "\n\n".join(chats)
    except Exception as e:
        return f"Ошибка при поиске: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_join_channel(client: TelegramClient, link_or_username: str) -> str:
    """Вступает в канал или группу по юзернейму или ссылке"""
    try:
        target = link_or_username.strip()
        
        # Проверяем, является ли это приватной пригласительной ссылкой
        if "t.me/+" in target or "t.me/joinchat/" in target:
            # Вытаскиваем хэш из ссылки
            if "t.me/+" in target:
                invite_hash = target.split("t.me/+")[1].split("/")[0].split("?")[0]
            else:
                invite_hash = target.split("t.me/joinchat/")[1].split("/")[0].split("?")[0]
                
            await client(functions.messages.ImportChatInviteRequest(invite_hash))
            return "Успешное присоединение по приватной ссылке."
            
        else:
            # Это публичный канал/группа (Telethon сам поймет @username или t.me/username)
            await client(functions.channels.JoinChannelRequest(channel=target))
            return f"Успешное присоединение к {target}."
            
    except Exception as e:
        return f"Ошибка при вступлении в канал: {e}"
    

@watchdog_decorator(userbot_telethon_module)
async def tg_comment_on_post(client: TelegramClient, channel_id: str | int, message_id: int, text: str) -> str:
    """Оставляет комментарий под постом в канале"""
    if isinstance(channel_id, str) and channel_id.lstrip('-').isdigit():
        channel_id = int(channel_id)
    try:
        # Магия Telethon: параметр comment_to сам находит привязанную группу и отправляет туда ответ
        msg = await client.send_message(channel_id, text, comment_to=message_id)
        return f"Комментарий успешно оставлен. ID комментария: {msg.id}"
    except Exception as e:
        return f"Ошибка при отправке комментария (возможно, комментарии закрыты или канал не привязан к группе): {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_get_unread_chats_summary(client: TelegramClient, limit: int = 50) -> str:
    """Получает сводку чатов ТОЛЬКО с непрочитанными входящими сообщениями"""
    unread_chats = []
    try:
        async for dialog in client.iter_dialogs(limit=limit):
            # Проверяем только входящие непрочитанные
            if dialog.unread_count > 0:
                entity = dialog.entity

                if dialog.is_user:
                    chat_type = "Пользователь"
                elif dialog.is_channel:
                    chat_type = "Канал" if getattr(entity, 'broadcast', False) else "Супергруппа"
                else:
                    chat_type = "Группа"
                    
                display_name = getattr(entity, 'first_name', getattr(entity, 'title', dialog.name))
                username = f"@{entity.username}" if getattr(entity, 'username', None) else "без_юзернейма"
                
                status_str = f"Новых: {dialog.unread_count}"
                
                unread_chats.append(f"- [{chat_type}] {display_name} ({username}) | ID: {dialog.id} | {status_str}")
                
        return "\n".join(unread_chats) if unread_chats else "Нет непрочитанных сообщений."
    except Exception as e:
        return f"Ошибка получения непрочитанных: {e}"
    

@watchdog_decorator(userbot_telethon_module)
async def tg_delete_message(client: TelegramClient, chat_id: str | int, message_id: int) -> str:
    """Удаляет сообщение"""
    try:
        if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit(): 
            chat_id = int(chat_id)
        await client.delete_messages(chat_id, [message_id])
        return f"Сообщение ID {message_id} успешно удалено."
    except Exception as e:
        return f"Ошибка при удалении сообщения: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_forward_message(client: TelegramClient, from_chat: str | int, message_id: int, to_chat: str | int) -> str:
    """Пересылает сообщение из одного чата в другой"""
    try:
        if isinstance(from_chat, str) and from_chat.lstrip('-').isdigit(): 
            from_chat = int(from_chat)
        if isinstance(to_chat, str) and to_chat.lstrip('-').isdigit(): 
            to_chat = int(to_chat)
        
        msg = await client.forward_messages(to_chat, messages=message_id, from_peer=from_chat)
        return f"Сообщение успешно переслано. Новый ID в целевом чате: {msg.id}"
    except Exception as e:
        return f"Ошибка при пересылке: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_create_poll(client: TelegramClient, chat_id: str | int, question: str, options: list) -> str:
    """Создает опрос в чате/канале"""
    try:
        if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit(): 
            chat_id = int(chat_id)
        
        # Telethon требует строгую кодировку байтов для опций
        answers = [
            PollAnswer(
                text=TextWithEntities(text=str(opt), entities=[]), 
                option=str(i).encode('utf-8') 
            ) for i, opt in enumerate(options)
        ]
        
        poll_media = InputMediaPoll(
            poll=Poll(
                id=random.getrandbits(62), # Исправлено: ID должен быть большим 64-битным числом
                question=TextWithEntities(text=question, entities=[]),
                answers=answers,
                closed=False,
                multiple_choice=False,
                quiz=False
            )
        )
        msg = await client.send_message(chat_id, file=poll_media)
        return f"Опрос '{question}' успешно создан. ID сообщения: {msg.id}"
    except Exception as e:
        return f"Ошибка при создании опроса: {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_get_post_comments(client: TelegramClient, channel_name: str, message_id: int, limit: int = 20) -> str:
    """Читает комментарии к конкретному посту"""
    comments = []
    try:
        entity = await client.get_entity(channel_name)
        async for message in client.iter_messages(entity, reply_to=message_id, limit=limit):
            
            # Умное получение имени
            sender = await message.get_sender()
            if not sender:
                sender = await message.get_chat()
                
            name = utils.get_display_name(sender) if sender else "Unknown"
            username = f"@{sender.username}" if getattr(sender, 'username', None) else ""
            
            text = _get_content(message)
            
            # ВАЖНО: Добавили вывод Chat ID группы обсуждений
            comments.append(f"Chat ID: {message.chat_id} | Msg ID: {message.id} | {name} ({username}): {text}")
        
        comments.reverse()
        return "\n".join(comments) if comments else "Комментариев пока нет."
    except Exception as e:
        return f"Ошибка чтения комментариев: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_change_bio(client: TelegramClient, new_bio: str) -> str:
    """Меняет раздел 'О себе' в профиле"""
    try:
        # Лимит Телеграма — 70 символов
        if len(new_bio) > 70:
            return f"Ошибка: Bio слишком длинное ({len(new_bio)} символов). Максимум 70."
        
        await client(UpdateProfileRequest(about=new_bio))
        return f"Статус (Bio) успешно изменен на: '{new_bio}'"
    except Exception as e:
        return f"Ошибка смены Bio: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_get_poll_results(client: TelegramClient, chat_id: str | int, message_id: int) -> str:
    """Получает результаты опроса"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        messages = await client.get_messages(chat_id, ids=[message_id])
        if not messages:
            return "Сообщение не найдено."
            
        message = messages[0]
        
        if not message or not getattr(message, 'poll', None):
            return "Сообщение не найдено или это не опрос."

        # Приводим время публикации сообщения из UTC к локальному времени сервера
        msg_time = message.date.astimezone().strftime("%Y-%m-%d %H:%M:%S")

        poll = message.poll.poll
        results = message.poll.results
        
        # Извлекаем текст вопроса (защита от объекта TextWithEntities)
        question_text = getattr(poll.question, 'text', str(poll.question))
        
        # Надежная проверка на количество голосов
        total_voters = getattr(results, 'total_voters', 0)
        
        if not results or total_voters == 0:
            return f"[{msg_time}] Опрос '{question_text}'. Голосов пока нет."

        summary = [f"[{msg_time}] Опрос: {question_text}\nВсего голосов: {total_voters}\nРезультаты:"]
        
        votes_map = {}
        if getattr(results, 'results', None):
            votes_map = {r.option: r.voters for r in results.results}
        
        for answer in poll.answers:
            # Извлекаем текст ответа (защита от объекта TextWithEntities)
            answer_text = getattr(answer.text, 'text', str(answer.text))
            count = votes_map.get(answer.option, 0)
            
            percent = 0
            if total_voters > 0:
                percent = round((count / total_voters) * 100, 1)
            summary.append(f"- {answer_text}: {count} ({percent}%)")
            
        return "\n".join(summary)
    except Exception as e:
        return f"Ошибка получения результатов опроса: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_ban_user(client: TelegramClient, chat_id: str | int, user_id: str | int, reason: str = "Ban") -> str:
    """Банит пользователя в группе/канале ИЛИ глобально в личных сообщениях"""
    try:
        # Если передали строку из цифр, конвертируем в int
        if isinstance(user_id, str) and user_id.lstrip('-').isdigit():
            user_id = int(user_id)
            
        try:
            user = await client.get_entity(user_id)
        except ValueError:
            return f"Ошибка Telethon: Невозможно найти пользователя по сырому ID '{user_id}', так как он не закэширован. Вызовите функцию снова, передав его @username."
        
        # Если передан 'global', 'me' или ID совпадает с юзером - это глобальный блок (ЧС)
        if str(chat_id).lower() in ["global", "me", "личные", "pm"] or str(chat_id) == str(user_id):
            await client(BlockRequest(id=user))
            return f"Пользователь {user.id} успешно добавлен в глобальный черный список (ЧС)."

        # Иначе это бан в группе
        if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
            chat_id = int(chat_id)
            
        rights = ChatBannedRights(
            until_date=None, view_messages=True, send_messages=True, 
            send_media=True, send_stickers=True, send_gifs=True, 
            send_games=True, send_inline=True, embed_links=True
        )
        
        await client(EditBannedRequest(channel=chat_id, participant=user, banned_rights=rights))
        return f"Пользователь {user.id} успешно забанен в чате {chat_id}. Причина: {reason}"
    except Exception as e:
        return f"Ошибка при бане пользователя: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_save_sticker_set(client: TelegramClient, stickerset_shortname: str) -> str:
    """Добавляет стикерпак к себе в коллекцию"""
    try:
        # stickerset_shortname это часть ссылки t.me/addstickers/ShortName
        # Если передали ссылку, пробуем вырезать имя
        if "addstickers/" in stickerset_shortname:
            stickerset_shortname = stickerset_shortname.split("addstickers/")[1].split("/")[0]

        await client(InstallStickerSetRequest(
            stickerset=InputStickerSetShortName(short_name=stickerset_shortname),
            archived=False
        ))
        return f"Стикерпак '{stickerset_shortname}' успешно добавлен в вашу коллекцию."
    except Exception as e:
        return f"Ошибка добавления стикерпака: {e}"
    

@watchdog_decorator(userbot_telethon_module)
async def tg_unban_user(client: TelegramClient, chat_id: str | int, user_id: str | int) -> str:
    """Разбанивает пользователя в группе ИЛИ вытаскивает из глобального ЧС"""
    try:
        user = await client.get_entity(user_id)
        
        # Глобальный разбан
        if str(chat_id).lower() in ["global", "me", "личные", "pm"] or str(chat_id) == str(user_id):
            await client(UnblockRequest(id=user))
            return f"Пользователь {user.id} успешно удален из глобального черного списка."

        # Разбан в группе
        if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
            chat_id = int(chat_id)
            
        rights = ChatBannedRights(until_date=None)
        await client(EditBannedRequest(channel=chat_id, participant=user, banned_rights=rights))
        return f"Пользователь {user.id} успешно разбанен в чате {chat_id}."
    except Exception as e:
        return f"Ошибка при разбане пользователя: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_get_banned_users(client: TelegramClient, chat_id: str | int, limit: int = 50) -> str:
    """Возвращает список забаненных пользователей в чате/канале ИЛИ глобальном ЧС"""
    try:
        banned_list = []
        
        # Проверка на глобальный ЧС
        if str(chat_id).lower() in ["global", "me", "личные", "pm"]:
            result = await client(GetBlockedRequest(offset=0, limit=limit))
            for user in result.users:
                name = getattr(user, 'first_name', 'Unknown')
                username = f"@{user.username}" if getattr(user, 'username', None) else "No_username"
                banned_list.append(f"- ID: {user.id} | {name} ({username})")
                
            if not banned_list:
                return "Глобальный черный список пуст."
            return "Глобальный ЧС (заблокированные пользователи):\n" + "\n".join(banned_list)

        # Иначе это бан-лист чата/канала
        if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
            chat_id = int(chat_id)
            
        async for user in client.iter_participants(chat_id, filter=ChannelParticipantsKicked, limit=limit):
            name = getattr(user, 'first_name', 'Unknown')
            username = f"@{user.username}" if getattr(user, 'username', None) else "No_username"
            banned_list.append(f"- ID: {user.id} | {name} ({username})")
            
        if not banned_list:
            return "Список забаненных в чате пуст."
            
        return f"Забаненные пользователи в чате {chat_id}:\n" + "\n".join(banned_list)
    except Exception as e:
        return f"Ошибка при получении списка забаненных пользователей: {e}"


@watchdog_decorator(userbot_telethon_module)
async def tg_create_channel_post(client: TelegramClient, channel_id: str | int, text: str) -> str:
    """Отправляет новый пост в Telegram-канал (требуются права администратора)"""
    if isinstance(channel_id, str) and channel_id.lstrip('-').isdigit():
        channel_id = int(channel_id)
    try:
        msg = await client.send_message(channel_id, text)
        return f"Пост успешно опубликован в канале. ID поста: {msg.id}"
    except Exception as e:
        return f"Ошибка публикации поста: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_edit_message(client: TelegramClient, chat_id: str | int, message_id: int, new_text: str) -> str:
    """Редактирует сообщение/пост"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        await client.edit_message(chat_id, message_id, new_text)
        return f"Сообщение ID {message_id} успешно отредактировано."
    except Exception as e:
        return f"Ошибка редактирования: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_pin_message(client: TelegramClient, chat_id: str | int, message_id: int) -> str:
    """Закрепляет сообщение в чате/канале"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        await client.pin_message(chat_id, message_id, notify=True)
        return f"Сообщение ID {message_id} успешно закреплено."
    except Exception as e:
        return f"Ошибка закрепления: {e}"
    

@watchdog_decorator(userbot_telethon_module)
async def tg_vote_in_poll(client: TelegramClient, chat_id: str | int, message_id: int, options: list) -> str:
    """Голосует в опросе. options - список байтовых строк или обычных строк (вариантов ответа)"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        # Telethon требует, чтобы отправляемые опции были в байтах (b'0', b'1' и т.д.)
        # Но для удобства LLM мы разрешаем ей передавать текст ответа или индекс, а под капотом конвертируем.
        
        # Получаем сам опрос, чтобы понять, какие байты соответствуют каким ответам
        messages = await client.get_messages(chat_id, ids=[message_id])
        if not messages or not messages[0].poll:
            return "Ошибка: Сообщение не найдено или это не опрос."
            
        poll_answers = messages[0].poll.poll.answers
        
        # Собираем байты, которые нужно отправить
        options_to_send = []
        for opt in options:
            opt_str = str(opt)
            # Ищем совпадение по тексту ответа
            for answer in poll_answers:
                answer_text = getattr(answer.text, 'text', str(answer.text))
                if opt_str.lower() in answer_text.lower():
                    options_to_send.append(answer.option)
                    break
            else:
                # Если текст не совпал, возможно LLM передала просто номер варианта (0, 1, 2)
                if opt_str.isdigit() and int(opt_str) < len(poll_answers):
                    options_to_send.append(poll_answers[int(opt_str)].option)

        if not options_to_send:
            return f"Ошибка: Не удалось найти вариант ответа '{options}' в опросе."

        await client(SendVoteRequest(
            peer=chat_id,
            msg_id=message_id,
            options=options_to_send
        ))
        return f"Голос за вариант(ы) '{options}' успешно отправлен."
    except Exception as e:
        return f"Ошибка при голосовании: {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_get_channel_subscribers(client: TelegramClient, chat_id: str | int, limit: int = 50) -> str:
    """Получает список подписчиков канала или группы (если есть права)"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
        
    try:
        subscribers = []
        # iter_participants по умолчанию вернет недавних участников
        async for user in client.iter_participants(chat_id, limit=limit, filter=ChannelParticipantsRecent):
            name = getattr(user, 'first_name', 'Unknown')
            username = f"@{user.username}" if getattr(user, 'username', None) else "без_юзернейма"
            subscribers.append(f"- ID: {user.id} | {name} ({username})")
            
        if not subscribers:
            return f"Список пуст или нет прав на просмотр участников в чате {chat_id}."
            
        return f"Список подписчиков (показано {len(subscribers)}):\n" + "\n".join(subscribers)
    except Exception as e:
        return f"Ошибка при получении подписчиков (возможно, вы не админ или участники скрыты): {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_check_user_in_chat(client: TelegramClient, chat_id: str | int, query: str) -> str:
    """Проверяет, есть ли конкретный пользователь в канале/группе (по ID, имени или @username)"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
        
    try:
        # Используем встроенный поиск Telethon по участникам
        # Он ищет по имени и юзернейму
        found_users = []
        async for user in client.iter_participants(chat_id, search=query, filter=ChannelParticipantsSearch):
            name = getattr(user, 'first_name', 'Unknown')
            username = f"@{user.username}" if getattr(user, 'username', None) else "без_юзернейма"
            found_users.append(f"ID: {user.id} | {name} ({username})")
            
        if not found_users:
            return f"Пользователь по запросу '{query}' не найден в чате {chat_id}."
            
        return f"Найдены совпадения по запросу '{query}':\n" + "\n".join(found_users)
    except Exception as e:
        return f"Ошибка при поиске пользователя: {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_send_voice_message(client: TelegramClient, chat_id: str | int, text: str) -> str:
    """Генерирует аудио и отправляет как голосовое сообщение"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        # 1. Генерируем аудиофайл во временной папке
        audio_path = await tts.generate_audio_file(text)
        
        # 2. Отправляем файл как voice_note
        msg = await client.send_file(
            chat_id, 
            file=audio_path, 
            voice_note=True
        )
        await client.send_read_acknowledge(chat_id, clear_mentions=True)
        return f"Голосовое сообщение успешно сгенерировано и отправлено. ID: {msg.id}"
    except Exception as e:
        return f"Ошибка при отправке голосового сообщения: {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_get_media(client: TelegramClient, chat_id: str | int, message_id: int) -> str:
    """Универсальный загрузчик: фото, ГС, кружочки, стикеры, миниатюры видео"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
        
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
            
            # ВМЕСТО СЛОВАРЯ ВЫЗЫВАЕМ СОПРОЦЕССОР
            description = await describe_image_with_vision_model(b64_string)
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
                    description = await describe_image_with_vision_model(b64_string)
                    return description
                else:
                    return "Не удалось извлечь изображение или миниатюру из файла."
                    
            return f"Это файл/документ: {msg.file.name}. Это НЕ медиа. Используйте сооветствующий инструмент для скачивания файлов/документов."

        # 3. Голосовые сообщения (Пока возвращаем заглушку, чтобы не крашить текстовые модели)
        elif msg.voice or msg.video_note:
            temp_path = workspace_manager.get_temp_file(prefix="audio_", extension=".ogg")
            await client.download_media(msg, file=str(temp_path))
            
            # Конвертируем ogg в mp3 base64 с помощью твоей готовой утилиты
            b64_data = await asyncio.to_thread(process_audio_for_llm, str(temp_path))
            
            # Отправляем в сопроцессор!
            transcription = await transcribe_audio_with_model(b64_data)
            return transcription
            
        return "Неизвестный тип медиа."
        
    except Exception as e:
        return f"Ошибка при получении медиа: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_send_sticker(client: TelegramClient, chat_id: str | int, emoji: str) -> str:
    """Отправляет стикер через встроенного инлайн-бота @sticker"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        # Используем официального инлайн-бота Telegram для подбора стикера по эмодзи
        results = await client.inline_query('sticker', emoji)
        if results:
            # Отправляем первый попавшийся подходящий стикер
            msg = await results[0].click(chat_id)
            await client.send_read_acknowledge(chat_id, clear_mentions=True)
            return f"Стикер для эмодзи '{emoji}' успешно отправлен. ID: {msg.id}"
        else:
            return f"Не удалось найти стикер для эмодзи '{emoji}'."
    except Exception as e:
        return f"Ошибка при отправке стикера: {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_change_avatar(client: TelegramClient, image_path: str) -> str:
    """Меняет аватарку профиля"""
    try:
        if not os.path.exists(image_path):
            return f"Ошибка: Файл изображения '{image_path}' не найден."
            
        # Telethon сам загрузит файл на сервер и поставит на аватарку
        file = await client.upload_file(image_path)
        await client(UploadProfilePhotoRequest(file=file))
        
        return "Аватарка профиля успешно обновлена."
    except Exception as e:
        return f"Ошибка при обновлении аватарки: {e}"
        

@watchdog_decorator(userbot_telethon_module)
async def tg_create_channel(client: TelegramClient, title: str, about: str = "") -> str:
    """Создает новый Telegram-канал и возвращает его ID"""
    try:
        # megagroup=False означает, что это именно канал (broadcasting), а не группа
        result = await client(CreateChannelRequest(
            title=title,
            about=about,
            megagroup=False
        ))
        
        # Вытаскиваем ID созданного канала из ответа
        channel_id = result.chats[0].id
        return f"Канал '{title}' успешно создан. Его внутренний ID: {channel_id}. Сохраните этот ID для дальнейшей настройки."
    except Exception as e:
        return f"Ошибка при создании канала: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_update_channel_info(client: TelegramClient, channel_id: str | int, new_title: str = None, new_about: str = None) -> str:
    """Изменяет название и/или описание канала"""
    if isinstance(channel_id, str) and channel_id.lstrip('-').isdigit():
        channel_id = int(channel_id)
    try:
        entity = await client.get_input_entity(channel_id)
        
        res_msg = []
        if new_title:
            await client(EditTitleRequest(channel=entity, title=new_title))
            res_msg.append("Название обновлено.")
        if new_about:
            await client(EditChatAboutRequest(peer=entity, about=new_about))
            res_msg.append("Описание обновлено.")
            
        return " ".join(res_msg) if res_msg else "Нет данных для обновления."
    except Exception as e:
        return f"Ошибка при обновлении информации канала: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_set_channel_username(client: TelegramClient, channel_id: str | int, username: str) -> str:
    """Делает канал публичным, устанавливая ему @username"""
    if isinstance(channel_id, str) and channel_id.lstrip('-').isdigit():
        channel_id = int(channel_id)
    try:
        entity = await client.get_input_entity(channel_id)
        clean_username = username.replace("@", "")
        
        await client(UpdateUsernameRequest(channel=entity, username=clean_username))
        return f"Канал успешно стал публичным. Ссылка: t.me/{clean_username}"
    except Exception as e:
        return f"Ошибка установки юзернейма (возможно, он занят или недопустим): {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_promote_to_admin(client: TelegramClient, channel_id: str | int, user_id: str | int) -> str:
    """Выдает пользователю полные права администратора в канале"""
    if isinstance(channel_id, str) and channel_id.lstrip('-').isdigit():
        channel_id = int(channel_id)
    try:
        channel_entity = await client.get_input_entity(channel_id)
        
        # Если передали строку (например @th0r3nt)
        if isinstance(user_id, str) and not user_id.lstrip('-').isdigit():
            user_entity = await client.get_input_entity(user_id)
        else:
            user_entity = await client.get_input_entity(int(user_id))

        # Выдаем максимальные права (как у создателя, кроме удаления самого канала)
        rights = ChatAdminRights(
            change_info=True, post_messages=True, edit_messages=True,
            delete_messages=True, ban_users=True, invite_users=True,
            pin_messages=True, add_admins=True, anonymous=False,
            manage_call=True
        )
        
        await client(EditAdminRequest(
            channel=channel_entity,
            user_id=user_entity,
            admin_rights=rights,
            rank="Creator's Proxy" # Кастомная плашка админа
        ))
        return f"Пользователь {user_id} успешно назначен администратором с полными правами."
    except Exception as e:
        return f"Ошибка выдачи прав администратора: {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_change_account_name(client: TelegramClient, first_name: str, last_name: str = "") -> str:
    """Меняет имя и фамилию профиля"""
    try:
        await client(UpdateProfileRequest(first_name=first_name, last_name=last_name))
        return f"Имя профиля успешно изменено на: {first_name} {last_name}"
    except Exception as e:
        return f"Ошибка при смене имени: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_change_account_username(client: TelegramClient, username: str) -> str:
    """Меняет @username профиля"""
    try:
        clean_username = username.replace("@", "")
        await client(UpdateUsernameRequest(username=clean_username))
        return f"Юзернейм успешно изменен на: @{clean_username}"
    except Exception as e:
        return f"Ошибка при смене юзернейма (возможно, он занят или недопустим): {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_create_discussion_group(client: TelegramClient, channel_id: str | int, group_title: str) -> str:
    """Создает супергруппу и привязывает её к каналу как чат для комментариев"""
    if isinstance(channel_id, str) and channel_id.lstrip('-').isdigit():
        channel_id = int(channel_id)
    try:
        channel_entity = await client.get_input_entity(channel_id)
        
        # 1. Создаем супергруппу (megagroup=True)
        created_group = await client(functions.channels.CreateChannelRequest(
            title=group_title,
            about="Группа для обсуждений",
            megagroup=True
        ))
        group_id = created_group.chats[0].id
        group_entity = await client.get_input_entity(group_id)
        
        # 2. Привязываем супергруппу к каналу
        await client(functions.channels.SetDiscussionGroupRequest(
            broadcast=channel_entity,
            group=group_entity
        ))
        return f"Группа обсуждений '{group_title}' успешно создана и привязана к каналу. ID группы: {group_id}"
    except Exception as e:
        return f"Ошибка при создании группы обсуждений: {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_set_typing_status(client: TelegramClient, chat_id: str | int, action: str = "typing") -> str:
    """Отправляет статус 'Печатает...' или 'Записывает аудио...' (длится ~5 секунд)"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        peer = await client.get_input_entity(chat_id)
        typing_action = SendMessageRecordAudioAction() if action == "record-audio" else SendMessageTypingAction()
        await client(SetTypingRequest(peer=peer, action=typing_action))
        return f"Статус '{action}' успешно отправлен в чат."
    except Exception as e:
        return f"Ошибка отправки статуса: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_leave_chat(client: TelegramClient, chat_id: str | int) -> str:
    """Выходит из канала или группы"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        entity = await client.get_input_entity(chat_id)
        await client(functions.channels.LeaveChannelRequest(channel=entity))
        return "Успешно покинули чат/канал."
    except Exception as e:
        # Fallback для обычных групп (не супергрупп)
        try:
            await client(functions.messages.DeleteChatUserRequest(chat_id=chat_id, user_id='me'))
            return "Успешно покинули базовую группу."
        except Exception as e2:
            return f"Ошибка при выходе из чата: {e} | {e2}"

@watchdog_decorator(userbot_telethon_module)
async def tg_archive_chat(client: TelegramClient, chat_id: str | int) -> str:
    """Отправляет чат в архив"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        entity = await client.get_input_entity(chat_id)
        # folder_id=1 это Архив
        await client(functions.folders.EditPeerFoldersRequest(
            folder_peers=[types.InputFolderPeer(peer=entity, folder_id=1)]
        ))
        return "Чат успешно отправлен в архив."
    except Exception as e:
        return f"Ошибка при архивации чата: {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_create_supergroup(client: TelegramClient, title: str, about: str = "") -> str:
    """Создает новую супергруппу (полноценный чат с историей)"""
    try:
        # В Telegram современные группы - это megagroup=True
        result = await client(functions.channels.CreateChannelRequest(
            title=title,
            about=about,
            megagroup=True
        ))
        group_id = result.chats[0].id
        return f"Группа '{title}' успешно создана. ID: {group_id}"
    except Exception as e:
        return f"Ошибка при создании группы: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_invite_to_chat(client: TelegramClient, chat_id: str | int, user_id: str | int) -> str:
    """Приглашает пользователя в группу/канал"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        chat_entity = await client.get_input_entity(chat_id)
        
        # Если передали строку
        if isinstance(user_id, str) and not user_id.lstrip('-').isdigit():
            user_entity = await client.get_input_entity(user_id)
        else:
            user_entity = await client.get_input_entity(int(user_id))

        await client(functions.channels.InviteToChannelRequest(
            channel=chat_entity,
            users=[user_entity]
        ))
        return f"Пользователь {user_id} успешно приглашен в чат {chat_id}."
    except Exception as e:
        return f"Ошибка при приглашении: {e} (Возможно, у пользователя закрыты приглашения в настройках приватности)"

@watchdog_decorator(userbot_telethon_module)
async def tg_add_to_contacts(client: TelegramClient, user_id: str | int, first_name: str, last_name: str = "") -> str:
    """Добавляет пользователя в контакты аккаунта"""
    try:
        if isinstance(user_id, str) and not user_id.lstrip('-').isdigit():
            user_entity = await client.get_input_entity(user_id)
        else:
            user_entity = await client.get_input_entity(int(user_id))
            
        await client(functions.contacts.AddContactRequest(
            id=user_entity,
            first_name=first_name,
            last_name=last_name,
            phone="", # Можно добавить без телефона, если мы с ним уже общались
            add_phone_privacy_exception=False
        ))
        return f"Пользователь {user_id} успешно добавлен в контакты как '{first_name} {last_name}'."
    except Exception as e:
        return f"Ошибка при добавлении в контакты: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_get_chat_admins(client: TelegramClient, chat_id: str | int) -> str:
    """Получает список администраторов чата/канала"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        admins = []
        # Фильтруем только админов
        async for admin in client.iter_participants(chat_id, filter=ChannelParticipantsAdmins):
            name = getattr(admin, 'first_name', 'Unknown')
            username = f"@{admin.username}" if getattr(admin, 'username', None) else "без_юзернейма"
            admins.append(f"- ID: {admin.id} | {name} ({username})")
            
        if not admins:
            return f"Не удалось найти администраторов в чате {chat_id}."
            
        return f"Список администраторов чата {chat_id}:\n" + "\n".join(admins)
    except Exception as e:
        return f"Ошибка при получении списка администраторов: {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_send_file(client: TelegramClient, chat_id: str | int, file_path: str, caption: str = "") -> str:
    """Отправляет локальный файл как документ в Telegram"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        msg = await client.send_file(chat_id, file=file_path, caption=caption)
        await client.send_read_acknowledge(chat_id, clear_mentions=True)
        return f"Файл успешно отправлен. ID сообщения: {msg.id}"
    except Exception as e:
        return f"Ошибка при отправке файла: {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_unarchive_chat(client: TelegramClient, chat_id: str | int) -> str:
    """Возвращает чат из архива в основной список диалогов"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
    try:
        entity = await client.get_input_entity(chat_id)
        # folder_id=0 — это основной список диалогов
        await client(functions.folders.EditPeerFoldersRequest(
            folder_peers=[types.InputFolderPeer(peer=entity, folder_id=0)]
        ))
        return "Чат успешно возвращен из архива."
    except Exception as e:
        return f"Ошибка при возврате чата из архива: {e}"
    
@watchdog_decorator(userbot_telethon_module)
async def tg_search_chat_messages(client: TelegramClient, chat_id: str | int, query: str = None, from_user: str | int = None, limit: int = 20) -> str:
    """Ищет сообщения в чате по тексту или от конкретного пользователя"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
        
    try:
        # Если передан from_user как строка из цифр, преобразуем в int
        if isinstance(from_user, str) and from_user.lstrip('-').isdigit():
            from_user = int(from_user)
            
        all_messages = []
        
        # Telethon сам поддерживает фильтрацию по search и from_user на стороне серверов ТГ
        async for message in client.iter_messages(chat_id, search=query, from_user=from_user, limit=limit):
            local_tz = datetime.now().astimezone().tzinfo
            msg_time = message.date.astimezone(local_tz).strftime("%Y-%m-%d %H:%M:%S")
            
            sender = await message.get_sender()
            if not sender:
                sender = await message.get_chat()
                
            first_name = utils.get_display_name(sender) if sender else "Unknown"
            username = f"@{sender.username}" if getattr(sender, 'username', None) else "No_Username"
            
            text = _get_content(message)
            
            all_messages.append(f"[{msg_time}] ID: {message.id} | {first_name} ({username}): {text}")
            
        all_messages.reverse() # Старые сверху, новые снизу
        
        if not all_messages:
            return "По вашему запросу ничего не найдено."
            
        return "Найденные сообщения:\n" + "\n".join(all_messages)
    except Exception as e:
        return f"Ошибка поиска сообщений: {e}"
    

@watchdog_decorator(userbot_telethon_module)
async def tg_download_file(client: TelegramClient, chat_id: str | int, message_id: int) -> str:
    """Скачивает файл из сообщения в песочницу"""
    if isinstance(chat_id, str) and chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)
        
    try:
        messages = await client.get_messages(chat_id, ids=[message_id])
        if not messages or not messages[0].media:
            return "Ошибка: Сообщение не найдено или не содержит медиа/файлов."
        
        msg = messages[0]
        
        # Пытаемся получить оригинальное имя файла
        filename = "downloaded_file"
        if msg.document:
            for attr in msg.document.attributes:
                if isinstance(attr, types.DocumentAttributeFilename):
                    filename = attr.file_name
                    break
                    
        # Очищаем имя файла от опасных символов (защита)
        clean_filename = re.sub(r'[\\/*?:"<>|]', "", filename)
        if not clean_filename:
            clean_filename = f"file_{message_id}.bin"
            
        target_path = workspace_manager.get_sandbox_file(clean_filename)
        
        await client.download_media(msg, file=str(target_path))
        return f"Файл '{clean_filename}' успешно скачан в песочницу."
        
    except Exception as e:
        return f"Ошибка при скачивании файла: {e}"

@watchdog_decorator(userbot_telethon_module)
async def tg_change_channel_avatar(client: TelegramClient, channel_id: str | int, image_path: str) -> str:
    """Меняет аватарку канала"""
    if isinstance(channel_id, str) and channel_id.lstrip('-').isdigit():
        channel_id = int(channel_id)
    try:
        if not os.path.exists(image_path):
            return f"Ошибка: Файл '{image_path}' не найден."
            
        entity = await client.get_input_entity(channel_id)
        uploaded_photo = await client.upload_file(image_path)
        
        await client(EditPhotoRequest(
            channel=entity,
            photo=uploaded_photo
        ))
        return "Аватарка канала успешно обновлена."
    except Exception as e:
        return f"Ошибка при обновлении аватарки канала (возможно, нет прав администратора): {e}"