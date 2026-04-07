import httpx
from typing import TYPE_CHECKING, Literal

from src.l00_utils.managers.logger import system_logger
from src.l00_utils._tools import clean_html_to_md

if TYPE_CHECKING:
    from src.l03_interfaces.type.api.habr.client import HabrClient

from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class HabrArticles(BaseInstrument):
    """
    Сервис для поиска и чтения статей на Хабре.
    """

    def __init__(self, agent_client: "HabrClient"):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.http = agent_client.client

    @skill()
    async def search_articles(self, query: str, limit: int = 5) -> ToolResult:
        """
        Поиск статей по ключевым словам. Возвращает список ID и заголовков.
        """
        try:
            # Эндпоинт поиска Хабра
            response = await self.http.get(
                "/articles/",
                params={
                    "query": query, 
                    "hl": "ru", 
                    "fl": "ru", 
                    "page": 1,
                    "order": "relevance",
                    "period": "alltime" 
                },
            )

            if response.status_code == 200:
                data = response.json()
                article_ids = data.get("articleIds", [])
                article_refs = data.get("articleRefs", {})

                if not article_ids:
                    return ToolResult.fail(
                        msg=f"[Habr] По запросу '{query}' ничего не найдено."
                    )

                result = [f"Результаты поиска Хабр по запросу '{query}':"]

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
                msg=f"Ошибка поиска на Хабре. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Habr] Ошибка сети при поиске статей: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при поиске на Хабре: {e}", error=str(e))

    @skill()
    async def get_article(self, article_id: int | str) -> ToolResult:
        """
        Получает полный текст статьи, её рейтинг, хабы и автора.
        """
        try:
            response = await self.http.get(
                f"/articles/{article_id}", params={"hl": "ru", "fl": "ru"}
            )

            if response.status_code == 200:
                data = response.json()

                title = clean_html_to_md(data.get("titleHtml", "Без названия"))
                author = data.get("author", {}).get("alias", "Unknown")

                # Статистика
                stats = data.get("statistics", {})
                score = stats.get("score", 0)
                views = stats.get("readingCount", 0)
                comments = stats.get("commentsCount", 0)
                bookmarks = stats.get("favoritesCount", 0)

                # Хабы (теги)
                hubs_list = [h.get("titleHtml", "") for h in data.get("hubs", [])]
                hubs_str = ", ".join([clean_html_to_md(h) for h in hubs_list])

                # Текст статьи
                raw_body = data.get("textHtml", "")
                clean_body = clean_html_to_md(raw_body)

                if not clean_body:
                    clean_body = "*Текст статьи недоступен или пуст.*"

                # Защита от переполнения контекста
                max_chars = 30000
                if len(clean_body) > max_chars:
                    clean_body = (
                        clean_body[:max_chars]
                        + f"\n\n...[СТАТЬЯ ОБРЕЗАНА: ПРЕВЫШЕН ЛИМИТ В {max_chars} СИМВОЛОВ]..."
                    )

                msg = (
                    f"--- Статья Хабр ID: {article_id} ---\n"
                    f"Название: {title}\n"
                    f"Автор: @{author} | Хабы: {hubs_str}\n"
                    f"Рейтинг: {score} | Просмотры: {views} | В закладках: {bookmarks} | Комментарии: {comments}\n"
                    f"--- Текст ---\n"
                    f"{clean_body}"
                )
                return ToolResult.ok(msg=msg, data=data)

            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"[Habr] Статья с ID {article_id} не найдена.", error="HTTP 404"
                )

            return ToolResult.fail(
                msg=f"Ошибка получения статьи. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Habr] Ошибка сети при запросе статьи {article_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при запросе статьи: {e}", error=str(e))

    @skill()
    async def get_hub_feed(
        self, hub_alias: str, sort_by: Literal["date", "rating"], limit: int = 5
    ) -> ToolResult:
        """
        Получает последние статьи из конкретного хаба.
        """
        try:
            params = {
                "hub": hub_alias,
                "sort": sort_by,
                "hl": "ru",
                "fl": "ru",
                "page": 1,
                "period": "daily"
            }

            response = await self.http.get("/articles/", params=params)

            if response.status_code == 200:
                data = response.json()
                article_ids = data.get("articleIds", [])
                article_refs = data.get("articleRefs", {})

                if not article_ids:
                    return ToolResult.fail(
                        msg=f"[Habr] В хабе '{hub_alias}' нет новых статей или хаб не существует."
                    )

                result = [f"Последние статьи в хабе '{hub_alias}':"]

                for a_id in article_ids[:limit]:
                    article = article_refs.get(str(a_id), {})
                    title = clean_html_to_md(article.get("titleHtml", "Без названия"))
                    score = article.get("statistics", {}).get("score", 0)

                    result.append(f"- ID: {a_id} (Рейтинг: {score}): {title}")

                return ToolResult.ok(msg="\n".join(result), data=data) #

            return ToolResult.fail(
                msg=f"Ошибка получения ленты хаба. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Habr] Ошибка сети при запросе хаба {hub_alias}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))
