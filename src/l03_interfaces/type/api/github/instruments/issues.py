import httpx

from src.l03_interfaces.type.base import BaseInstrument
from src.l00_utils.managers.logger import system_logger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.api.github.client import GithubClient
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill


class GithubIssue(BaseInstrument):

    def __init__(self, agent_client: 'GithubClient'):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.http = agent_client.client

    def _clean_repo_name(self, repo_name: str) -> str:
        repo_name = repo_name.strip()
        if "github.com/" in repo_name:
            repo_name = repo_name.split("github.com/")[-1]
        return repo_name.strip("/")

    @skill()
    async def get_issue(self, repo_name: str, issue_number: int) -> ToolResult:
        """
        Показывает issue переданного репозитория.
        """
        repo_name = self._clean_repo_name(repo_name)
        try:
            response = await self.http.get(f"/repos/{repo_name}/issues/{issue_number}")

            if response.status_code == 200:
                data = response.json()
                is_pr = "pull_request" in data
                type_str = "Pull Request" if is_pr else "Issue"

                title = data.get("title", "Без названия")
                state = data.get("state", "unknown")
                author = data.get("user", {}).get("login", "Unknown")
                body = data.get("body") or "*Пустое описание*"
                labels = [label.get("name") for label in data.get("labels", [])]
                labels_str = ", ".join(labels) if labels else "Нет"

                msg = (
                    f"[{type_str} #{issue_number}] {title}\n"
                    f"Статус: {state.upper()} | Автор: @{author} | Лейблы: {labels_str}\n"
                    f"--- Описание ---\n{body}"
                )
                return ToolResult.ok(msg=msg, data=data)

            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"Issue #{issue_number} не найдено в репозитории {repo_name}.",
                    error="HTTP 404",
                )

            return ToolResult.fail(
                msg=f"Ошибка при получении Issue. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка сети при получении Issue #{issue_number}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при запросе Issue: {e}", error=str(e))

    @skill()
    async def get_issue_comments(
        self, repo_name: str, issue_number: int, limit: int = 15
    ) -> ToolResult:
        """
        Показывает последние n комментариев к issue переданного репозитория.
        """
        repo_name = self._clean_repo_name(repo_name)
        try:
            response = await self.http.get(
                f"/repos/{repo_name}/issues/{issue_number}/comments",
                params={"per_page": min(limit, 100)},
            )

            if response.status_code == 200:
                comments = response.json()
                if not comments:
                    return ToolResult.ok(
                        msg=f"В Issue #{issue_number} пока нет комментариев.", data=[]
                    )

                if len(comments) > limit:
                    comments = comments[-limit:]

                result = [f"Последние {len(comments)} комментариев в Issue #{issue_number}:"]
                for c in comments:
                    author = c.get("user", {}).get("login", "Unknown")
                    date = c.get("updated_at", "").replace("T", " ").replace("Z", "")
                    body = c.get("body", "")
                    result.append(f"\n[ID: {c.get('id')} | @{author} | {date}]\n{body}")

                return ToolResult.ok(msg="\n".join(result), data=comments)

            return ToolResult.fail(
                msg=f"Ошибка при получении комментариев. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(
                f"[GitHub] Ошибка сети при чтении комментариев #{issue_number}: {e}"
            )
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))

    @skill()
    async def create_issue_comment(
        self, repo_name: str, issue_number: int, body: str
    ) -> ToolResult:
        """
        Создает комментарий к переданному issue репозитория.
        """
        repo_name = self._clean_repo_name(repo_name)
        try:
            response = await self.http.post(
                f"/repos/{repo_name}/issues/{issue_number}/comments",
                json={"body": body},
            )

            if response.status_code == 201:
                data = response.json()
                comment_url = data.get("html_url", "")
                system_logger.info(
                    f"[GitHub] Комментарий в {repo_name}#{issue_number} успешно опубликован."
                )
                return ToolResult.ok(
                    msg=f"Комментарий успешно опубликован ({comment_url}).", data=data
                )

            return ToolResult.fail(
                msg=f"Не удалось опубликовать комментарий. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка отправки комментария в #{issue_number}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при отправке комментария: {e}", error=str(e))

    @skill()
    async def create_issue(
        self, repo_name: str, title: str, body: str, labels: list[str] = None
    ) -> ToolResult:
        """
        Создает issue к переданному репозиторию.
        """
        repo_name = self._clean_repo_name(repo_name)
        payload = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels

        try:
            response = await self.http.post(f"/repos/{repo_name}/issues", json=payload)

            if response.status_code == 201:
                data = response.json()
                issue_number = data.get("number")
                url = data.get("html_url")
                system_logger.info(f"[GitHub] Создано Issue #{issue_number} в {repo_name}")
                return ToolResult.ok(
                    msg=f"Issue #{issue_number} '{title}' успешно создано. Ссылка: {url}",
                    data=data,
                )

            return ToolResult.fail(
                msg=f"Ошибка создания Issue. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка создания Issue в {repo_name}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при создании Issue: {e}", error=str(e))

    @skill()
    async def manage_issue(
        self,
        repo_name: str,
        issue_number: int,
        state: str = None,
        labels: list[str] = None,
    ) -> ToolResult:
        """Взаимодействие с issue."""

        repo_name = self._clean_repo_name(repo_name)
        payload = {}

        if state:
            if state.lower() not in ["open", "closed"]:
                return ToolResult.fail(
                    msg="Ошибка: параметр 'state' должен быть либо 'open', либо 'closed'."
                )
            payload["state"] = state.lower()

        if labels is not None:
            payload["labels"] = labels

        if not payload:
            return ToolResult.fail(msg="Не передано параметров для изменения (state или labels).")

        try:
            response = await self.http.patch(
                f"/repos/{repo_name}/issues/{issue_number}", json=payload
            )

            if response.status_code == 200:
                res_parts = []
                if state:
                    res_parts.append(f"Статус изменен на '{state}'")
                if labels is not None:
                    res_parts.append(f"Лейблы обновлены на {labels}")

                system_logger.info(
                    f"[GitHub] Обновлено Issue #{issue_number} в {repo_name}: {', '.join(res_parts)}"
                )
                return ToolResult.ok(
                    msg=f"Issue #{issue_number} успешно обновлено. {', '.join(res_parts)}.",
                    data=response.json(),
                )

            return ToolResult.fail(
                msg=f"Ошибка обновления Issue. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка обновления Issue #{issue_number}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при обновлении Issue: {e}", error=str(e))
