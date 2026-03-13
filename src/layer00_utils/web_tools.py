import requests
import xml.etree.ElementTree as ET
import os
from tavily import TavilyClient
from src.layer00_utils.logger import system_logger

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

def _web_search(query: str, limit: int = 5) -> str:
    """Ищет информацию в интернете через Tavily API (специально для AI)"""
    if not TAVILY_API_KEY:
         return "Ошибка: Ключ TAVILY_API_KEY не найден в файле .env. Поиск невозможен."

    try:
        # Создаем клиента внутри функции, чтобы не крашить импорты, если ключа нет
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        
        # Делаем запрос. search_depth="advanced" ищет более глубоко и качественно
        response = tavily.search(
            query=query, 
            search_depth="advanced", 
            max_results=limit,
            include_answer=True # Tavily сам попытается сгенерировать короткий ответ
        )
        
        if not response.get('results'):
            return f"По запросу '{query}' ничего не найдено."
        
        formatted_results = []
        
        # Если Tavily смог сгенерировать прямой ответ на вопрос, добавляем его в начало
        if response.get('answer'):
            formatted_results.append(f"Краткая сводка от поисковика: {response['answer']}\n")
            
        # Добавляем сами ссылки и их содержимое
        for i, res in enumerate(response['results'], 1):
            title = res.get('title', 'Без названия')
            href = res.get('url', '')
            content = res.get('content', '')
            formatted_results.append(f"{i}. {title}\nURL: {href}\nФакты: {content}\n")
        
        system_logger.debug(f"[Web Search] Выполнен поиск (Tavily) по запросу: '{query}'")
        return f"Результаты веб-поиска по запросу '{query}':\n\n" + "\n".join(formatted_results)
        
    except Exception as e:
        system_logger.error(f"Ошибка веб-поиска (Tavily): {e}")
        return f"Ошибка при выполнении веб-поиска: {e}"

def _read_webpage(url: str) -> str:
    """Читает содержимое веб-страницы, очищая от мусора через Jina Reader API"""
    try:
        # Jina Reader API автоматически парсит страницу и возвращает чистый Markdown
        jina_url = f"https://r.jina.ai/{url}"
        response = requests.get(jina_url, timeout=25)
        
        if response.status_code != 200:
            return f"Ошибка при чтении страницы: сервер вернул код {response.status_code}."
            
        content = response.text
        
        # Защита от переполнения контекста LLM (обрезаем до ~15000 символов)
        MAX_CHARS = 15000
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS] + "\n\n... [ВНИМАНИЕ: ОСТАЛЬНАЯ ЧАСТЬ СТРАНИЦЫ ОБРЕЗАНА ИЗ-ЗА ЛИМИТОВ]"
            
        system_logger.debug(f"[Web Reader] Прочитана страница: {url}")
        return f"Содержимое страницы {url}:\n\n{content}"
    except Exception as e:
        system_logger.error(f"Ошибка чтения веб-страницы: {e}")
        return f"Ошибка при попытке прочитать страницу: {e}"
    

def _get_habr_articles(limit: int = 5) -> str:
    """Получает свежие статьи с главной страницы Хабра через RSS"""
    try:
        url = "https://habr.com/ru/rss/articles/?fl=ru"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return f"Ошибка доступа к habr.com: сервер вернул код {response.status_code}."
            
        root = ET.fromstring(response.content)
        channel = root.find("channel")
        
        formatted_news = []
        count = 0
        
        for item in channel.findall("item"):
            if count >= limit:
                break
                
            title = item.find("title").text
            link = item.find("link").text
            pub_date = item.find("pubDate").text
            
            # Очищаем дату от часового пояса (опционально, для красоты)
            pub_date_clean = pub_date.split(" +")[0] if " +" in pub_date else pub_date
            
            formatted_news.append(f"[{pub_date_clean}] {title}\nURL: {link}")
            count += 1
            
        system_logger.debug(f"[Web Reader] Получено {count} свежих статей с Хабра.")
        
        if not formatted_news:
            return "Новостей на Хабре не найдено."
            
        return "Недавние статьи с Хабра:\n\n" + "\n\n".join(formatted_news)
        
    except Exception as e:
        system_logger.error(f"Ошибка получения новостей Хабра: {e}")
        return f"Ошибка при попытке прочитать Хабр: {e}"
    
def _get_habr_news(limit: int = 5) -> str:
    """Получает недавние короткие новости с Хабра через RSS"""
    import xml.etree.ElementTree as ET
    try:
        url = "https://habr.com/ru/rss/news/?fl=ru"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return f"Ошибка доступа к новостям Хабра: сервер вернул код {response.status_code}."
            
        root = ET.fromstring(response.content)
        channel = root.find("channel")
        
        formatted_news = []
        count = 0
        
        for item in channel.findall("item"):
            if count >= limit:
                break
                
            title = item.find("title").text
            link = item.find("link").text
            pub_date = item.find("pubDate").text
            
            # Очищаем дату от часового пояса
            pub_date_clean = pub_date.split(" +")[0] if " +" in pub_date else pub_date
            
            formatted_news.append(f"[{pub_date_clean}] {title}\nURL: {link}")
            count += 1
            
        system_logger.debug(f"[Web Reader] Получено {count} свежих новостей с Хабра.")
        
        if not formatted_news:
            return "Новостей на Хабре не найдено."
            
        return "Недавние новости с Хабра:\n\n" + "\n\n".join(formatted_news)
        
    except Exception as e:
        system_logger.error(f"Ошибка получения новостей Хабра: {e}")
        return f"Ошибка при попытке прочитать новости Хабра: {e}"