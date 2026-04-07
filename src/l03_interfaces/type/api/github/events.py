import asyncio
import httpx
import datetime
from cachetools import LRUCache

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.event.registry import Events

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.l03_interfaces.type.api.github.client import GithubClient


class GitHubEvents:
    def __init__(
        self, event_bus: EventBus, client: "GithubClient", polling_interval: int = 180
    ):
        self.event_bus = event_bus
        self.client = client
        self.polling_interval = polling_interval

        self.PROCESSED_NOTIFICATIONS = LRUCache(
            maxsize=1000
        )  # Кэш для обработанных уведомлений, чтобы не кидать их в шину дважды
        self.ETAGS = (
            {}
        )  # Словарь для хранения ETag-заголовков (защита от сжигания лимитов API)

    async def _fetch_notifications(self):
        """Внутренняя функция для запроса непрочитанных уведомлений с GitHub"""

        headers = {}
        # Если мы уже делали запрос, передаем старый ETag
        if "notifications" in self.ETAGS:
            headers["If-None-Match"] = self.ETAGS["notifications"]

        try:
            # Запрашиваем только непрочитанные уведомления (all=false)
            response = await self.client.client.get(
                "/notifications", params={"all": "false"}, headers=headers
            )

            # 304 Not Modified - ничего не изменилось, лимиты API не списаны. Идеально
            if response.status_code == 304:
                system_logger.debug(
                    "[GitHub Polling] 304 Not Modified. Новых уведомлений нет."
                )
                return

            # 200 OK - есть что-то новенькое
            if response.status_code == 200:
                # Сохраняем новый ETag на будущее
                if "ETag" in response.headers:
                    self.ETAGS["notifications"] = response.headers["ETag"]

                notifications = response.json()
                if not notifications:
                    return

                for notif in notifications:
                    notif_id = notif.get("id")

                    # Защита от дублей
                    if notif_id in self.PROCESSED_NOTIFICATIONS:
                        continue
                    self.PROCESSED_NOTIFICATIONS[notif_id] = True

                    # Парсим полезную информацию
                    reason = notif.get(
                        "reason"
                    )  # Почему пришло: mention, assign, review_requested, subscribed
                    subject = notif.get("subject", {})
                    title = subject.get("title", "Без названия")
                    subject_type = subject.get(
                        "type", "Unknown"
                    )  # Issue, PullRequest, Discussion
                    repo_name = notif.get("repository", {}).get("full_name", "Unknown Repo")

                    # Получаем ссылку на API, чтобы агент мог вытащить сам текст
                    subject_url = subject.get("url", "")

                    system_logger.info(
                        f"[GitHub] Новое событие ({reason}) в {repo_name}: {title}"
                    )

                    time_str = datetime.datetime.now().strftime("%H:%M")
                    log_str = f"[{time_str}] notification ({reason}) in {repo_name}: {title}"
                    self.client.recent_activity.append(log_str)

                    # Распределяем по шине событий в зависимости от reason
                    if reason in ["mention", "assign", "review_requested"]:
                        await self.event_bus.publish(
                            Events.GITHUB_MENTION_INCOMING,
                            notification_id=notif_id,
                            repo_name=repo_name,
                            subject_type=subject_type,
                            title=title,
                            reason=reason,
                            api_url=subject_url,
                        )
                    else:
                        # Обычные уведомления (кто-то создал Issue в отслеживаемом репо, но не тегал агента)
                        await self.event_bus.publish(
                            Events.GITHUB_REPO_ACTIVITY,
                            notification_id=notif_id,
                            repo_name=repo_name,
                            subject_type=subject_type,
                            title=title,
                            reason=reason,
                            api_url=subject_url,
                        )

            elif response.status_code == 401:
                system_logger.error(
                    "[GitHub Polling] Ошибка 401: Токен недействителен. Поллинг остановлен."
                )
                raise ValueError("Invalid GitHub Token")
            else:
                system_logger.warning(
                    f"[GitHub Polling] Неожиданный ответ: {response.status_code} - {response.text}"
                )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub Polling] Ошибка сети при запросе уведомлений: {e}")

    async def github_event_loop(self):
        """
        Бесконечный цикл поллинга, который запускается как фоновая задача.
        """
        # 1. Если токена нет изначально, поллинг личных уведомлений бессмысленен
        if not self.client.token:
            system_logger.info(
                "[GitHub] Токен отсутствует. Фоновый поллинг уведомлений отключен (режим Read-Only)."
            )
            return

        system_logger.info(
            f"[GitHub] Запуск фонового поллинга (интервал: {self.polling_interval} сек.)"
        )

        # Проверяем, жив ли токен в данный момент
        is_alive = await self.client.check_connection()
        if not is_alive:
            system_logger.error("[GitHub] Агент не авторизован. Поллинг отменен.")
            return

        # Основной цикл
        while True:
            try:
                await self._fetch_notifications()

            except ValueError as ve:
                # Если функция _fetch_notifications выбросила именно ошибку токена
                if "Invalid GitHub Token" in str(ve):
                    # Прерываем бесконечный цикл, чтобы не спамить логи каждые 3 минуты
                    break
                system_logger.error(f"[GitHub Polling] Ошибка в цикле: {ve}")

            except Exception as e:
                system_logger.error(f"[GitHub Polling] Критическая ошибка в цикле: {e}")

            await asyncio.sleep(self.polling_interval)

    def start_polling(self):
        """Синхронная обертка для удобного запуска из api.py"""
        asyncio.create_task(self.github_event_loop())
