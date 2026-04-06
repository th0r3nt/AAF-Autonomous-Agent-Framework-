import httpx

from src.l00_utils.managers.logger import system_logger

# Родители
from src.l03_interfaces.type.base import BaseClient

# Инструменты
from src.l03_interfaces.type.web.http.instruments.requests import HttpRequests


class HTTPClient(BaseClient):
    """Асинхронный клиент для общих HTTP-запросов агента."""

    def __init__(self):

        limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
        timeout = httpx.Timeout(15.0, connect=5.0)
        headers = {
            "User-Agent": "AAF-Agent (Autonomous Agent Framework)",
            "Accept": "application/json, text/plain, */*",
        }

        self.client = httpx.AsyncClient(
            limits=limits, timeout=timeout, headers=headers, follow_redirects=True
        )
        system_logger.debug("[HTTP Client] Глобальная сессия инициализирована.")

    def register_instruments(self):
        HttpRequests(self)
        system_logger.debug("[HTTP Client] Инструменты сетевых запросов зарегистрированы.")

    async def start_background_polling(self) -> None:
        pass  # Нет поллинга, HTTP-запросы выполняются по требованию

    async def check_connection(self) -> bool:
        try:
            response = await self.client.get("https://1.1.1.1", timeout=5.0)
            if response.status_code in [200, 301, 302, 403, 404]:
                system_logger.info("[HTTP Client] Сетевое подключение активно.")
                return True
            return False
        except httpx.RequestError as e:
            system_logger.error(f"[HTTP Client] Ошибка сети при проверке подключения: {e}")
            return False

    async def close(self, *args, **kwargs):
        await self.client.aclose()
        system_logger.info("[HTTP Client] Сессия закрыта.")
