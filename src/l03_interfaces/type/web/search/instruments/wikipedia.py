import httpx
from src.l00_utils.managers.logger import system_logger
from src.l00_utils._tools import clean_html_to_md
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.web.search.client import SearchClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class WikipediaSearch(BaseInstrument):
    """Сервис для точечного фактчекинга без засорения контекста."""

    def __init__(self, search_client: 'SearchClient'):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.api = search_client.client

    @skill()
    async def wiki_search(self, query: str, limit: int = 5, lang: str = "eng") -> ToolResult:
        """
        Ищет точное название статьи по ключевым словам.
        Необходимо для последующего извлечения фактов.
        """
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "utf8": 1,
            "format": "json",
            "srlimit": limit,
        }

        try:
            resp = await self.api.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                search_results = data.get("query", {}).get("search", [])

                if not search_results:
                    return ToolResult.fail(
                        msg=f"В Википедии ({lang}) по запросу '{query}' статьи не найдены."
                    )

                result = [f"Найденные статьи в Википедии по запросу '{query}':"]
                for item in search_results:
                    title = item.get("title")
                    snippet = clean_html_to_md(item.get("snippet", ""))
                    result.append(f"- {title} (Фрагмент: {snippet})")

                return ToolResult.ok(msg="\n".join(result), data=search_results)

            return ToolResult.fail(
                msg=f"Ошибка API Википедии. HTTP Status: {resp.status_code}",
                error=resp.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Wikipedia] Ошибка сети при поиске: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))

    async def wiki_read_summary(self, article_title: str, lang: str = "ru") -> ToolResult:
        """
        Читает только первый вводный абзац статьи (Intro). Самый экономный метод.
        """
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "prop": "extracts",
            "exintro": 1,  # Вернуть только вступление
            "explaintext": 1,  # Вернуть чистый текст, без HTML
            "titles": article_title,
            "format": "json",
        }

        try:
            resp = await self.api.get(url, params=params)
            if resp.status_code == 200:
                pages = resp.json().get("query", {}).get("pages", {})

                # API Википедии возвращает словарь { "page_id": { ... } }
                for page_id, page_data in pages.items():
                    if page_id == "-1":
                        return ToolResult.fail(
                            msg=f"Статья с названием '{article_title}' не найдена.",
                            error="404",
                        )

                    extract = page_data.get("extract", "").strip()
                    if not extract:
                        return ToolResult.fail(
                            msg=f"Статья '{article_title}' пуста (возможно, перенаправление или список)."
                        )

                    return ToolResult.ok(
                        msg=f"--- {article_title} (Википедия) ---\n{extract}",
                        data=page_data,
                    )

            return ToolResult.fail(
                msg=f"Ошибка API Википедии. HTTP Status: {resp.status_code}",
                error=resp.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Wikipedia] Ошибка сети при чтении intro: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))

    @skill()
    async def wiki_read_section(
        self, article_title: str, section_index: str = None, lang: str = "ru"
    ) -> ToolResult:
        """
        Двойной метод:
        1. Если section_index не указан - возвращает только оглавление.
        2. Если section_index передан - возвращает текст конкретного раздела.
        """
        url = f"https://{lang}.wikipedia.org/w/api.php"

        try:
            if section_index is None:
                # 1. ЗАПРОС ОГЛАВЛЕНИЯ
                params = {
                    "action": "parse",
                    "page": article_title,
                    "prop": "sections",
                    "format": "json",
                }
                resp = await self.api.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if "error" in data:
                        return ToolResult.fail(
                            msg=f"Ошибка Википедии: {data['error'].get('info')}",
                            error=str(data["error"]),
                        )

                    sections = data.get("parse", {}).get("sections", [])
                    if not sections:
                        return ToolResult.fail(
                            msg=f"В статье '{article_title}' нет разделов оглавления."
                        )

                    result = [f"Оглавление статьи '{article_title}':"]
                    for sec in sections:
                        result.append(f"Индекс: {sec['index']} | {sec['line']}")

                    result.append(
                        "\nДля чтения вызовите эту функцию повторно, передав 'section_index'."
                    )
                    return ToolResult.ok(msg="\n".join(result), data=sections)

            else:
                # 2. ЗАПРОС КОНКРЕТНОГО РАЗДЕЛА
                params = {
                    "action": "parse",
                    "page": article_title,
                    "prop": "text",
                    "section": section_index,
                    "format": "json",
                }
                resp = await self.api.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if "error" in data:
                        return ToolResult.fail(
                            msg=f"Ошибка Википедии: {data['error'].get('info')}",
                            error=str(data["error"]),
                        )

                    html_text = data.get("parse", {}).get("text", {}).get("*", "")

                    # Очищаем HTML в читаемый Markdown для агента
                    clean_text = clean_html_to_md(html_text)

                    # Жестко обрезаем огромные разделы для защиты контекста
                    if len(clean_text) > 12000:
                        clean_text = clean_text[:11997] + "..."

                    return ToolResult.ok(
                        msg=f"--- Раздел {section_index} статьи '{article_title}' ---\n{clean_text}",
                        data=data,
                    )

            return ToolResult.fail(
                msg=f"Ошибка API Википедии. HTTP Status: {resp.status_code}",
                error=resp.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Wikipedia] Ошибка сети при чтении раздела: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))
