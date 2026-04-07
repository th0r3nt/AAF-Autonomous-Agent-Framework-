from src.l00_utils.managers.logger import system_logger

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from src.l03_interfaces.type.api.reddit.client import RedditClient

from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class RedditSubreddits(BaseInstrument):
    """Сервис для поиска сабреддитов, чтения правил и получения постов."""

    def __init__(self, client: "RedditClient"):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.api = client

    def _clean_sub_name(self, name: str) -> str:
        """
        Вспомогательный метод. Убирает r/ и слэши из названия саба.
        """
        return name.lstrip("r/").lstrip("/r/").strip()

    @skill()
    async def get_subreddit_info(self, subreddit: str) -> ToolResult:
        """
        Получает базовую информацию о сабреддите (описание, онлайн, NSFW).
        """
        subreddit = self._clean_sub_name(subreddit)

        try:
            response = await self.api.request("GET", f"r/{subreddit}/about")

            if response.status_code == 200:
                data = response.json().get("data", {})

                title = data.get("title", subreddit)
                public_description = data.get("public_description", "Нет описания")
                subscribers = data.get("subscribers", 0)
                active_users = data.get("active_user_count", 0)
                over18 = data.get("over18", False)

                nsfw_warning = "\nNSFW: True." if over18 else ""

                msg = (
                    f"--- Сабреддит: r/{subreddit} ---\n"
                    f"Название: {title}\n"
                    f"Подписчиков: {subscribers} | Сейчас онлайн: {active_users}{nsfw_warning}\n"
                    f"Описание: {public_description}"
                )
                return ToolResult.ok(msg=msg, data=data)

            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"Сабреддит r/{subreddit} не найден.", error="HTTP 404"
                )
            elif response.status_code == 403:
                return ToolResult.fail(
                    msg=f"Доступ к r/{subreddit} запрещен (Private сообщество).",
                    error="HTTP 403",
                )

            return ToolResult.fail(
                msg=f"Ошибка при получении информации о r/{subreddit}. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка сети при запросе r/{subreddit}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))

    @skill()
    async def get_subreddit_rules(self, subreddit: str) -> ToolResult:
        """
        Получает правила сабреддита.
        """
        subreddit = self._clean_sub_name(subreddit)

        try:
            response = await self.api.request("GET", f"r/{subreddit}/about/rules")

            if response.status_code == 200:
                rules = response.json().get("rules", [])

                if not rules:
                    return ToolResult.ok(
                        msg=f"В r/{subreddit} нет явно заданных правил. Рекомендуется придерживаться общих правил Reddit (Reddiquette).",
                        data=[],
                    )

                result = [
                    f"--- ПРАВИЛА СООБЩЕСТВА r/{subreddit} ---",
                    "Нарушение приведет к бану.",
                ]

                for idx, rule in enumerate(rules, 1):
                    short_name = rule.get("short_name", "Правило")
                    desc = rule.get("description", "")
                    if desc and len(desc) > 500:
                        desc = desc[:497] + "..."
                    desc_str = f"\n  Детали: {desc}" if desc else ""
                    result.append(f"{idx}. {short_name}{desc_str}")

                return ToolResult.ok(msg="\n".join(result), data=rules)

            return ToolResult.fail(
                msg=f"Ошибка получения правил. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка сети при запросе правил r/{subreddit}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при получении правил: {e}", error=str(e))

    @skill()
    async def search_subreddits(self, query: str, limit: int = 5) -> ToolResult:
        """Ищет сообщества по ключевому слову."""
        try:
            response = await self.api.request(
                "GET",
                "subreddits/search",
                params={"q": query, "limit": limit, "sort": "relevance"},
            )

            if response.status_code == 200:
                children = response.json().get("data", {}).get("children", [])

                if not children:
                    return ToolResult.fail(msg=f"По запросу '{query}' сабреддиты не найдены.")

                result = [f"Найденные сообщества по запросу '{query}':"]
                for item in children:
                    data = item.get("data", {})
                    name = data.get("display_name", "unknown")
                    subs = data.get("subscribers", 0)
                    desc = data.get("public_description", "").replace("\n", " ")
                    if len(desc) > 100:
                        desc = desc[:97] + "..."
                    result.append(f"- r/{name} (Подписчиков: {subs}): {desc}")

                return ToolResult.ok(msg="\n".join(result), data=children)

            return ToolResult.fail(
                msg=f"Ошибка поиска сообществ. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка сети при поиске сабреддитов: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при поиске: {e}", error=str(e))

    @skill()
    async def get_subreddit_feed(
        self,
        subreddit: str,
        sort_by: Literal["hot", "new", "top", "rising"] = "hot",
        limit: int = 5,
    ) -> ToolResult:
        """
        Получает ленту постов из саба.
        """
        subreddit = self._clean_sub_name(subreddit)
        if sort_by not in ["hot", "new", "top", "rising"]:
            sort_by = "hot"

        try:
            endpoint = f"r/{subreddit}/{sort_by}" if subreddit.lower() != "all" else sort_by

            response = await self.api.request("GET", endpoint, params={"limit": limit})

            if response.status_code == 200:
                children = response.json().get("data", {}).get("children", [])

                if not children:
                    return ToolResult.fail(msg=f"Лента r/{subreddit} пуста или не существует.")

                result = [f"--- Лента r/{subreddit} (Сортировка: {sort_by.upper()}) ---"]
                for item in children:
                    data = item.get("data", {})
                    post_id = data.get("id")
                    title = data.get("title", "Без названия")
                    author = data.get("author", "unknown")
                    score = data.get("score", 0)
                    comments_count = data.get("num_comments", 0)
                    is_pinned = data.get("stickied", False)
                    pin_marker = "[ЗАКРЕП] " if is_pinned else ""
                    result.append(
                        f"{pin_marker}ID: {post_id} | Рейтинг: {score} | Комментов: {comments_count} | Автор: u/{author}\n"
                        f"Заголовок: {title}"
                    )

                return ToolResult.ok(msg="\n\n".join(result), data=children)

            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"Сабреддит r/{subreddit} не найден.", error="HTTP 404"
                )

            return ToolResult.fail(
                msg=f"Ошибка получения ленты. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка сети при чтении ленты r/{subreddit}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при получении постов: {e}", error=str(e))
