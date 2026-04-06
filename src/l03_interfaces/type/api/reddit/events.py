import asyncio
import datetime
from cachetools import LRUCache

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.event.registry import Events
from src.l03_interfaces.type.api.reddit.client import RedditClient


class RedditEvents:
    def __init__(self, event_bus: EventBus, client: RedditClient, polling_interval: int = 180):
        self.event_bus = event_bus
        self.client = client
        self.polling_interval = polling_interval

        self.PROCESSED_REDDIT_MESSAGES = LRUCache(maxsize=1000)

    async def _fetch_unread_messages(self):
        """Запрашивает непрочитанные уведомления и личные сообщения из Inbox."""
        try:
            # Запрашиваем только непрочитанные. Limit 15 хватит для минутного поллинга.
            response = await self.client.request("GET", "message/unread", params={"limit": 15})

            if response.status_code != 200:
                if response.status_code != 429:  # 429 логируется внутри клиента
                    system_logger.warning(
                        f"[Reddit Polling] Ошибка при проверке почты: HTTP {response.status_code}"
                    )
                return

            data = response.json().get("data", {})
            children = data.get("children", [])

            if not children:
                return  # Новых уведомлений нет

            messages_to_mark_read = []

            for item in children:
                msg_data = item.get("data", {})
                msg_id = msg_data.get("name")  # fullname (например, t1_j9z8b или t4_8xk2)

                # Если уже обрабатывали - пропускаем
                if msg_id in self.PROCESSED_REDDIT_MESSAGES:
                    continue

                self.PROCESSED_REDDIT_MESSAGES[msg_id] = True
                messages_to_mark_read.append(msg_id)

                # Собираем данные
                author = msg_data.get("author", "unknown")
                body = msg_data.get("body", "")
                subject = msg_data.get("subject", "")
                subreddit = msg_data.get("subreddit", "")  # Для PM будет пустым или None
                was_comment = msg_data.get("was_comment", False)
                context_url = msg_data.get("context", "")

                # Убираем слишком длинные цитаты, чтобы не спамить в EventBus
                if len(body) > 500:
                    body = body[:497] + "..."

                time_str = datetime.datetime.now().strftime("%H:%M")
                log_str = f"[{time_str}] u/{author} (r/{subreddit or 'PM'}): {subject}"
                self.client.recent_activity.append(log_str)

                # Определяем тип события (Reddit отдает это в поле subject или type)
                if subject == "username mention":
                    system_logger.info(f"[Reddit] Упоминание от u/{author} в r/{subreddit}")
                    await self.event_bus.publish(
                        Events.REDDIT_COMMENT_MENTION,
                        message_id=msg_id,
                        author=author,
                        subreddit=subreddit,
                        text=body,
                        url=context_url,
                    )

                elif subject in ["comment reply", "post reply"]:
                    system_logger.info(f"[Reddit] Ответ от u/{author} в r/{subreddit}")
                    await self.event_bus.publish(
                        Events.REDDIT_COMMENT_REPLY,
                        message_id=msg_id,
                        author=author,
                        subreddit=subreddit,
                        text=body,
                        url=context_url,
                        reply_type=subject,
                    )

                elif not was_comment:
                    # Это личное сообщение (Private Message)
                    system_logger.info(f"[Reddit] Новое личное сообщение от u/{author}: {subject}")
                    await self.event_bus.publish(
                        Events.REDDIT_MESSAGE_INCOMING,
                        message_id=msg_id,
                        author=author,
                        subject=subject,
                        text=body,
                    )
                else:
                    # Неизвестный тип уведомления (например, инвайт в сабреддит)
                    system_logger.debug(
                        f"[Reddit] Неизвестное уведомление от u/{author}. Subject: {subject}"
                    )

            # Помечаем сообщения прочитанными на стороне Reddit,
            # чтобы они не висели в Inbox и не отдавались при следующем запросе
            if messages_to_mark_read:
                # API принимает строку ID, разделенных запятыми
                ids_str = ",".join(messages_to_mark_read)
                await self.client.request("POST", "api/read_message", data={"id": ids_str})
                system_logger.debug(
                    f"[Reddit Polling] Отмечены как прочитанные: {len(messages_to_mark_read)} шт."
                )

        except Exception as e:
            system_logger.error(f"[Reddit Polling] Критическая ошибка в логике поллинга: {e}")

    async def reddit_event_loop(self):
        """
        Бесконечный цикл поллинга, который запускается как фоновая задача.
        Reddit лимитирует жестко, так что проверяем раз в 3 минуты (180 сек).
        """
        system_logger.info(
            f"[Reddit] Запуск фонового поллинга (интервал: {self.polling_interval} сек.)"
        )

        # Ждем проверки пульса перед стартом
        is_alive = await self.client.check_connection()
        if not is_alive:
            system_logger.error("[Reddit] Агент не авторизован. Поллинг отменен.")
            return

        while True:
            try:
                await self._fetch_unread_messages()
            except Exception as e:
                system_logger.error(f"[Reddit Polling] Сбой цикла: {e}")

            await asyncio.sleep(self.polling_interval)

    def start_polling(self):
        """Синхронная обертка для удобного запуска из менеджера интерфейсов."""
        asyncio.create_task(self.reddit_event_loop())
