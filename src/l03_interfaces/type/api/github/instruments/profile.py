import httpx

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.base import BaseInstrument
from src.l03_interfaces.type.api.github.client import GithubClient
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill


class GithubProfile(BaseInstrument):
    """Сервис для работы с профилями GitHub (своим и чужими)."""

    def __init__(self, agent_client: GithubClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.http = agent_client.client

    @skill()
    async def get_own_profile(self) -> ToolResult:
        """
        Получает базовую информацию о текущем профиле агента.
        """
        try:
            response = await self.http.get("/user")

            if response.status_code == 200:
                data = response.json()
                login = data.get("login")
                name = data.get("name") or "Не указано"
                bio = data.get("bio") or "Нет описания"
                repos = data.get("public_repos", 0)
                followers = data.get("followers", 0)

                result = (
                    f"GitHub профиль:\n"
                    f"Username: @{login}\n"
                    f"Имя: {name}\n"
                    f"Bio: {bio}\n"
                    f"Публичных репозиториев: {repos} | Подписчиков: {followers}"
                )
                return ToolResult.ok(msg=result, data=data)

            return ToolResult.fail(
                msg=f"Ошибка получения профиля. HTTP Status: {response.status_code}",
                error=f"HTTP {response.status_code}: {response.text}",
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка сети при получении профиля: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при получении профиля: {e}", error=str(e))

    @skill()
    async def update_own_profile(
        self,
        name: str = None,
        bio: str = None,
        blog: str = None,
        company: str = None,
        location: str = None,
    ) -> ToolResult:
        """
        Изменяет публичную информацию профиля агента.
        """

        # Собираем только те поля, которые агент решил обновить
        payload = {}
        if name is not None:
            payload["name"] = name
        if bio is not None:
            payload["bio"] = bio
        if blog is not None:
            payload["blog"] = blog
        if company is not None:
            payload["company"] = company
        if location is not None:
            payload["location"] = location

        if not payload:
            return ToolResult.fail(msg="Нет данных для обновления.")

        try:
            response = await self.http.patch("/user", json=payload)
            if response.status_code == 200:
                updated_keys = ", ".join(payload.keys())
                system_logger.info(f"[GitHub] Профиль обновлен. Изменены поля: {updated_keys}")
                return ToolResult.ok(
                    msg=f"Профиль успешно обновлен. Изменены поля: {updated_keys}",
                    data=payload,
                )

            return ToolResult.fail(
                msg=f"Ошибка обновления профиля. HTTP Status: {response.status_code}. Ответ: {response.text}",
                error=f"HTTP {response.status_code}: {response.text}",
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка сети при обновлении профиля: {e}")
            return ToolResult.fail(msg=f"Ошибка при обновлении профиля: {e}", error=str(e))

    @skill()
    async def get_user_profile(self, username: str) -> ToolResult:
        """
        Получает сводку по чужому GitHub-аккаунту.
        """
        username = username.lstrip("@")

        try:
            response = await self.http.get(f"/users/{username}")

            if response.status_code == 200:
                data = response.json()
                name = data.get("name") or "Не указано"
                bio = data.get("bio") or "Нет описания"
                company = data.get("company") or "Не указано"
                repos = data.get("public_repos", 0)
                followers = data.get("followers", 0)

                result = (
                    f"Профиль @{username}:\n"
                    f"Имя: {name}\n"
                    f"Компания: {company}\n"
                    f"Bio: {bio}\n"
                    f"Репозиториев: {repos} | Подписчиков: {followers}\n"
                    f"Ссылка: {data.get('html_url')}"
                )

                return ToolResult.ok(msg=result, data=data)

            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"Пользователь @{username} не найден на GitHub.",
                    error=f"Пользователь @{username} не найден на GitHub.",
                )

            return ToolResult.fail(
                msg=f"Ошибка запроса. HTTP {response.status_code}: {response.text}",
                error=f"HTTP {response.status_code}: {response.text}",
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка сети при запросе профиля {username}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при поиске пользователя: {e}", error=str(e))

    @skill()
    async def follow_user(self, username: str) -> ToolResult:
        """
        Подписывается на разработчика (Follow).
        """
        username = username.lstrip("@")
        try:
            # GitHub API требует PUT запрос без тела для подписки
            response = await self.http.put(f"/user/following/{username}")
            if response.status_code == 204:
                system_logger.info(f"[GitHub] Успешная подписка на @{username}")
                return ToolResult.ok(msg=f"Успешная подписка на @{username}.")

            return ToolResult.fail(
                msg=f"Не удалось подписаться на @{username}. HTTP {response.status_code}",
                error=f"HTTP {response.status_code}: {response.text}",
            )

        except httpx.RequestError as e:
            return ToolResult.fail(msg=f"Ошибка при попытке подписки: {e}", error=str(e))

    @skill()
    async def get_user_repositories(self, username: str, limit: int = 5) -> ToolResult:
        """
        Получает список публичных репозиториев пользователя.
        """
        username = username.lstrip("@")
        try:
            # Запрашиваем репозитории, сортируем по дате обновления
            response = await self.http.get(
                f"/users/{username}/repos",
                params={"sort": "updated", "per_page": limit},
            )

            if response.status_code == 200:
                repos = response.json()
                if not repos:
                    return ToolResult.fail(f"У @{username} нет публичных репозиториев.")

                result = [f"Последние репозитории пользователя @{username}:"]
                for repo in repos:
                    name = repo.get("name")
                    stars = repo.get("stargazers_count", 0)
                    lang = repo.get("language") or "Не определен"
                    desc = repo.get("description") or "Без описания"

                    if len(desc) > 80:
                        desc = desc[:77] + "..."

                    result.append(f"- {name} [{lang}] (⭐ {stars}): {desc}")

                return ToolResult.ok(msg="\n".join(result), data=repos)

            elif response.status_code == 404:
                return ToolResult.fail(msg=f"Пользователь @{username} не найден на GitHub.")

            return ToolResult.fail(
                msg=f"Ошибка при получении репозиториев. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка сети при запросе репозиториев {username}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}")
