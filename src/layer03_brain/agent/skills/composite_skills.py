import asyncio 
import os
from src.layer00_utils.logger import system_logger
from src.layer00_utils.web_tools import (
    _read_webpage
)

from tavily import TavilyClient
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


async def deep_research(queries: list, max_urls: int = 10) -> str:
    """Обертка: композитный навык глубокого ресерча с параллельным парсингом"""
    if not TAVILY_API_KEY:
        return "Ошибка: Ключ TAVILY_API_KEY не найден."
    
    system_logger.info(f"[Web Search] Запуск Deep Research по запросам: {queries}")
    
    # 1. Собираем ссылки (в отдельном потоке, так как TavilyClient синхронный)
    def _get_urls():
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        urls = []
        for q in queries:
            try:
                # search_depth="basic" работает быстрее и дает достаточно инфы
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
    
    # 2. Читаем все страницы параллельно (экономит кучу времени)
    read_tasks = [asyncio.to_thread(_read_webpage, url) for url in target_urls]
    pages_content = await asyncio.gather(*read_tasks, return_exceptions=True)
    
    # 3. Склеиваем результат
    final_report = [f"РЕЗУЛЬТАТЫ DEEP RESEARCH (По запросам: {', '.join(queries)}):\n"]
    for url, content in zip(target_urls, pages_content):
        if isinstance(content, Exception):
            content = f"Ошибка при чтении: {content}"
            
        final_report.append(f"\nИСТОЧНИК: {url} \n{content}\n")
        
    system_logger.info("[Web Search] deep_research успешно завершен.")
    return "\n".join(final_report)