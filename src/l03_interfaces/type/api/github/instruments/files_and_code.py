import base64
import httpx
from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.api.github.client import GithubClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class GithubFilesAndCode(BaseInstrument):
    """Сервис для работы с исходным кодом: чтение структуры, файлов и прямые коммиты."""

    def __init__(self, agent_client: GithubClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.http = agent_client.client

    def _clean_repo_name(self, repo_name: str) -> str:
        repo_name = repo_name.strip()
        if "github.com/" in repo_name:
            repo_name = repo_name.split("github.com/")[-1]
        return repo_name.strip("/")

    @skill()
    async def get_repository_tree(
        self, repo_name: str, branch: str = "main", recursive: bool = True
    ) -> ToolResult:
        """
        Возвращает дерево переданного репозитория.
        """
        repo_name = self._clean_repo_name(repo_name)
        rec_param = "1" if recursive else "0"

        try:
            response = await self.http.get(
                f"/repos/{repo_name}/git/trees/{branch}",
                params={"recursive": rec_param},
            )

            if response.status_code == 200:
                data = response.json()
                tree = data.get("tree", [])

                if not tree:
                    return ToolResult.ok(
                        msg=f"Ветка '{branch}' пуста или не существует в {repo_name}.",
                        data=[],
                    )

                ignore_list = [
                    ".git/",
                    "node_modules/",
                    "__pycache__/",
                    "venv/",
                    ".idea/",
                    "dist/",
                    "build/",
                ]
                paths = []
                for item in tree:
                    path = item.get("path", "")
                    if any(ignored in path for ignored in ignore_list):
                        continue
                    item_type = "📁" if item.get("type") == "tree" else "📄"
                    paths.append(f"{item_type} {path}")

                truncated_warning = (
                    "\n\n[ВНИМАНИЕ] Дерево слишком большое и было обрезано GitHub API."
                    if data.get("truncated")
                    else ""
                )

                if len(paths) > 500:
                    paths = paths[:500]
                    truncated_warning = (
                        "\n\n[ВНИМАНИЕ] Показаны только первые 500 файлов для экономии памяти."
                    )

                msg = (
                    f"Структура репозитория {repo_name} (ветка: {branch}):\n"
                    + "\n".join(paths)
                    + truncated_warning
                )
                return ToolResult.ok(msg=msg, data=tree)

            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"Репозиторий '{repo_name}' или ветка '{branch}' не найдены.",
                    error="HTTP 404",
                )

            return ToolResult.fail(
                msg=f"Ошибка получения структуры дерева. HTTP Status: {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка сети при запросе дерева {repo_name}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при запросе структуры: {e}", error=str(e))

    @skill()
    async def read_file_content(
        self, repo_name: str, file_path: str, branch: str = "main"
    ) -> ToolResult:
        """
        Читает переданный файл в переданном репозитории и ветке.
        """
        repo_name = self._clean_repo_name(repo_name)
        file_path = file_path.lstrip("/")

        try:
            response = await self.http.get(
                f"/repos/{repo_name}/contents/{file_path}", params={"ref": branch}
            )

            if response.status_code == 200:
                data = response.json()

                if isinstance(data, list):
                    return ToolResult.fail(
                        msg=f"Ошибка: Указанный путь '{file_path}' является директорией, а не файлом.",
                        data=data,
                    )

                content_b64 = data.get("content", "")
                if not content_b64:
                    return ToolResult.ok(
                        msg=f"Файл '{file_path}' пуст или имеет неподдерживаемый формат.",
                        data=data,
                    )

                try:
                    content_bytes = base64.b64decode(content_b64)
                    text_content = content_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    return ToolResult.fail(
                        msg=f"Ошибка: Файл '{file_path}' является бинарным и не может быть прочитан как текст."
                    )

                max_chars = 15000
                if len(text_content) > max_chars:
                    text_content = (
                        text_content[:max_chars]
                        + f"\n\n...[ФАЙЛ ОБРЕЗАН: ПРЕВЫШЕН ЛИМИТ В {max_chars} СИМВОЛОВ] ..."
                    )

                msg = f"--- Файл: {file_path} (ветка: {branch}) ---\n{text_content}"
                return ToolResult.ok(
                    msg=msg,
                    data={
                        "path": file_path,
                        "sha": data.get("sha"),
                        "content": text_content,
                    },
                )

            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"Файл '{file_path}' не найден в ветке '{branch}'.",
                    error="HTTP 404",
                )

            return ToolResult.fail(
                msg=f"Ошибка чтения файла. HTTP {response.status_code}: {response.text}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка сети при чтении файла {file_path}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при чтении файла: {e}", error=str(e))

    @skill()
    async def commit_file(
        self,
        repo_name: str,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str = "main",
    ) -> ToolResult:
        """
        Коммитит файл.
        """
        repo_name = self._clean_repo_name(repo_name)
        file_path = file_path.lstrip("/")

        try:
            sha = None
            check_response = await self.http.get(
                f"/repos/{repo_name}/contents/{file_path}", params={"ref": branch}
            )

            if check_response.status_code == 200:
                data = check_response.json()
                if isinstance(data, list):
                    return ToolResult.fail(
                        msg=f"Ошибка: '{file_path}' является директорией. Невозможно записать в неё как в файл."
                    )
                sha = data.get("sha")
            elif check_response.status_code not in [404, 403]:
                return ToolResult.fail(
                    msg=f"Не удалось проверить статус файла. HTTP {check_response.status_code}",
                    error=check_response.text,
                )

            encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
            payload = {
                "message": commit_message,
                "content": encoded_content,
                "branch": branch,
            }
            if sha:
                payload["sha"] = sha

            response = await self.http.put(f"/repos/{repo_name}/contents/{file_path}", json=payload)

            if response.status_code in [200, 201]:
                resp_data = response.json()
                commit_data = resp_data.get("commit", {})
                commit_url = commit_data.get("html_url", "")
                commit_sha = commit_data.get("sha", "")[:7]

                action = "обновлен" if sha else "создан"
                system_logger.info(
                    f"[GitHub] Файл {file_path} {action} в {repo_name} (Commit: {commit_sha})"
                )

                msg = f"Файл '{file_path}' успешно {action}. Коммит {commit_sha}.\nСсылка на коммит: {commit_url}"
                return ToolResult.ok(msg=msg, data=resp_data)

            elif response.status_code == 409:
                return ToolResult.fail(
                    msg="Ошибка 409 (Конфликт): Несовпадение SHA или кто-то другой изменил файл.",
                    error="HTTP 409 Conflict",
                )
            elif response.status_code == 403:
                return ToolResult.fail(
                    msg=f"Ошибка 403: У агента нет прав на запись (push) в репозиторий '{repo_name}'.",
                    error="HTTP 403 Forbidden",
                )

            return ToolResult.fail(
                msg=f"Ошибка при коммите. HTTP {response.status_code}: {response.text}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[GitHub] Ошибка сети при коммите файла {file_path}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при выполнении коммита: {e}", error=str(e))
