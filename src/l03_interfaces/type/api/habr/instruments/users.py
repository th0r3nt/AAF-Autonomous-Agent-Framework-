import httpx
from src.l00_utils.managers.logger import system_logger
from src.l00_utils._tools import clean_html_to_md
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.api.habr.client import HabrClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class HabrUsers(BaseInstrument):
    """
    Сервис для сбора информации о пользователях Хабра.
    """

    def __init__(self, agent_client: 'HabrClient'):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.http = agent_client.client

    @skill()
    async def get_user_profile(self, username: str) -> ToolResult:
        """
        Получает детальную информацию о пользователе: карма, рейтинг, специализация, активность.
        """
        # Очищаем юзернейм от символа @, если агент случайно его передал
        username = username.lstrip("@").strip()

        try:
            # Эндпоинт Хабра для получения профиля (API v2)
            response = await self.http.get(f"/users/{username}/card", params={"hl": "ru", "fl": "ru"})

            if response.status_code == 200:
                data = response.json()

                # Базовая информация
                alias = data.get("alias", username)
                fullname = data.get("fullname")
                speciality = clean_html_to_md(data.get("speciality", "")) or "Не указана"

                # Репутация
                score_stats = data.get("scoreStats", {})
                karma = score_stats.get("score", 0)  # Карма (влияет на права)
                rating = data.get("rating", 0)  # Рейтинг (вклад в сообщество)

                # Статистика активности
                counters = data.get("counters", {})
                articles_count = counters.get("articles", 0)
                comments_count = counters.get("comments", 0)
                followers = counters.get("followers", 0)

                # Место работы (если есть)
                companies = data.get("companies", [])
                companies_str = ", ".join([clean_html_to_md(c.get("alias", "")) for c in companies])
                workplace = f"\nКомпании: {companies_str}" if companies_str else ""

                # Формируем имя для вывода
                display_name = f"{fullname} (@{alias})" if fullname else f"@{alias}"

                msg = (
                    f"--- Пользователь Хабр: {display_name} ---\n"
                    f"Специализация: {speciality}{workplace}\n"
                    f"Репутация: Карма {karma} | Рейтинг {rating}\n"
                    f"Активность: Статей {articles_count} | Комментариев {comments_count} | Подписчиков {followers}"
                )
                return ToolResult.ok(msg=msg, data=data)

            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"[Habr] Пользователь @{username} не найден.", error="HTTP 404"
                )

            return ToolResult.fail(
                msg=f"Ошибка при получении профиля пользователя. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Habr] Ошибка сети при запросе профиля @{username}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при запросе профиля: {e}", error=str(e))
