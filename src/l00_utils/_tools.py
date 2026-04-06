import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md


def clean_html_to_md(raw_html: str) -> str:
    """
    Универсальный онвертер HTML в Markdown-подобный текст для LLM.
    Использует BeautifulSoup4 для вырезания мусора и markdownify для парсинга,
    чтобы не сломаться на кривой верстке или вложенных тегах.
    """
    if not raw_html or not isinstance(raw_html, str):
        return ""

    # Загружаем HTML в надежный парсер
    # (html.parser встроен в Python, не требует lxml)
    soup = BeautifulSoup(raw_html, "html.parser")

    # Безжалостно вырезаем скрипты, стили и метатеги ВМЕСТЕ с их содержимым.
    # Регулярками это делать опасно, а bs4 справляется идеально.
    for element in soup(["script", "style", "meta", "noscript", "iframe"]):
        element.decompose()

    # Конвертируем очищенное DOM-дерево в Markdown
    # heading_style="ATX" делает заголовки через решетки (# Заголовок), а не через подчеркивания (===)
    text = md(
        str(soup),
        heading_style="ATX",
        strip=["img", "picture", "figure"],  # Изображения LLM читать текстом не нужно
    )

    # 4. Финальная косметика (чистим артефакты множественных переносов)
    # markdownify может оставлять лишние пустые строки после таблиц и дивов
    text = re.sub(r"^[ \t]+", "", text, flags=re.MULTILINE)  # Убираем пробелы в начале строк
    text = re.sub(r"\n{3,}", "\n\n", text)  # Схлопываем 3+ пустые строки в 2

    return text.strip()
