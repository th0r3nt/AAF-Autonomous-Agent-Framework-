import re
from cachetools import TTLCache
from src.l00_utils.managers.logger import system_logger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.web.search.client import SearchClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class DuckDuckGoSearch(BaseInstrument):
    """Инструмент бесплатного поиска через парсинг DuckDuckGo."""

    def __init__(self, search_client: 'SearchClient'):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.api = search_client
        self.DDG_CACHE = TTLCache(maxsize=100, ttl=3600)

    @skill()
    async def search(self, query: str, limit: int = 5) -> ToolResult:
        """
        Ищет информацию в DuckDuckGo. Возвращает форматированный список сниппетов.
        """
        anti_seo_tags = "-site:pinterest.com"
        full_query = f"{query} {anti_seo_tags}".strip()

        # Проверяем кэш
        cache_key = f"{full_query}_{limit}"
        if cache_key in self.DDG_CACHE:
            system_logger.debug(f"[DDG Search] Отдача из кэша: '{query}'")
            return self.DDG_CACHE[cache_key]

        system_logger.info(f"[DDG Search] Запрос: '{query}'")

        data = {"q": full_query, "kl": "wt-wt"}  # Без региональной привязки

        try:
            resp = await self.api.client.post("https://lite.duckduckgo.com/lite/", data=data)

            if resp.status_code == 200:
                html = resp.text
                # Бьем HTML на блоки результатов (в Lite-версии они разделены тегами <tr>)
                blocks = html.split("<tr")

                results = []
                for block in blocks:
                    # Регулярки для вытаскивания данных из табличной верстки DDG Lite
                    link_match = re.search(r'class="result-url" href="([^"]+)"', block)
                    title_match = re.search(
                        r'class="result-url"[^>]*>(.*?)</a>', block, re.IGNORECASE
                    )
                    snippet_match = re.search(
                        r'class="result-snippet"[^>]*>(.*?)</td>', block, re.IGNORECASE
                    )

                    if link_match and title_match and snippet_match:
                        link = link_match.group(1)
                        # Очищаем от HTML-тегов (типа <b> для подсветки запроса)
                        title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
                        snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()

                        results.append(
                            f"{len(results)+1}. {title}\nURL: {link}\nСниппет: {snippet}"
                        )

                        if len(results) >= limit:
                            break

                if not results:
                    res_obj = ToolResult.fail(
                        msg=f"В DuckDuckGo по запросу '{query}' ничего не найдено."
                    )
                    self.DDG_CACHE[cache_key] = res_obj
                    return res_obj

                res_obj = ToolResult.ok(
                    msg=f"--- Результаты DuckDuckGo по запросу '{query}' ---\n\n"
                    + "\n\n".join(results),
                    data=results,
                )
                self.DDG_CACHE[cache_key] = res_obj
                return res_obj

            return ToolResult.fail(
                msg=f"Ошибка DuckDuckGo. HTTP Status: {resp.status_code}",
                error=f"HTTP {resp.status_code}: {resp.text}",
            )

        except Exception as e:
            system_logger.error(f"[DDG Search] Ошибка сети при поиске: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))
