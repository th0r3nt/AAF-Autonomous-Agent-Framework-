from telethon import TelegramClient, events
from config.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events
from src.layer01_datastate.sql_db.management.dialogue import create_dialogue_entry
from telethon.tl.types import UpdateMessageReactions
from telethon import utils

# Кэш для названий топиков: {chat_id: {topic_id: "Название"}}
TOPIC_TITLE_CACHE = {}

TG_AGENT_NICKNAME = config.telegram.agent_nickname

def register_agent_events(client: TelegramClient):
    """Регистрирует события"""

    # Личные сообщения агенту
    @client.on(events.NewMessage(incoming=True))
    async def handle_new_message(event):
        if event.is_private:
            sender = await event.get_sender()
            
            # Игнорируем сервисные аккаунты Telegram (Replies = 708513, Telegram = 777000)
            if sender and getattr(sender, 'id', None) in config.telegram.ignored_users:
                return

            # Проверяем, что лежит в сообщении
            raw_text = event.raw_text or ""
            media_prefix = ""

            if event.sticker:
                # Пытаемся достать эмодзи, привязанный к стикеру
                emoji = event.file.emoji if event.file and hasattr(event.file, 'emoji') else ""
                media_prefix = f"[Стикер {emoji}] "
            elif event.photo:
                media_prefix = "[Фотография] "
            elif event.video:
                media_prefix = "[Видео] "
            elif event.voice:
                media_prefix = "[Голосовое сообщение] "
            elif event.gif:
                media_prefix = "[GIF] "
            elif event.poll:
                media_prefix = "[Опрос] "
            elif event.document:
                media_prefix = "[Вложение/Медиа] "

            # Склеиваем тег медиа и текст (если он есть)
            text = (media_prefix + raw_text).strip()

            if sender and getattr(sender, 'username', None):
                username = sender.username.replace("@", "")
            else:
                username = str(sender.id) if sender else str(event.chat_id)
                
            message_id = event.id
            chat_id = str(event.chat_id) 
            
            chat_source = f"tg_agent_chat_({username})"
            await create_dialogue_entry(actor=f"@{username}", message=text, source=chat_source)
            
            # Передаем chat_id в kwargs
            await event_bus.publish(Events.AGENT_NEW_INCOMING_MESSAGE_TG, username=username, chat_id=chat_id, text=text, chat_source=chat_source, message_id=message_id)

    # Упоминания агента в группах ИЛИ прямые ответы на её сообщения
    @client.on(events.NewMessage(incoming=True))
    async def handle_group_messages(event):
        if not event.is_private:
            me = await client.get_me()
            
            # 1. Встроенная проверка Telegram (ловит и @юзернейм, и прямые реплаи на нас)
            is_mention = getattr(event.message, 'mentioned', False)
            
            # 2. Фоллбэк: проверка по текстовому юзернейму (если встроенная не сработала)
            if not is_mention and TG_AGENT_NICKNAME and f"@{TG_AGENT_NICKNAME}".lower() in event.raw_text.lower():
                is_mention = True
            
            # 3. Фоллбэк: ручная проверка реплая (для 100% гарантии)
            if not is_mention and event.is_reply:
                try:
                    reply_msg = await event.get_reply_message()
                    if reply_msg and reply_msg.sender_id == me.id:
                        is_mention = True
                except Exception:
                    pass
            
            sender = await event.get_sender()
            chat = await event.get_chat()

            # Проверяем, что лежит в сообщении
            raw_text = event.raw_text or ""
            media_prefix = ""

            if event.sticker:
                # Пытаемся достать эмодзи, привязанный к стикеру
                emoji = event.file.emoji if event.file and hasattr(event.file, 'emoji') else ""
                media_prefix = f"[Стикер {emoji}] "
            elif event.photo:
                media_prefix = "[Фотография] "
            elif event.video:
                media_prefix = "[Видео] "
            elif event.voice:
                media_prefix = "[Голосовое сообщение] "
            elif event.gif:
                media_prefix = "[GIF] "
            elif event.poll:
                media_prefix = "[Опрос] "
            elif event.document:
                media_prefix = "[Вложение/Медиа] "

            # Склеиваем тег медиа и текст (если он есть)
            text = (media_prefix + raw_text).strip()

            # Если сообщение отправлено от лица канала/группы (анонимный админ)
            # Иногда sender вообще None, иногда его ID совпадает с ID чата
            if not sender or getattr(sender, 'id', None) == getattr(chat, 'id', None):
                sender = chat

            # Пытаемся достать @username
            if getattr(sender, 'username', None):
                username = sender.username
            else:
                # Если юзернейма нет (или это группа), берем читаемое название
                username = utils.get_display_name(sender)
                if not username:
                    username = str(getattr(sender, 'id', 'Unknown'))

            chat_title = getattr(chat, 'title', 'Unknown Chat')
            
            # Достаем ID чата
            chat_id = str(chat.id)
            if not chat_id.startswith("-100") and getattr(chat, 'megagroup', False):
                chat_id = f"-100{chat_id}"
                
            message_id = event.id

            # Топики + кэширование названий
            topic_id = None
            topic_prefix = ""
            if event.message.reply_to and event.message.reply_to.forum_topic:
                topic_id = event.message.reply_to.reply_to_top_id or event.message.reply_to.reply_to_msg_id
                
                chat_id_int = chat.id
                if chat_id_int not in TOPIC_TITLE_CACHE:
                    TOPIC_TITLE_CACHE[chat_id_int] = {}
                
                # Топик по умолчанию всегда имеет ID 1
                if topic_id == 1:
                    topic_title = "General"
                    TOPIC_TITLE_CACHE[chat_id_int][topic_id] = topic_title
                else:
                    # Ищем в кэше
                    topic_title = TOPIC_TITLE_CACHE[chat_id_int].get(topic_id)
                    
                    # Если в кэше нет, делаем запрос к Telegram
                    if not topic_title:
                        try:
                            # Корневое сообщение топика содержит его название в атрибуте action
                            topic_msg = await client.get_messages(chat, ids=topic_id)
                            if topic_msg and topic_msg.action and hasattr(topic_msg.action, 'title'):
                                topic_title = topic_msg.action.title
                            else:
                                topic_title = "Без названия"
                                
                            # Сохраняем в кэш, чтобы больше не дергать API
                            TOPIC_TITLE_CACHE[chat_id_int][topic_id] = topic_title
                        except Exception:
                            topic_title = "Неизвестный топик"

                topic_prefix = f" [Топик: {topic_title} (ID: {topic_id})]"

            chat_source = f"tg_agent_group_({chat_title}){topic_prefix}"
            
            # Обрезаем длину источника, чтобы SQLAlchemy не падал с DataError (лимит 100 символов)
            if len(chat_source) > 99:
                chat_source = chat_source[:99] + "..."
            
            # Сохраняем в историю диалогов в ЛЮБОМ случае 
            try:
                await create_dialogue_entry(actor=f"@{username}", message=text, source=chat_source)
            except Exception as e:
                system_logger.error(f"[Telegram Events] Ошибка сохранения сообщения из группы в БД: {e}")
            
            # Сохраняем в историю диалогов в ЛЮБОМ случае 
            # ВАЖНО: Если это канал обсуждений, мы тоже это залогируем
            await create_dialogue_entry(actor=f"@{username}", message=text, source=chat_source)

            # --- Теперь распределяем по важности ---
            if is_mention:
                await event_bus.publish(
                    Events.AGENT_NEW_MENTION_TG, 
                    chat_title=chat_title, 
                    chat_id=chat_id, 
                    username=username, 
                    text=text, 
                    chat_source=chat_source, 
                    message_id=message_id
                )
            else:
                # Фоновое чтение для Изолятора и других групп
                await event_bus.publish(
                    Events.AGENT_NEW_GROUP_MESSAGE,
                    chat_title=chat_title,
                    chat_id=chat_id,
                    username=username,
                    text=text,
                    chat_source=chat_source,
                    message_id=message_id
                )

    # Ловим реакции на сообщения
    @client.on(events.Raw)
    async def handle_reactions(event):
        if isinstance(event, UpdateMessageReactions):
            try:
                msg_id = event.msg_id
                peer = event.peer
                
                # Получаем ID чата/юзера
                chat_id = utils.get_peer_id(peer)
                
                # Достаем саму реакцию (берем первую из списка)
                if event.reactions and event.reactions.results:
                    reaction_obj = event.reactions.results[0].reaction
                    emoticon = getattr(reaction_obj, 'emoticon', 'какая-то реакция')
                    
                    chat = await client.get_entity(peer)
                    if getattr(chat, 'title', None):
                        chat_source = f"tg_agent_group_({chat.title})"
                    else:
                        username = getattr(chat, 'username', None)
                        if not username:
                            username = str(chat.id)
                        chat_source = f"tg_agent_chat_({username})"
                    sys_msg = f"[Системное уведомление: На сообщение ID {msg_id} была поставлена реакция: {emoticon}]"
                    
                    await create_dialogue_entry(actor="System", message=sys_msg, source=chat_source)
                    
                    # Публикуем событие на шину
                    await event_bus.publish(
                        Events.AGENT_MESSAGE_REACTION, 
                        chat_id=chat_id, 
                        message_id=msg_id, 
                        emoticon=emoticon
                    )
                    
            except Exception:
                pass # Игнорируем ошибки парсинга сырых ивентов


    # Ловим системные события в чатах (вступление, выход, кик)
    @client.on(events.ChatAction)
    async def handle_chat_actions(event):
        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', 'Unknown Chat')
            chat_source = f"tg_agent_group_({chat_title})"
            
            if event.user_joined or event.user_added:
                users = await event.get_users()
                for user in users:
                    name = getattr(user, 'first_name', 'Unknown')
                    username = f"@{user.username}" if getattr(user, 'username', None) else "без_юзернейма"
                    
                    sys_msg = f"[Системное уведомление: Пользователь {name} ({username}) присоединился к группе]"
                    await create_dialogue_entry(actor="System", message=sys_msg, source=chat_source)
                    
            elif event.user_left or event.user_kicked:
                users = await event.get_users()
                for user in users:
                    name = getattr(user, 'first_name', 'Unknown')
                    username = f"@{user.username}" if getattr(user, 'username', None) else "без_юзернейма"
                    
                    action = "покинул группу" if event.user_left else "был исключен из группы"
                    sys_msg = f"[Системное уведомление: Пользователь {name} ({username}) {action}]"
                    await create_dialogue_entry(actor="System", message=sys_msg, source=chat_source)
                    
        except Exception:
            # Игнорируем ошибки парсинга, чтобы не ронять бота
            pass