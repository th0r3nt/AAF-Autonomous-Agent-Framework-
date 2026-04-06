from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.api.reddit.client import RedditClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class RedditPosts(BaseInstrument):
    """Сервис для работы с постами (чтение текста, создание, голосование, удаление)."""

    def __init__(self, client: RedditClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.api = client.transport

    def _ensure_post_fullname(self, post_id: str) -> str:
        """Вспомогательный метод. Убеждается, что ID поста имеет префикс 't3_'."""
        post_id = str(post_id).strip()
        if not post_id.startswith("t3_"):
            return f"t3_{post_id}"
        return post_id

    def _clean_sub_name(self, name: str) -> str:
        return name.lstrip("r/").lstrip("/r/").strip()

    @skill()
    async def get_post_details(self, post_id: str) -> ToolResult:
        """
        Получает полный текст поста, его рейтинг (score), соотношение лайков (upvote_ratio)
        и статус (закреплен/закрыт/удален).
        """
        fullname = self._ensure_post_fullname(post_id)

        try:
            # Используем эндпоинт /api/info для получения чистой инфы о посте (без дерева комментов)
            response = await self.api.request("GET", "api/info", params={"id": fullname})

            if response.status_code == 200:
                data = response.json()
                children = data.get("data", {}).get("children", [])

                if not children:
                    return ToolResult.fail(
                        msg=f"Пост с ID '{post_id}' не найден.", error="Not Found"
                    )

                post_data = children[0].get("data", {})

                title = post_data.get("title", "Без названия")
                author = post_data.get("author", "unknown")
                subreddit = post_data.get("subreddit", "unknown")

                score = post_data.get("score", 0)
                upvote_ratio = post_data.get("upvote_ratio", 0.0)
                comments_count = post_data.get("num_comments", 0)

                body = post_data.get("selftext", "").strip()
                if not body:
                    url = post_data.get("url", "")
                    body = f"[Это пост-ссылка или медиа. Указанный URL: {url}]"
                else:
                    if len(body) > 15000:
                        body = body[:14997] + "..."

                status_tags = []
                if post_data.get("stickied"):
                    status_tags.append("Закреплен")
                if post_data.get("locked"):
                    status_tags.append("Закрыт для комментов")
                if post_data.get("over_18"):
                    status_tags.append("NSFW")
                if post_data.get("is_robot_indexable") is False:
                    status_tags.append("Удален/Скрыт")

                tags_str = f" | Теги: {', '.join(status_tags)}" if status_tags else ""
                ratio_percent = int(upvote_ratio * 100)

                result = (
                    f"--- Пост ID: {post_id} (r/{subreddit}) ---\n"
                    f"Заголовок: {title}\n"
                    f"Автор: u/{author}{tags_str}\n"
                    f"Рейтинг: {score} ({ratio_percent}% апвоутов) | Комментариев: {comments_count}\n"
                    f"--- Текст поста ---\n"
                    f"{body}"
                )
                return ToolResult.ok(msg=result, data=post_data)

            return ToolResult.fail(
                msg=f"Ошибка при получении поста. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка сети при запросе поста {post_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))

    @skill()
    async def create_post(self, subreddit: str, title: str, text: str) -> ToolResult:
        """
        Создает новый текстовый пост (self-post) в указанном сабреддите.
        """
        subreddit = self._clean_sub_name(subreddit)

        try:
            payload = {
                "api_type": "json",
                "kind": "self",
                "sr": subreddit,
                "title": title,
                "text": text,
            }

            response = await self.api.request("POST", "api/submit", data=payload)

            if response.status_code == 200:
                data = response.json()
                errors = data.get("json", {}).get("errors", [])
                if errors:
                    error_msgs = ", ".join([f"{e[0]}: {e[1]}" for e in errors])
                    return ToolResult.fail(
                        msg=f"Ошибка API Reddit при создании поста: {error_msgs}",
                        error=str(errors),
                    )

                new_post_data = data.get("json", {}).get("data", {})
                new_id = new_post_data.get("id", "unknown")
                url = new_post_data.get("url", "unknown")

                system_logger.info(f"[Reddit] Создан пост в r/{subreddit} (ID: {new_id})")
                return ToolResult.ok(
                    msg=f"Пост '{title}' успешно опубликован в r/{subreddit}. ID: {new_id} | Ссылка: {url}",
                    data=new_post_data,
                )

            elif response.status_code == 403:
                return ToolResult.fail(
                    msg=f"Ошибка 403: Нет прав для публикации в r/{subreddit}.",
                    error="HTTP 403 Forbidden",
                )

            return ToolResult.fail(
                msg=f"Ошибка HTTP {response.status_code}: {response.text}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка создания поста в r/{subreddit}: {e}")
            return ToolResult.fail(msg=f"Критическая ошибка при публикации: {e}", error=str(e))

    @skill()
    async def vote_post(self, post_id: str, direction: int) -> ToolResult:
        """
        Голосует за пост.
        direction: 1 (Upvote), -1 (Downvote), 0 (Снять голос)
        """
        if direction not in [1, 0, -1]:
            return ToolResult.fail(
                msg="Ошибка: direction должен быть 1 (апвоут), -1 (даунвоут) или 0 (отмена)."
            )

        fullname = self._ensure_post_fullname(post_id)

        try:
            payload = {"id": fullname, "dir": direction}

            response = await self.api.request("POST", "api/vote", data=payload)

            if response.status_code == 200:
                action_str = (
                    "Upvote (👍)"
                    if direction == 1
                    else "Downvote (👎)" if direction == -1 else "Сброс голоса"
                )
                return ToolResult.ok(msg=f"Успешно: {action_str} для поста {post_id}.")

            return ToolResult.fail(
                msg=f"Не удалось проголосовать. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка голосования за пост {post_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при голосовании: {e}", error=str(e))

    @skill()
    async def delete_post(self, post_id: str) -> ToolResult:
        """
        Удаляет собственный пост агента.
        """
        fullname = self._ensure_post_fullname(post_id)

        try:
            payload = {"id": fullname}

            response = await self.api.request("POST", "api/del", data=payload)

            if response.status_code == 200:
                system_logger.info(f"[Reddit] Пост {post_id} удален агентом.")
                return ToolResult.ok(msg=f"Пост {post_id} был успешно удален.")

            return ToolResult.fail(
                msg=f"Ошибка удаления поста. HTTP {response.status_code}",
                error=response.text,
            )

        except Exception as e:
            system_logger.error(f"[Reddit] Ошибка удаления поста {post_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при удалении: {e}", error=str(e))
