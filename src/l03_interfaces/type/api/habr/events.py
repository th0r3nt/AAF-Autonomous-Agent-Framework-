import asyncio
import httpx
import datetime
from cachetools import LRUCache

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.managers.config import settings
from src.l00_utils.event.registry import Events
from src.l00_utils._tools import clean_html_to_md

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.api.habr.client import HabrClient


class HabrEvents:
    def __init__(self, event_bus: EventBus, client: 'HabrClient', polling_interval: int = 600):
        self.event_bus = event_bus
        self.client = client
        self.polling_interval = polling_interval  # 10 минут по умолчанию, бережем API

        # Раздельные кэши, чтобы ID статей и уведомлений не пересекались
        self.PROCESSED_NOTIFICATIONS = LRUCache(maxsize=1000)
        self.PROCESSED_ARTICLES = LRUCache(maxsize=2000)

        self.ETAGS = {}

    async def _fetch_hub_radar(self):
        """
        Read-Only.
        Проверяет свежие статьи в отслеживаемых хабах.
        """

        tracked_hubs = settings.interfaces.api.habr.tracked_hubs
        if not tracked_hubs:
            return

        for hub in tracked_hubs:
            headers = {}
            etag_key = f"radar_{hub}"
            if etag_key in self.ETAGS:
                headers["If-None-Match"] = self.ETAGS[etag_key]

            try:
                # Запрашиваем ленту хаба, сортировка по дате (самые свежие)
                response = await self.client.client.get(
                    "/articles/",
                    params={"hub": hub, "sort": "date", "hl": "ru", "fl": "ru", "page": 1},
                    headers=headers,
                )

                if response.status_code == 304:
                    continue  # Ничего нового в этом хабе

                if response.status_code == 200:
                    if "ETag" in response.headers:
                        self.ETAGS[etag_key] = response.headers["ETag"]

                    data = response.json()
                    article_ids = data.get("articleIds", [])
                    article_refs = data.get("articleRefs", {})

                    for a_id in article_ids:
                        a_id_str = str(a_id)
                        # Проверяем кэш
                        if a_id_str in self.PROCESSED_ARTICLES:
                            continue
                        self.PROCESSED_ARTICLES[a_id_str] = True

                        article = article_refs.get(a_id_str, {})
                        title = clean_html_to_md(article.get("titleHtml", "Без названия"))
                        author = article.get("author", {}).get("alias", "Unknown")
                        score = article.get("statistics", {}).get("score", 0)

                        system_logger.debug(f"[Habr] Новая статья в хабе '{hub}': {title}")

                        time_str = datetime.datetime.now().strftime("%H:%M")
                        log_str = f"[{time_str}] New article in '{hub}': {title} (from @{author})"
                        self.client.recent_activity.append(log_str)

                        # Отправляем в шину агенту как BACKGROUND событие
                        await self.event_bus.publish(
                            Events.HABR_ARTICLE_PUBLISHED,
                            article_id=a_id_str,
                            hub=hub,
                            title=title,
                            author=author,
                            score=score,
                        )

            except httpx.RequestError as e:
                system_logger.error(f"[Habr] Ошибка сети при опросе хаба '{hub}': {e}")

            # Небольшая пауза между хабами, чтобы не спамить запросами
            await asyncio.sleep(2)

    async def _fetch_notifications(self):
        """
        Вызывается, если у агента есть личный аккаунт на Хабре.
        Проверяет личные уведомления аккаунта агента.
        """

        headers = {}
        if "notifications" in self.ETAGS:
            headers["If-None-Match"] = self.ETAGS["notifications"]

        try:
            # Запрашиваем трекер (уведомления)
            # Примечание: Это внутренний эндпоинт Хабра, он может отдавать данные в специфичном формате
            response = await self.client.client.get("/me/tracker", headers=headers)

            if response.status_code == 304:
                return

            if response.status_code == 200:
                if "ETag" in response.headers:
                    self.ETAGS["notifications"] = response.headers["ETag"]

                data = response.json()
                # Предполагаемая структура: список событий или объект с массивом.
                # Зависит от актуального ответа API Хабра. Оставляю безопасный парсинг.
                events_list = (
                    data.get("events", [])
                    if isinstance(data, dict)
                    else (data if isinstance(data, list) else [])
                )

                for event in events_list:
                    event_id = str(event.get("id", ""))
                    if not event_id or event_id in self.PROCESSED_NOTIFICATIONS:
                        continue

                    self.PROCESSED_NOTIFICATIONS[event_id] = True

                    action = event.get("action", "")  # mention, reply, etc
                    text = clean_html_to_md(event.get("textHtml", ""))
                    author = event.get("author", {}).get("alias", "Unknown")

                    time_str = datetime.datetime.now().strftime("%H:%M")
                    log_str = f"[{time_str}] notification ({action}) from @{author}: {text[:1000]}"
                    self.client.recent_activity.append(log_str)

                    if action == "mention":
                        system_logger.info(f"[Habr] Упоминание от @{author}")
                        await self.event_bus.publish(
                            Events.HABR_MENTION_INCOMING,
                            notification_id=event_id,
                            author=author,
                            text=text,
                        )
                    elif action == "reply":
                        system_logger.info(f"[Habr] Ответ на комментарий от @{author}")
                        await self.event_bus.publish(
                            Events.HABR_COMMENT_REPLY,
                            notification_id=event_id,
                            author=author,
                            text=text,
                        )

            elif response.status_code == 401 or response.status_code == 403:
                system_logger.error(
                    "[Habr] Сессия истекла (401/403). Режим аккаунта отключен."
                )
                self.client.is_authenticated = False

        except httpx.RequestError as e:
            system_logger.error(f"[Habr] Ошибка сети: {e}")

    async def habr_event_loop(self):
        """
        Бесконечный цикл поллинга.
        """
        system_logger.info(
            f"[Habr] Запуск фонового поллинга (интервал: {self.polling_interval} сек.)"
        )

        # Если поллинг выключен и аккаунта нет - крутить луп бессмысленно
        tracked_hubs = settings.interfaces.api.habr.tracked_hubs
        if not self.client.is_authenticated and not tracked_hubs:
            system_logger.info(
                "[Habr] Нет отслеживаемых хабов и авторизации. Поллинг остановлен."
            )
            return

        while True:
            try:
                # Поллинг (новости/статьи)
                if tracked_hubs:
                    await self._fetch_hub_radar()

                # Поллинг личных уведомлений (если есть аккаунт)
                if self.client.is_authenticated:
                    await self._fetch_notifications()

            except Exception as e:
                system_logger.error(f"[Habr Polling] Критическая ошибка в цикле: {e}")

            await asyncio.sleep(self.polling_interval)

    def start_polling(self):
        """Синхронная обертка для вызова из клиента."""
        asyncio.create_task(self.habr_event_loop())
