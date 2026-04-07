from collections import deque
import os
import time
import asyncio
import httpx
from typing import Optional
from dotenv import load_dotenv

from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.managers.logger import system_logger

# Родители
from src.l03_interfaces.type.base import BaseClient

# Поллинг
from src.l03_interfaces.type.api.reddit.events import RedditEvents

# Инструменты
from src.l03_interfaces.type.api.reddit.instruments.comments import RedditComments
from src.l03_interfaces.type.api.reddit.instruments.posts import RedditPosts
from src.l03_interfaces.type.api.reddit.instruments.profile import RedditProfile
from src.l03_interfaces.type.api.reddit.instruments.subreddits import RedditSubreddits

load_dotenv()


class RedditClient(BaseClient):
    AUTH_URL = "https://www.reddit.com/api/v1/access_token"
    BASE_URL = "https://oauth.reddit.com"

    name = "reddit"  # Имя для маппинга

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.username = os.getenv("REDDIT_USERNAME")
        self.password = os.getenv("REDDIT_PASSWORD")

        self.is_ready = all([self.client_id, self.client_secret, self.username, self.password])
        self.user_agent = f"python:aaf.agent:v1 (by u/{self.username or 'unknown'})"

        self._token: Optional[str] = None
        self._token_expires_at: float = 0

        if not self.is_ready:
            system_logger.warning("[Reddit] Учетные данные неполные. Интерфейс отключен.")

        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL, headers={"User-Agent": self.user_agent}, timeout=20.0
        )

        self.recent_activity = deque(maxlen=50)

    def register_instruments(self):
        RedditComments(self)
        RedditPosts(self)
        RedditProfile(self)
        RedditSubreddits(self)
        system_logger.debug("[Reddit] Инструменты успешно зарегистрированы.")

    async def start_background_polling(self) -> None:
        events = RedditEvents(event_bus=self.event_bus, client=self)
        events.start_polling()

    def get_passive_context(self) -> dict:
        status = "🟢 ONLINE" if self.is_ready else "🔴 OFFLINE"
        return {
            "name": "reddit",
            "status": status,
            "recent_activity": list(self.recent_activity)
        }

    async def _ensure_token(self) -> bool:
        if not self.is_ready:
            return False
        if self._token and time.time() < self._token_expires_at - 60:
            return True

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": self.user_agent}
            ) as auth_client:
                resp = await auth_client.post(
                    self.AUTH_URL,
                    auth=(self.client_id, self.client_secret),
                    data={
                        "grant_type": "password",
                        "username": self.username,
                        "password": self.password,
                    },
                )
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("access_token")
                self._token_expires_at = time.time() + data.get("expires_in", 3600)
                self.client.headers["Authorization"] = f"Bearer {self._token}"
                return True
            return False
        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка сети при получении токена: {e}")
            return False

    async def request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        if not await self._ensure_token():
            raise RuntimeError("[Reddit] Нет токена авторизации.")
        endpoint = endpoint.lstrip("/")
        response = await self.client.request(method, endpoint, **kwargs)

        if response.status_code == 429:
            reset_time = float(response.headers.get("x-ratelimit-reset", 60.0))
            system_logger.warning(f"[Reddit] Rate Limit (429). Сон на {int(reset_time)} сек.")
            await asyncio.sleep(reset_time + 1)
            response = await self.client.request(method, endpoint, **kwargs)

        return response

    async def check_connection(self) -> bool:
        if not self.is_ready:
            return False
        try:
            response = await self.request("GET", "api/v1/me")
            if response.status_code == 200:
                system_logger.info(
                    f"[Reddit] Авторизация успешна. Подключен как: u/{response.json().get('name')}"
                )
                return True
            return False
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()
        system_logger.info("[Reddit] Сессия закрыта.")
