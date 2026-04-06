from datetime import datetime
from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.api.reddit.client import RedditClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class RedditProfile(BaseInstrument):
    """Сервис для сбора досье (профайлинга) и работы с аккаунтами Reddit."""

    def __init__(self, client: RedditClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.api = client.transport

    def _format_timestamp(self, utc_timestamp: float) -> str:
        """
        Вспомогательный метод для конвертации Unix времени в читаемый вид.
        """
        if not utc_timestamp:
            return "Неизвестно"
        return datetime.utcfromtimestamp(utc_timestamp).strftime("%Y-%m-%d")

    @skill()
    async def get_own_profile(self) -> ToolResult:
        """
        Получает сводную информацию о текущем профиле агента.
        """
        try:
            response = await self.api.request("GET", "api/v1/me")

            if response.status_code == 200:
                data = response.json()
                name = data.get("name", "Unknown")
                total_karma = data.get("total_karma", 0)
                comment_karma = data.get("comment_karma", 0)
                link_karma = data.get("link_karma", 0)
                registration_date = self._format_timestamp(data.get("created_utc"))

                karma_warning = (
                    "\nВажно: карма комментариев отрицательная. Reddit может ограничивать публикацию."
                    if comment_karma < 0
                    else ""
                )
                msg = f"--- Ваш профиль Reddit (u/{name}) ---\nДата регистрации: {registration_date}\nОбщая карма: {total_karma} (Посты: {link_karma} | Комментарии: {comment_karma}){karma_warning}"
                return ToolResult.ok(msg=msg, data=data)

            return ToolResult.fail(
                msg=f"Ошибка получения профиля. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка сети при запросе своего профиля: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при запросе профиля: {e}", error=str(e))

    @skill()
    async def get_user_profile(self, username: str) -> ToolResult:
        """
        Получает детальное досье на любого пользователя Reddit.
        """
        username = username.lstrip("u/").lstrip("/u/").strip()

        try:
            response = await self.api.request("GET", f"user/{username}/about")

            if response.status_code == 200:
                user_data = response.json().get("data", {})
                name = user_data.get("name", username)
                total_karma = user_data.get("total_karma", 0)
                comment_karma = user_data.get("comment_karma", 0)
                link_karma = user_data.get("link_karma", 0)
                registration_date = self._format_timestamp(user_data.get("created_utc"))

                status_tags = []
                if user_data.get("is_mod", False):
                    status_tags.append("Модератор")
                if user_data.get("is_gold", False):
                    status_tags.append("Premium")
                tags_str = f" | Теги: {', '.join(status_tags)}" if status_tags else ""

                msg = f"--- Пользователь Reddit: u/{name} ---\nДата регистрации: {registration_date}{tags_str}\nОбщая карма: {total_karma} (Посты: {link_karma} | Комментарии: {comment_karma})"
                return ToolResult.ok(msg=msg, data=user_data)

            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"Пользователь u/{username} не найден (возможно, удален или заблокирован Reddit/Shadowbanned).",
                    error="HTTP 404",
                )

            return ToolResult.fail(
                msg=f"Ошибка при получении профиля u/{username}. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка сети при запросе профиля u/{username}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при запросе досье: {e}", error=str(e))

    @skill()
    async def get_user_activity(self, username: str, limit: int = 5) -> ToolResult:
        """
        Получает последние комментарии и посты пользователя.
        """
        username = username.lstrip("u/").lstrip("/u/").strip()

        try:
            response = await self.api.request(
                "GET",
                f"user/{username}/overview",
                params={"limit": limit, "sort": "new"},
            )

            if response.status_code == 200:
                children = response.json().get("data", {}).get("children", [])
                if not children:
                    return ToolResult.ok(
                        msg=f"У пользователя u/{username} нет публичной активности (постов или комментариев).",
                        data=[],
                    )

                result = [f"Последняя активность u/{username}:"]
                for item in children:
                    kind, data = item.get("kind"), item.get("data", {})
                    subreddit, score = data.get("subreddit", "unknown"), data.get("score", 0)

                    if kind == "t1":
                        body = data.get("body", "")
                        if len(body) > 300:
                            body = body[:297] + "...[ОБРЕЗАНО]"
                        result.append(
                            f"- [Коммент в r/{subreddit}] (Карма: {score}): {body.replace(chr(10), ' ')}"
                        )
                    elif kind == "t3":
                        result.append(
                            f"- [Пост в r/{subreddit}] (Карма: {score}): {data.get('title', 'Без названия')}"
                        )

                return ToolResult.ok(msg="\n".join(result), data=children)

            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"Пользователь u/{username} не найден.", error="HTTP 404"
                )
            elif response.status_code == 403:
                return ToolResult.fail(
                    msg=f"Профиль u/{username} скрыт настройками приватности.",
                    error="HTTP 403",
                )

            return ToolResult.fail(
                msg=f"Ошибка получения активности. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка сети при запросе активности u/{username}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))
