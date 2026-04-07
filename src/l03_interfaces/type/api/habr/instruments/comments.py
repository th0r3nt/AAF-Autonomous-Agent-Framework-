import httpx
from src.l00_utils.managers.logger import system_logger
from src.l00_utils._tools import clean_html_to_md
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.l03_interfaces.type.api.habr.client import HabrClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class HabrComments(BaseInstrument):
    """
    Сервис для чтения и анализа комментариев к статьям на Хабре.
    """

    def __init__(self, agent_client: "HabrClient"):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.http = agent_client.client

    def _build_comment_tree(
        self,
        comments_data: dict,
        parent_id: int = 0,
        depth: int = 0,
        max_depth: int = 3,
    ) -> list[str]:
        """
        Рекурсивно строит дерево комментариев в виде отступов.
        Ограничиваем глубину (max_depth), чтобы LLM не сошла с ума от лесенок в 20 уровней.
        """
        tree_strings = []
        # Ищем все комментарии, у которых parentId совпадает с текущим (0 = корневые)
        children = [c for c in comments_data.values() if c.get("parentId") == parent_id]

        # Сортируем по времени создания
        children.sort(key=lambda x: x.get("timePublished", ""))

        for comment in children:
            c_id = comment.get("id")
            author = comment.get("author", {}).get("alias", "Unknown")
            score = comment.get("score", 0)
            raw_text = comment.get("message", "")
            clean_text = clean_html_to_md(raw_text)

            # Убираем слишком длинные цитаты внутри комментов
            if len(clean_text) > 800:
                clean_text = clean_text[:797] + "..."

            # Создаем визуальный отступ
            indent = "  " * depth
            prefix = "└─ " if depth > 0 else "💬 "

            tree_strings.append(
                f"{indent}{prefix}[ID: {c_id}] @{author} (Рейтинг: {score}): {clean_text}"
            )

            # Рекурсивно добавляем ответы на этот комментарий, если не превысили лимит глубины
            if depth < max_depth:
                tree_strings.extend(
                    self._build_comment_tree(
                        comments_data,
                        parent_id=c_id,
                        depth=depth + 1,
                        max_depth=max_depth,
                    )
                )
            elif any(c.get("parentId") == c_id for c in comments_data.values()):
                # Если есть ответы глубже, просто ставим пометку, чтобы сэкономить контекст
                tree_strings.append(f"{indent}    └─ [Есть скрытые ответы...]")

        return tree_strings

    @skill()
    async def get_article_comments(self, article_id: int | str, limit: int = 30) -> ToolResult:
        """
        Получает комментарии к конкретной статье и выстраивает их в дерево дискуссий.
        """
        try:
            # Эндпоинт для получения комментов (API v2)
            response = await self.http.get(
                f"/articles/{article_id}/comments/", params={"hl": "ru", "fl": "ru"}
            )

            if response.status_code == 200:
                data = response.json()
                comments_dict = data.get("comments", {})

                if not comments_dict:
                    return ToolResult.ok(
                        msg=f"[Habr] К статье {article_id} пока нет комментариев.",
                        data=[],
                    )

                # Унифицируем parentId для корней (на случай если Хабр вернет строку или None)
                for c in comments_dict.values():
                    if c.get("parentId") in ("0", None, ""):
                        c["parentId"] = 0

                # Строим дерево из ВСЕХ комментариев (без преждевременного срезания)
                tree_lines = self._build_comment_tree(
                    comments_dict, parent_id=0, depth=0, max_depth=3
                )

                # Fallback, если дерево почему-то совсем не собралось
                if not tree_lines:
                    for c_id, c in comments_dict.items():
                        author = c.get("author", {}).get("alias", "Unknown")
                        text = clean_html_to_md(c.get("message", ""))[:200]
                        tree_lines.append(f"[ID: {c_id}] @{author}: {text}")

                # Вот теперь безопасно ограничиваем по количеству выводимых строк (веток)
                warning = ""
                total_lines = len(tree_lines)
                if total_lines > limit:
                    warning = f"\n\n[ВНИМАНИЕ] Показаны не все комментарии (Лимит: {limit} из {total_lines})."
                    tree_lines = tree_lines[:limit]

                formatted_tree = "\n".join(tree_lines)

                # Жесткая защита по символам (на всякий случай)
                max_str_len = 8000
                if len(formatted_tree) > max_str_len:
                    formatted_tree = (
                        formatted_tree[:max_str_len]
                        + "\n...[ОБРЕЗАНО ИЗ-ЗА ПРЕВЫШЕНИЯ ЛИМИТА СИМВОЛОВ]..."
                    )

                return ToolResult.ok(
                    msg=f"--- Ветка комментариев (Статья ID: {article_id}) ---\n{formatted_tree}{warning}",
                    data=data,
                )

            elif response.status_code == 404:
                return ToolResult.fail(
                    msg=f"[Habr] Статья {article_id} не найдена или комментарии закрыты.",
                    error="HTTP 404",
                )

            elif response.status_code == 403:
                return ToolResult.fail(
                    msg="[Habr] Доступ к комментариям запрещен.", error="HTTP 403"
                )

            return ToolResult.fail(
                msg=f"Ошибка при получении комментариев. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(
                f"[Habr] Ошибка сети при запросе комментов к {article_id}: {e}"
            )
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))
