import datetime
from cachetools import LRUCache
from telethon import events, utils
from telethon.tl.types import UpdateMessageReactions, User, Chat, Channel
from typing import List

from src.l03_interfaces.type.telegram.telethon.client import TelethonClient
from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.event.registry import Events


class TelethonEvents:
    """
    Класс для регистрации и обработки событий Telethon.
    Инкапсулирует кэш топиков и логику парсинга сообщений.
    """

    def __init__(self, event_bus: EventBus, client: TelethonClient, ignored_users: List[int]):
        self.event_bus = event_bus
        self.client = client
        self.ignored_users = ignored_users

        self.topic_cache = LRUCache(maxsize=1000)

    def register_handlers(self):
        """Регистрирует все обработчики событий в клиенте."""

        # Telethon позволяет фильтровать события прямо при регистрации (func=...)
        self.client.add_event_handler(
            self.handle_private_message,
            events.NewMessage(incoming=True, func=lambda e: e.is_private),
        )

        self.client.add_event_handler(
            self.handle_group_message,
            events.NewMessage(incoming=True, func=lambda e: not e.is_private),
        )

        self.client.add_event_handler(self.handle_reactions, events.Raw)
        system_logger.info("[Telethon] Обработчики событий успешно зарегистрированы.")

    # ==========================================
    # Основные обработчики
    # ==========================================

    async def handle_private_message(self, event: events.NewMessage.Event):
        sender = await event.get_sender()

        # Игнорируем сервисные аккаунты
        if sender and getattr(sender, "id", None) in self.ignored_users:
            return

        text = self._extract_text_with_media(event)
        username = self._get_sender_username(sender, fallback_id=event.chat_id)
        chat_id = str(event.chat_id)
        chat_source = f"tg_agent_chat_({chat_id})"

        # Логгируем входящие личные сообщения
        time_str = datetime.datetime.now().strftime("%H:%M")
        # Формат: [15:43] @user (in personal messages): привет, как дела?
        log_str = f"[{time_str}] @{username} (in personal messages): {text}"
        if len(log_str) > 1000:
            log_str = log_str[:977] + "...[ОБРЕЗАНО]"  # Режем слишком длинные сообщения

        self.client.recent_activity.append(log_str)

        await self.event_bus.publish(
            Events.TELEGRAM_MESSAGE_INCOMING,
            username=username,
            chat_id=chat_id,
            text=text,
            chat_source=chat_source,
            message_id=event.id,
        )

    async def handle_group_message(self, event: events.NewMessage.Event):
        me = await self.client.get_me()
        chat = await event.get_chat()
        sender = await event.get_sender()

        # Проверка на упоминание
        is_mention = getattr(event.message, "mentioned", False)
        if not is_mention and event.is_reply:
            is_mention = await self._is_reply_to_me(event, me.id)

        # Обработка анонимных админов (когда пишут от имени группы/канала)
        if not sender or getattr(sender, "id", None) == getattr(chat, "id", None):
            sender = chat

        username = self._get_sender_username(sender, fallback_id=chat.id)
        chat_title = getattr(chat, "title", "Unknown Chat")
        text = self._extract_text_with_media(event)

        chat_id = self._normalize_chat_id(chat)
        topic_prefix = await self._resolve_topic_prefix(event, chat)

        chat_source = f"tg_agent_group_({chat_id}){topic_prefix}"
        if len(chat_source) > 99:
            chat_source = chat_source[:99] + "..."

        event_type = (
            Events.TELEGRAM_GROUP_MENTION if is_mention else Events.TELEGRAM_GROUP_MESSAGE
        )

        # Логгируем фоновые сообщения

        time_str = datetime.datetime.now().strftime("%H:%M")
        # Формат: [15:43] @user (in group 'AAF'): всем привет
        log_str = f"[{time_str}] @{username} (in group '{chat_title}{topic_prefix}'): {text}"
        if len(log_str) > 1000:
            log_str = log_str[:977] + "...[ОБРЕЗАНО]"

        self.client.recent_activity.append(log_str)

        await self.event_bus.publish(
            event_type,
            chat_title=chat_title,
            chat_id=chat_id,
            username=username,
            text=text,
            chat_source=chat_source,
            message_id=event.id,
        )

    async def handle_reactions(self, event: events.Raw):
        if not isinstance(event, UpdateMessageReactions):
            return

        try:
            if not event.reactions or not event.reactions.results:
                return

            chat_id = utils.get_peer_id(event.peer)
            msg_id = event.msg_id

            # Берем первую реакцию
            reaction_obj = event.reactions.results[0].reaction
            emoticon = getattr(reaction_obj, "emoticon", "какая-то реакция")

            await self.event_bus.publish(
                Events.TELEGRAM_MESSAGE_REACTION,
                chat_id=chat_id,
                message_id=msg_id,
                emoticon=emoticon,
            )
        except Exception as e:
            system_logger.warning(f"[Telethon] Ошибка парсинга реакции: {e}")

    # ==========================================
    # Вспомогательные методы
    # ==========================================

    @staticmethod
    def _extract_text_with_media(event: events.NewMessage.Event) -> str:
        """Извлекает сырой текст и добавляет префикс, если есть медиавложение."""
        prefix = ""
        if event.sticker:
            emoji = getattr(event.file, "emoji", "")
            prefix = f"[Стикер {emoji}] " if emoji else "[Стикер] "
        elif event.photo:
            prefix = "[Фотография] "
        elif event.video:
            prefix = "[Видео] "
        elif event.voice:
            prefix = "[Голосовое сообщение] "
        elif event.gif:
            prefix = "[GIF] "
        elif event.poll:
            prefix = "[Опрос] "
        elif event.document:
            prefix = "[Вложение/Медиа] "

        raw_text = event.raw_text or ""
        return (prefix + raw_text).strip()

    @staticmethod
    def _get_sender_username(sender: User | Chat | Channel | None, fallback_id: int) -> str:
        """Пытается получить @username, иначе имя, иначе ID."""
        if not sender:
            return str(fallback_id)

        if getattr(sender, "username", None):
            return sender.username.replace("@", "")

        display_name = utils.get_display_name(sender)
        return display_name if display_name else str(getattr(sender, "id", fallback_id))

    @staticmethod
    def _normalize_chat_id(chat: Chat | Channel) -> str:
        """Приводит ID супергрупп к формату -100..."""
        chat_id = str(chat.id)
        if not chat_id.startswith("-100") and getattr(chat, "megagroup", False):
            return f"-100{chat_id}"
        return chat_id

    async def _is_reply_to_me(self, event: events.NewMessage.Event, my_id: int) -> bool:
        """Проверяет, является ли сообщение ответом на сообщение нашего агента."""
        try:
            reply_msg = await event.get_reply_message()
            return bool(reply_msg and reply_msg.sender_id == my_id)
        except Exception as e:
            system_logger.debug(f"[Telethon Dispatcher] Ошибка проверки реплая: {e}")
            return False

    async def _resolve_topic_prefix(self, event: events.NewMessage.Event, chat) -> str:
        """Определяет ID и название топика, используя кэш."""
        if (
            getattr(event.message, "reply_to", None) is None
            or not event.message.reply_to.forum_topic
        ):
            return ""

        topic_id = (
            event.message.reply_to.reply_to_top_id or event.message.reply_to.reply_to_msg_id
        )

        if topic_id == 1:
            return "[Топик ID: 1]"  # General топик

        cache_key = f"{chat.id}_{topic_id}"

        # Если нет в кэше, идем в API Telegram
        if cache_key not in self.topic_cache:
            try:
                topic_msg = await self.client.get_messages(chat, ids=topic_id)
                if topic_msg and topic_msg.action and hasattr(topic_msg.action, "title"):
                    self.topic_cache[cache_key] = topic_msg.action.title
                else:
                    self.topic_cache[cache_key] = "Без названия"
            except Exception as e:
                system_logger.warning(
                    f"[Telethon Dispatcher] Не удалось получить название топика {topic_id}: {e}"
                )
                self.topic_cache[cache_key] = "Неизвестный топик"

        return f"[Топик ID: {topic_id}]"
