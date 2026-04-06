from cachetools import TTLCache
from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.web.search.client import SearchClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class GoogleSearch(BaseInstrument):
    """Инструмент поиска через официальный Google Custom Search API."""

    def __init__(self, search_client: SearchClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.api = search_client
        self.GOOGLE_CACHE = TTLCache(maxsize=100, ttl=3600)

    @skill()
    async def search(self, query: str, limit: int = 5) -> ToolResult:
        """
        Ищет информацию в Google.
        Возвращает форматированный список сниппетов.
        """
        if not self.api.is_google_enabled:
            return ToolResult.fail(
                msg="Ошибка: Ключи GOOGLE_API_KEY и GOOGLE_SEARCH_ENGINE_ID не настроены.",
                error="ConfigError",
            )

        # Анти-SEO фильтр (отсекаем мусор)
        anti_seo_tags = "-site:pinterest.com"
        full_query = f"{query} {anti_seo_tags}".strip()

        # Проверяем кэш
        cache_key = f"{full_query}_{limit}"
        if cache_key in self.GOOGLE_CACHE:
            system_logger.debug(f"[Google Search] Отдача из кэша: '{query}'")
            return self.GOOGLE_CACHE[cache_key]

        system_logger.info(f"[Google Search] Запрос: '{query}'")

        params = {
            "key": self.api.google_api_key,
            "cx": self.api.google_cx,
            "q": full_query,
            "num": min(limit, 10),  # API Google не отдает больше 10 результатов за раз
        }

        try:
            resp = await self.api.client.get(
                "https://www.googleapis.com/customsearch/v1", params=params
            )

            if resp.status_code == 200:
                items = resp.json().get("items", [])

                if not items:
                    res_obj = ToolResult.fail(
                        msg=f"В Google по запросу '{query}' ничего не найдено."
                    )
                    self.GOOGLE_CACHE[cache_key] = res_obj
                    return res_obj

                formatted_results = [f"--- Результаты Google по запросу '{query}' ---"]
                for idx, item in enumerate(items, 1):
                    title = item.get("title", "Без названия")
                    link = item.get("link", "")
                    snippet = item.get("snippet", "").replace("\n", " ")
                    formatted_results.append(f"{idx}. {title}\nURL: {link}\nСниппет: {snippet}")

                res_obj = ToolResult.ok(msg="\n\n".join(formatted_results), data=items)
                self.GOOGLE_CACHE[cache_key] = res_obj
                return res_obj

            return ToolResult.fail(
                msg=f"Ошибка Google API. HTTP Status: {resp.status_code}",
                error=resp.text,
            )

        except Exception as e:
            system_logger.error(f"[Google Search] Ошибка сети при поиске: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))
