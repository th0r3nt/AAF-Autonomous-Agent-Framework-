import os
import httpx
from dotenv import load_dotenv

from src.l00_utils.managers.logger import system_logger

# Родители
from src.l03_interfaces.type.base import BaseClient

# Инструменты
from src.l03_interfaces.type.web.search.instruments.duckduckgo import DuckDuckGoSearch
from src.l03_interfaces.type.web.search.instruments.google import GoogleSearch
from src.l03_interfaces.type.web.search.instruments.wikipedia import WikipediaSearch

load_dotenv()


class SearchClient(BaseClient):
    """Асинхронный клиент для поисковых сервисов."""

    name = "web search"  # Имя для маппинга

    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_cx = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        self.is_google_enabled = bool(self.google_api_key and self.google_cx)

        headers = {
            "AAF-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        self.client = httpx.AsyncClient(headers=headers, timeout=15.0, follow_redirects=True)
        system_logger.debug("[Web Search] HTTP-клиент для поиска инициализирован.")

    def register_instruments(self):
        DuckDuckGoSearch(self)
        GoogleSearch(self)
        WikipediaSearch(self)
        system_logger.debug("[Web Search] Инструменты поиска зарегистрированы.")

    async def start_background_polling(self) -> None:
        pass  # Поиск работает только по запросу

    async def check_connection(self) -> bool:
        try:
            resp = await self.client.get("https://lite.duckduckgo.com/lite/", timeout=5.0)
            if resp.status_code == 200:
                system_logger.info("[Web Search] Поисковые сервисы доступны.")
                return True
            return False
        except httpx.RequestError as e:
            system_logger.error(f"[Web Search] Ошибка проверки соединения: {e}")
            return False

    async def close(self, *args, **kwargs):
        await self.client.aclose()
        system_logger.info("[Web Search] Сессия закрыта.")
