from src.l00_utils.managers.logger import system_logger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.api.reddit.client import RedditClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class RedditComments(BaseInstrument):
    """Сервис для чтения веток комментариев, ответов и модерации своих сообщений."""

    def __init__(self, client: 'RedditClient'):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.api = client.transport

    def _ensure_prefix(self, item_id: str, prefix: str) -> str:
        """
        Вспомогательный метод. Добавляет нужный префикс (t1_ или t3_), если его нет.
        """
        item_id = str(item_id).strip()
        if not item_id.startswith(prefix):
            return f"{prefix}{item_id}"
        return item_id

    def _build_comment_tree(self, children: list, depth: int = 0, max_depth: int = 3) -> list:
        """
        Рекурсивно строит дерево комментариев с отступами.
        Обрезает ветки глубже max_depth и ограничивает длину сообщений.
        """
        tree_strings = []

        for item in children:
            kind = item.get("kind")
            data = item.get("data", {})

            if kind == "more":
                count = data.get("count", 0)
                indent = "  " * depth
                if count > 0:
                    tree_strings.append(f"{indent}└─ [Скрыто {count} ответов...]")
                continue

            if kind == "t1":
                c_id = data.get("id")
                author = data.get("author", "[deleted]")
                score = data.get("score", 0)
                body = data.get("body", "").replace(chr(10), " ")

                if len(body) > 350:
                    body = body[:347] + "..."

                is_submitter = " [Автор поста]" if data.get("is_submitter") else ""
                indent = "  " * depth
                prefix = "└─ " if depth > 0 else "💬 "

                tree_strings.append(
                    f"{indent}{prefix}[ID: {c_id}] u/{author}{is_submitter} (Карма: {score}): {body}"
                )

                replies = data.get("replies")
                if replies and isinstance(replies, dict):
                    next_children = replies.get("data", {}).get("children", [])

                    if next_children:
                        if depth < max_depth:
                            tree_strings.extend(
                                self._build_comment_tree(next_children, depth + 1, max_depth)
                            )
                        else:
                            tree_strings.append(
                                f"{indent}    └─ [Ветка дискуссии уходит глубже...]"
                            )

        return tree_strings

    async def _submit_comment(self, parent_fullname: str, text: str) -> ToolResult:
        """
        Внутренний метод для отправки комментариев.
        """
        try:
            payload = {"api_type": "json", "text": text, "thing_id": parent_fullname}

            response = await self.api.request("POST", "api/comment", data=payload)

            if response.status_code == 200:
                data = response.json()
                errors = data.get("json", {}).get("errors", [])
                if errors:
                    error_msgs = ", ".join([f"{e[0]}: {e[1]}" for e in errors])
                    return ToolResult.fail(
                        msg=f"Ошибка API Reddit: {error_msgs}", error=str(errors)
                    )

                new_comment_data = (
                    data.get("json", {}).get("data", {}).get("things", [{}])[0].get("data", {})
                )
                new_id = new_comment_data.get("id", "unknown")

                system_logger.info(f"[Reddit] Успешный ответ на {parent_fullname}. ID: {new_id}")
                return ToolResult.ok(
                    msg=f"Комментарий успешно опубликован. Ваш ID: {new_id}",
                    data=new_comment_data,
                )

            elif response.status_code == 403:
                return ToolResult.fail(
                    msg="Ошибка 403: нет прав комментировать.",
                    error="HTTP 403 Forbidden",
                )

            return ToolResult.fail(
                msg=f"Ошибка публикации комментария. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка создания коммента к {parent_fullname}: {e}")
            return ToolResult.fail(msg=f"Ошибка публикации: {e}", error=str(e))

    @skill()
    async def get_post_comments(
        self, post_id: str, max_depth: int = 3, limit: int = 20
    ) -> ToolResult:
        """
        Получает ветку комментариев к посту.
        max_depth ограничивает "лесенку" ответов. limit ограничивает количество корневых комментов.
        """
        clean_id = post_id.lstrip("t3_").strip()

        try:
            response = await self.api.request(
                "GET",
                f"comments/{clean_id}",
                params={"depth": max_depth + 1, "limit": limit, "sort": "confidence"},
            )

            if response.status_code == 200:
                data_list = response.json()

                if len(data_list) < 2:
                    return ToolResult.ok(msg=f"К посту {post_id} пока нет комментариев.", data=[])

                comments_data = data_list[1].get("data", {}).get("children", [])

                if not comments_data:
                    return ToolResult.ok(msg=f"К посту {post_id} пока нет комментариев.", data=[])

                tree_lines = self._build_comment_tree(comments_data, depth=0, max_depth=max_depth)
                formatted_tree = "\n".join(tree_lines)

                return ToolResult.ok(
                    msg=f"--- Комментарии к посту {post_id} ---\n{formatted_tree}",
                    data=data_list,
                )

            elif response.status_code == 404:
                return ToolResult.fail(msg=f"Пост {post_id} не найден.", error="HTTP 404 Not Found")

            return ToolResult.fail(
                msg=f"Ошибка получения комментариев. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка сети при парсинге комментариев {post_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при парсинге: {e}", error=str(e))

    @skill()
    async def comment_on_post(self, post_id: str, text: str) -> ToolResult:
        """
        Оставляет корневой комментарий прямо под постом.
        """
        fullname = self._ensure_prefix(post_id, "t3_")
        return await self._submit_comment(fullname, text)

    @skill()
    async def reply_to_comment(self, comment_id: str, text: str) -> ToolResult:
        """
        Отвечает на чужой комментарий в ветке.
        """
        fullname = self._ensure_prefix(comment_id, "t1_")
        return await self._submit_comment(fullname, text)

    @skill()
    async def delete_comment(self, comment_id: str) -> ToolResult:
        """
        Удаляет собственный комментарий агента.
        """
        fullname = self._ensure_prefix(comment_id, "t1_")

        try:
            payload = {"id": fullname}
            response = await self.api.request("POST", "api/del", data=payload)

            if response.status_code == 200:
                system_logger.info(f"[Reddit] Комментарий {comment_id} удален агентом.")
                return ToolResult.ok(msg=f"Комментарий {comment_id} успешно удален.")

            return ToolResult.fail(
                msg=f"Ошибка удаления комментария. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка удаления коммента {comment_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при удалении: {e}", error=str(e))

    @skill()
    async def vote_comment(self, comment_id: str, direction: int) -> ToolResult:
        """
        Голосует за комментарий: 1 (Upvote), -1 (Downvote), 0 (Снять голос).
        """
        fullname = self._ensure_prefix(comment_id, "t1_")

        if direction not in [1, 0, -1]:
            return ToolResult.fail(msg="Ошибка: direction должен быть 1, -1 или 0.")

        try:
            payload = {"id": fullname, "dir": direction}
            response = await self.api.request("POST", "api/vote", data=payload)

            if response.status_code == 200:
                action_str = (
                    "Upvote (👍)"
                    if direction == 1
                    else "Downvote (👎)" if direction == -1 else "Сброс голоса"
                )
                return ToolResult.ok(msg=f"Успешно: {action_str} для комментария {comment_id}.")

            return ToolResult.fail(
                msg=f"Не удалось проголосовать. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка голосования за коммент {comment_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при голосовании: {e}", error=str(e))
