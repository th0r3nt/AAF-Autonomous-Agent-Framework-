import os
import asyncio
from tavily import TavilyClient
from src.layer00_utils.logger import system_logger

from src.layer00_utils.web_tools import (
    _web_search, _read_webpage, _get_habr_articles, _get_habr_news
)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

def web_search(query: str, limit: int = 10) -> str:
    """Обертка: поиск в интернете"""
    return _web_search(query, limit)

def read_webpage(url: str) -> str:
    """Обертка: чтение страницы"""
    return _read_webpage(url)

def get_habr_articles(limit: int = 5) -> str:
    """Обертка: чтение последних n статей с Хабра"""
    return _get_habr_articles(limit)

def get_habr_news(limit: int = 5) -> str:
    """Обертка: чтение новостной ленты Хабра"""
    return _get_habr_news(limit)

async def deep_research(queries: list, max_urls: int = 10) -> str:
    if not TAVILY_API_KEY:
        return "Ошибка: Ключ TAVILY_API_KEY не найден."
    
    system_logger.info(f"[Web Search] Запуск Deep Research по запросам: {queries}")
    
    def _get_urls():
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        urls = []
        for q in queries:
            try:
                res = tavily.search(query=q, search_depth="basic", max_results=3)
                for r in res.get('results', []):
                    if r.get('url') not in urls:
                        urls.append(r['url'])
            except Exception as e:
                system_logger.error(f"[Web Search] Tavily ошибка: {e}")
        return urls[:max_urls]
        
    target_urls = await asyncio.to_thread(_get_urls)
    
    if not target_urls:
        return "Не удалось найти информацию по данным запросам."
        
    system_logger.info(f"[Web Search] Deep Research читает {len(target_urls)} страниц параллельно...")
    
    read_tasks = [asyncio.to_thread(_read_webpage, url) for url in target_urls]
    pages_content = await asyncio.gather(*read_tasks, return_exceptions=True)
    
    final_report = [f"РЕЗУЛЬТАТЫ DEEP RESEARCH (По запросам: {', '.join(queries)}):\n"]
    for url, content in zip(target_urls, pages_content):
        if isinstance(content, Exception):
            content = f"Ошибка при чтении: {content}"
        final_report.append(f"\nИСТОЧНИК: {url} \n{content}\n")
        
    system_logger.info("[Web Search] deep_research успешно завершен.")
    return "\n".join(final_report)

WEB_REGISTRY = {
    "web_search": web_search,
    "read_webpage": read_webpage,
    "get_habr_articles": get_habr_articles,
    "get_habr_news": get_habr_news,
    "deep_research": deep_research,
}