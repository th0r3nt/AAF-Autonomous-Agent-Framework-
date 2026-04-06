import httpx

from src.l03_interfaces.type.base import BaseInstrument
from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.api.github.client import GithubClient
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill


class GithubRepository(BaseInstrument):
    """Сервис для работы с репозиториями (поиск, информация, ветки, форки)."""

    def __init__(self, agent_client: GithubClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.http = agent_client.client

    def _clean_repo_name(self, repo_name: str) -> str:
        """Вспомогательный метод. Убирает домен, если агент передал полную ссылку."""
        repo_name = repo_name.strip()
        if "github.com/" in repo_name:
            repo_name = repo_name.split("github.com/")[-1]
        return repo_name.strip("/")

    @skill()
    async def get_repository_info(self, repo_name: str) -> ToolResult:
        """
        Получает сводную информацию о репозитории (звезды, форки, язык, открытые issue).
        Ожидает формат 'owner/repo'.
        """
        repo_name = self._clean_repo_name(repo_name)
        try:
            response = await self.http.get(f"/repos/{repo_name}")

            if response.status_code == 200:
                data = response.json()
                desc = data.get("description") or "Без описания"
                lang = data.get("language") or "Не определен"
                stars = data.get("stargazers_count", 0)
                forks = data.get("forks_count", 0)
                issues = data.get("open_issues_count", 0)
                branch = data.get("default_branch", "main")
                visibility = "Private" if data.get("private") else "Public"

                result = (
                    f"Репозиторий: {repo_name} [{visibility}]\n"
                    f"Описание: {desc}\n"
                    f"Язык: {lang} | Ветка по умолчанию: {branch}\n"
                    f"Stars: {stars} | Forks: {forks} | Открытых Issue/PR: {issues}"
                )
                return ToolResult.ok(msg=result, data=data)
            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"Репозиторий '{repo_name}' не найден.", error="HTTP 404"
                )

            return ToolResult.fail(
                msg=f"Ошибка запроса. HTTP Status: {response.status_code}",
                error=f"HTTP {response.status_code}: {response.text}",
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка сети при запросе репо {repo_name}: {e}")
            return ToolResult.fail(
                msg=f"Ошибка сети при запросе информации о репозитории: {e}",
                error=str(e),
            )

    @skill()
    async def search_repositories(self, query: str, limit: int = 5) -> ToolResult:
        """
        Ищет репозитории по всему GitHub.
        """
        try:
            response = await self.http.get(
                "/search/repositories",
                params={"q": query, "per_page": limit, "sort": "stars"},
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                if not items:
                    return ToolResult.fail(msg=f"По запросу '{query}' репозитории не найдены.")

                result = [f"Результаты поиска по запросу '{query}':"]
                for repo in items:
                    name = repo.get("full_name")
                    stars = repo.get("stargazers_count", 0)
                    desc = repo.get("description") or "Без описания"
                    if len(desc) > 150:
                        desc = desc[:147] + "..."
                    result.append(f"- {name} (⭐ {stars}): {desc}")

                return ToolResult.ok(msg="\n".join(result), data=data)

            return ToolResult.fail(
                msg=f"Ошибка поиска. HTTP Status: {response.status_code}",
                error=f"HTTP {response.status_code}: {response.text}",
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка сети при поиске репозиториев: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при поиске: {e}", error=str(e))

    @skill()
    async def list_branches(self, repo_name: str) -> ToolResult:
        """
        Получает список веток в репозитории (до 30 штук).
        """
        repo_name = self._clean_repo_name(repo_name)
        try:
            response = await self.http.get(f"/repos/{repo_name}/branches")

            if response.status_code == 200:
                branches = response.json()
                if not branches:
                    return ToolResult.fail(msg=f"В репозитории {repo_name} нет доступных веток.")

                branch_names = [b.get("name") for b in branches]
                return ToolResult.ok(
                    msg=f"Ветки репозитория {repo_name}:\n" + ", ".join(branch_names),
                    data=branches,
                )

            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"Репозиторий '{repo_name}' не найден.", error="HTTP 404"
                )

            return ToolResult.fail(
                msg=f"Ошибка запроса веток. HTTP Status: {response.status_code}",
                error=f"HTTP {response.status_code}: {response.text}",
            )

        except httpx.RequestError as e:
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))

    @skill()
    async def fork_repository(self, repo_name: str) -> ToolResult:
        """
        Форкает чужой репозиторий в аккаунт агента.
        Необходимо для того, чтобы агент мог вносить изменения и делать Pull Requests.
        """
        repo_name = self._clean_repo_name(repo_name)
        try:
            # POST запрос без тела создает форк
            response = await self.http.post(f"/repos/{repo_name}/forks")

            if response.status_code in [202, 200]:
                data = response.json()
                fork_name = data.get("full_name")
                system_logger.info(f"[GitHub] Успешно создан форк: {fork_name}")
                result = (
                    f"Репозиторий {repo_name} успешно форкнут.\n"
                    f"Теперь копия доступна по адресу: {fork_name}\n"
                    f"GitHub может потребоваться пара минут на полное копирование файлов."
                )
                return ToolResult.ok(msg=result, data=data)

            return ToolResult.fail(
                msg=f"Ошибка при создании форка. HTTP {response.status_code}: {response.text}",
                error=f"HTTP {response.status_code}",
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка форка {repo_name}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при создании форка: {e}", error=str(e))

    @skill()
    async def star_repository(self, repo_name: str) -> ToolResult:
        """
        Ставит звездочку репозиторию.
        """
        repo_name = self._clean_repo_name(repo_name)
        try:
            response = await self.http.put(f"/user/starred/{repo_name}")
            if response.status_code == 204:
                return ToolResult.ok(
                    msg=f"Репозиторию {repo_name} успешно поставлена звездочка (Star)."
                )
            return ToolResult.fail(
                msg=f"Не удалось поставить звезду. HTTP {response.status_code}",
                error=f"HTTP {response.status_code}",
            )
        except httpx.RequestError as e:
            return ToolResult.fail(msg=f"Ошибка при попытке поставить звезду: {e}", error=str(e))
