import httpx
from src.l00_utils.managers.logger import system_logger
from src.l00_utils._tools import clean_html_to_md
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.l03_interfaces.type.api.habr.client import HabrClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class HabrNews(BaseInstrument):
    """
    Сервис для поиска и чтения новостей на Хабре.
    """

    def __init__(self, agent_client: "HabrClient"):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.http = agent_client.client

    @skill()
    async def search_news(self, query: str, limit: int = 5) -> ToolResult:
        """
        Поиск новостей по ключевым словам. Возвращает список ID и заголовков.
        """
        try:
            response = await self.http.get(
                "/articles/",
                params={
                    "query": query,
                    "news": "true",
                    "hl": "ru",
                    "fl": "ru",
                    "page": 1,
                    "period": "alltime"
                },
            )

            if response.status_code == 200:
                data = response.json()
                
                # Проверяем сначала newsIds, потом articleIds
                article_ids = data.get("newsIds") or data.get("articleIds",[])
                article_refs = data.get("newsRefs") or data.get("articleRefs", {})
                if not article_ids:
                    return ToolResult.fail(
                        msg=f"[Habr News] По запросу '{query}' ничего не найдено."
                    )

                result = [f"Результаты поиска новостей Хабр по запросу '{query}':"]

                # Ограничиваем выдачу
                for a_id in article_ids[:limit]:
                    article = article_refs.get(str(a_id), {})

                    title = clean_html_to_md(article.get("titleHtml", "Без названия"))
                    author = article.get("author", {}).get("alias", "Unknown")
                    score = article.get("statistics", {}).get("score", 0)
                    views = article.get("statistics", {}).get("readingCount", 0)

                    result.append(
                        f"- ID: {a_id} | Рейтинг: {score} | Просмотры: {views} | Автор: @{author}\n  Название: {title}"
                    )

                return ToolResult.ok(msg="\n\n".join(result), data=data)

            return ToolResult.fail(
                msg=f"Ошибка поиска новостей на Хабре. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Habr] Ошибка сети при поиске новостей: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при поиске новостей: {e}", error=str(e))

    @skill()
    async def get_news(self, limit: int = 5) -> ToolResult:
        """
        Получает список последних новостей (без фильтрации по запросу).
        Используем хаб 'news' для получения актуальной ленты.
        """
        try:
            response = await self.http.get(
                "/articles/",
                params={
                    "news": "true",
                    "sort": "date",
                    "hl": "ru",
                    "fl": "ru",
                    "page": 1,
                    "period": "daily"
                },
            )

            if response.status_code == 200:
                data = response.json()
                
                # Хабр для news=true возвращает newsIds и newsRefs вместо articleIds
                article_ids = data.get("newsIds") or data.get("articleIds",[])
                article_refs = data.get("newsRefs") or data.get("articleRefs", {})

                if not article_ids:
                    return ToolResult.fail(msg="[Habr News] Новых новостей пока нет.")

                result =["Последние новости на Хабре:"]

                for a_id in article_ids[:limit]:
                    article = article_refs.get(str(a_id), {})
                    title = clean_html_to_md(article.get("titleHtml", "Без названия"))
                    author = article.get("author", {}).get("alias", "Unknown")
                    score = article.get("statistics", {}).get("score", 0)

                    result.append(
                        f"- ID: {a_id} (Рейтинг: {score}) | Автор: @{author}\n  Название: {title}"
                    )

                return ToolResult.ok(msg="\n\n".join(result), data=data)

            return ToolResult.fail(
                msg=f"Ошибка получения списка новостей. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Habr] Ошибка сети при получении ленты новостей: {e}")
            return ToolResult.fail(
                msg=f"Ошибка сети при получении новостей: {e}", error=str(e)
            )