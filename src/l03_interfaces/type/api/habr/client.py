import os
from collections import deque
import httpx
from dotenv import load_dotenv

from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.managers.logger import system_logger

# Родители
from src.l03_interfaces.type.base import BaseClient

# Поллинг
from src.l03_interfaces.type.api.habr.events import HabrEvents

# Инструменты
from src.l03_interfaces.type.api.habr.instruments.articles import HabrArticles
from src.l03_interfaces.type.api.habr.instruments.comments import HabrComments
from src.l03_interfaces.type.api.habr.instruments.news import HabrNews
from src.l03_interfaces.type.api.habr.instruments.users import HabrUsers

load_dotenv()


class HabrClient(BaseClient):
    """Асинхронный клиент для работы ИИ-агента с Habr."""

    name = "habr"  # Имя для маппинга

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        self.cookie_sid = os.getenv("HABR_CONNECT_SID")
        self.csrf_token = os.getenv("HABR_CSRF_TOKEN")

        self.is_authenticated = bool(self.cookie_sid)

        if not self.is_authenticated:
            system_logger.info("[Habr] API работает в режиме Read-Only.")
        else:
            system_logger.info("[Habr] Авторизационные данные найдены.")

        self.base_url = "https://habr.com/kek/v2"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://habr.com/ru/",
        }
        if self.csrf_token:
            headers["csrf-token"] = self.csrf_token

        cookies = {}
        if self.cookie_sid:
            cookies["connect_sid"] = self.cookie_sid

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            cookies=cookies,
            timeout=15.0,
            follow_redirects=True,
        )

        self.recent_activity = deque(maxlen=50)

    def register_instruments(self):
        HabrArticles(self)
        HabrComments(self)
        HabrNews(self)
        HabrUsers(self)
        system_logger.debug("[Habr] Инструменты успешно зарегистрированы.")

    async def start_background_polling(self) -> None:
        events = HabrEvents(event_bus=self.event_bus, client=self, polling_interval=600)
        events.start_polling()

    def get_passive_context(self) -> dict:
        status = "🟢 ONLINE" if self.is_authenticated else "🟡 READ-ONLY"
        return {
            "name": "habr",
            "status": status,
            "recent_activity": list(self.recent_activity)
        }

    async def check_connection(self) -> bool:
        try:
            if self.is_authenticated:
                response = await self.client.get("/me", params={"hl": "ru"})
                if response.status_code == 200:
                    login = response.json().get("alias", "Unknown")
                    system_logger.info(
                        f"[Habr] Авторизация успешна. Подключен аккаунт: @{login}"
                    )
                    return True
                else:
                    system_logger.warning("[Habr] Ошибка авторизации. Переход в Read-Only режим.")
                    self.is_authenticated = False
            
            # Анонимная проверка (Read-Only)
            response = await self.client.get(
                "/articles/", params={"hl": "ru", "fl": "ru", "page": 1}
            )
            if response.status_code == 200:
                system_logger.info("[Habr] Анонимное подключение к API успешно.")
                return True

            # Даже если API штормит (например, 503), оставляем навыки доступными
            return True  
            
        except httpx.RequestError as e:
            # Даем агенту шанс использовать навыки, даже если при старте был скачок сети
            system_logger.warning(f"[Habr] Скачок сети при старте: {e}. Навыки будут зарегистрированы.")
            return True

    async def close(self):
        await self.client.aclose()
        system_logger.info("[Habr] Сессия клиента закрыта.")
