import time
import asyncio
import httpx

from src.l00_utils.managers.logger import system_logger

# Родители
from src.l03_interfaces.type.base import BaseClient

# Инструменты
from src.l03_interfaces.type.geo.instruments.geocoding import GeoGeocoding
from src.l03_interfaces.type.geo.instruments.places import GeoPlaces
from src.l03_interfaces.type.geo.instruments.routing import GeoRouting
from src.l03_interfaces.type.geo.instruments.weather import GeoWeather


class GeoClient(BaseClient):
    """Асинхронный клиент для работы с бесплатными гео-сервисами."""

    name = "geo"  # Имя для маппинга

    def __init__(self):
        headers = {
            "User-Agent": "AAF-Agent (Autonomous Agent Framework)",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        self.client = httpx.AsyncClient(headers=headers, timeout=15.0, follow_redirects=True)

        self._request_lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._min_delay = 1.2

    def register_instruments(self):
        GeoGeocoding(self)
        GeoPlaces(self)
        GeoRouting(self)
        GeoWeather(self)
        system_logger.debug("[Geo] Инструменты успешно зарегистрированы.")

    async def start_background_polling(self) -> None:
        pass  # Нет поллинга

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async with self._request_lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_delay:
                await asyncio.sleep(self._min_delay - elapsed)
            try:
                response = await self.client.request(method, url, **kwargs)
                self._last_request_time = time.time()
                return response
            except Exception as e:
                self._last_request_time = time.time()
                raise e

    async def check_connection(self) -> bool:
        try:
            response = await self.request(
                "GET",
                "https://nominatim.openstreetmap.org/status.php",
                params={"format": "json"},
            )
            if response.status_code == 200:
                system_logger.info("[Geo] Подключение к гео-сервисам OSM успешно установлено.")
                return True
            
            return False
        
        except Exception as e:
            system_logger.error(f"[Geo] Ошибка сети при проверке подключения: {e}")
            return False

    async def close(self):
        await self.client.aclose()
        system_logger.info("[Geo] Сессия закрыта.")
