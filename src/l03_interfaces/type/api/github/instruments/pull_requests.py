import httpx

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.base import BaseInstrument
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.api.github.client import GithubClient
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill


class GithubPullRequest(BaseInstrument):
    """Сервис для работы с Pull Requests (просмотр кода, код-ревью, создание и слияние)."""

    def __init__(self, agent_client: 'GithubClient'):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.http = agent_client.client

    def _clean_repo_name(self, repo_name: str) -> str:
        """Очищает ссылку, оставляя только 'owner/repo'."""
        repo_name = repo_name.strip()
        if "github.com/" in repo_name:
            repo_name = repo_name.split("github.com/")[-1]
        return repo_name.strip("/")

    @skill()
    async def get_pull_request_info(self, repo_name: str, pr_number: int) -> ToolResult:
        """
        Получает сводную информацию о PR (Ветки, статус слияния, описание).
        """
        repo_name = self._clean_repo_name(repo_name)
        try:
            response = await self.http.get(f"/repos/{repo_name}/pulls/{pr_number}")

            if response.status_code == 200:
                data = response.json()
                title = data.get("title", "Без названия")
                state = data.get("state", "unknown")
                author = data.get("user", {}).get("login", "Unknown")
                body = data.get("body") or "*Пустое описание*"

                head_branch = data.get("head", {}).get("ref", "unknown")
                base_branch = data.get("base", {}).get("ref", "unknown")

                mergeable = data.get(
                    "mergeable"
                )  # True, False, или None (если GitHub еще вычисляет)
                merge_status = (
                    "Можно сливать (Mergeable)"
                    if mergeable
                    else "ЕСТЬ КОНФЛИКТЫ (или не проверено)"
                )

                additions = data.get("additions", 0)
                deletions = data.get("deletions", 0)
                changed_files = data.get("changed_files", 0)

                msg = (
                    f"[Pull Request #{pr_number}] {title}\n"
                    f"Статус: {state.upper()} | Автор: @{author}\n"
                    f"Направление: {head_branch} -> {base_branch}\n"
                    f"Состояние конфликтов: {merge_status}\n"
                    f"Изменения: {changed_files} файлов (+{additions} / -{deletions} строк)\n"
                    f"--- Описание ---\n"
                    f"{body}"
                )
                return ToolResult.ok(msg=msg, data=data)
            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"PR #{pr_number} не найден в {repo_name}.", error="HTTP 404"
                )

            return ToolResult.fail(
                msg=f"Ошибка при получении PR. HTTP Status: {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка сети при запросе PR #{pr_number}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))

    @skill()
    async def get_pull_request_changes(
        self, repo_name: str, pr_number: int, max_files: int = 10
    ) -> ToolResult:
        """
        Получает DIFF (изменения в коде) для проведения Code Review.
        Защищено лимитами, чтобы не переполнить контекст LLM.
        """
        repo_name = self._clean_repo_name(repo_name)
        try:
            response = await self.http.get(
                f"/repos/{repo_name}/pulls/{pr_number}/files",
                params={"per_page": max_files},
            )

            if response.status_code == 200:
                files = response.json()
                if not files:
                    return ToolResult.ok(msg=f"В PR #{pr_number} нет измененных файлов.", data=[])

                result = [f"Измененные файлы в PR #{pr_number} (показано до {max_files} файлов):"]

                for f in files:
                    filename = f.get("filename")
                    status = f.get("status")  # added, modified, removed
                    additions = f.get("additions", 0)
                    deletions = f.get("deletions", 0)
                    patch = f.get("patch")  # Это сам diff (куски кода)

                    file_header = (
                        f"\n📄 Файл: {filename} [{status.upper()}] (+{additions}/-{deletions})"
                    )
                    result.append(file_header)

                    if patch:
                        if len(patch) > 3000:
                            patch = patch[:3000] + "\n...[ДИФФ ОБРЕЗАН ДЛЯ ЭКОНОМИИ КОНТЕКСТА] ..."
                        result.append("```diff\n" + patch + "\n```")
                    else:
                        result.append(
                            "*Нет доступного текстового патча (возможно бинарный файл или слишком большой)*"
                        )

                return ToolResult.ok(msg="\n".join(result), data=files)

            return ToolResult.fail(
                msg=f"Ошибка получения файлов PR. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка запроса diff для PR #{pr_number}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при запросе изменений кода: {e}", error=str(e))

    @skill()
    async def submit_pull_request_review(
        self, repo_name: str, pr_number: int, event: str, body: str
    ) -> ToolResult:
        """
        Отправляет формальное Code Review.
        :param event: Должен быть 'APPROVE', 'REQUEST_CHANGES' или 'COMMENT'.
        """
        repo_name = self._clean_repo_name(repo_name)
        event = event.upper()

        if event not in ["APPROVE", "REQUEST_CHANGES", "COMMENT"]:
            return ToolResult.fail(
                msg="Ошибка: event должен быть APPROVE, REQUEST_CHANGES или COMMENT."
            )

        try:
            payload = {"event": event, "body": body}
            response = await self.http.post(
                f"/repos/{repo_name}/pulls/{pr_number}/reviews", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                review_url = data.get("html_url", "")
                system_logger.info(
                    f"[GitHub] Оставлено ревью ({event}) для PR #{pr_number} в {repo_name}."
                )
                return ToolResult.ok(
                    msg=f"Code Review ({event}) успешно опубликовано ({review_url}).",
                    data=data,
                )

            return ToolResult.fail(
                msg=f"Ошибка публикации ревью. HTTP {response.status_code}: {response.text}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка отправки ревью в PR #{pr_number}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при отправке ревью: {e}", error=str(e))

    @skill()
    async def merge_pull_request(
        self, repo_name: str, pr_number: int, merge_method: str = "squash"
    ) -> ToolResult:
        """
        Сливает PR в целевую ветку.
        :param merge_method: 'merge', 'squash', или 'rebase' (рекомендуется squash для чистоты истории).
        """
        repo_name = self._clean_repo_name(repo_name)
        if merge_method not in ["merge", "squash", "rebase"]:
            merge_method = "squash"

        try:
            payload = {"merge_method": merge_method}
            response = await self.http.put(
                f"/repos/{repo_name}/pulls/{pr_number}/merge", json=payload
            )

            if response.status_code == 200:
                data = response.json()
                msg = data.get("message", "Merged")
                system_logger.info(
                    f"[GitHub] PR #{pr_number} в {repo_name} успешно слит ({merge_method})."
                )
                return ToolResult.ok(
                    msg=f"Pull Request #{pr_number} успешно слит. ({msg})", data=data
                )

            elif response.status_code == 405:
                return ToolResult.fail(
                    msg=f"Слияние отклонено (HTTP 405): {response.text}",
                    error="HTTP 405",
                )

            return ToolResult.fail(
                msg=f"Ошибка слияния PR. HTTP {response.status_code}: {response.text}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка слияния PR #{pr_number}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при слиянии: {e}", error=str(e))

    @skill()
    async def create_pull_request(
        self,
        repo_name: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
    ) -> ToolResult:
        """
        Создает новый Pull Request (например, из ветки агента в main).
        """
        repo_name = self._clean_repo_name(repo_name)
        try:
            payload = {
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch,
            }
            response = await self.http.post(f"/repos/{repo_name}/pulls", json=payload)

            if response.status_code == 201:
                data = response.json()
                pr_number = data.get("number")
                url = data.get("html_url")
                system_logger.info(
                    f"[GitHub] Открыт новый PR #{pr_number} в {repo_name} ({head_branch} -> {base_branch})"
                )
                return ToolResult.ok(
                    msg=f"Pull Request #{pr_number} '{title}' успешно создан! Ссылка: {url}",
                    data=data,
                )

            elif response.status_code == 422:
                return ToolResult.fail(
                    msg=f"Ошибка 422: Невозможно создать PR. Детали: {response.text}",
                    error="HTTP 422",
                )

            return ToolResult.fail(
                msg=f"Ошибка создания PR. HTTP {response.status_code}: {response.text}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка создания PR в {repo_name}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при создании PR: {e}", error=str(e))
