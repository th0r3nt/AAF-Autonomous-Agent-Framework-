web_search_scheme = {
    "name": "web_search",
    "description": "Ищет информацию в интернете (Google/DuckDuckGo). Возвращает список релевантных ссылок с их кратким описанием.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Поисковый запрос (например: 'новости ИИ 2026', 'документация Python asyncio')"},
            "limit": {"type": "integer", "description": "Количество результатов (от 1 до 30, по умолчанию 10)"}
        },
        "required": ["query"]
    }
}

read_webpage_scheme = {
    "name": "read_webpage",
    "description": "Выкачивает текст по конкретному URL, очищает его от мусора (рекламы, меню) и возвращает чистый текст статьи.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Прямая ссылка на страницу."}
        },
        "required": ["url"]
    }
}

get_habr_articles_scheme = {
    "name": "get_habr_articles",
    "description": "Получает список свежих статей с главной страницы Хабра (IT-портал).",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Количество статей (от 1 до 15, по умолчанию 5)"}
        }
    }
}

get_habr_news_scheme = {
    "name": "get_habr_news",
    "description": "Получает список свежих коротких новостей (инфоповодов) с IT-портала Хабр.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Количество новостей (от 1 до 15, по умолчанию 5)"}
        }
    }
}

deep_research_scheme = {
    "name": "deep_research",
    "description": "Композитный навык для глубокого анализа темы. Сам делает поисковые запросы, выкачивает содержимое статей и возвращает единый текст.",
    "parameters": {
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список поисковых запросов (от 1 до 3). Например: ['LLM AI agents 2026', 'OpenClaw review']"
            },
            "max_urls": {
                "type": "integer",
                "description": "Сколько максимум страниц прочитать (по умолчанию 10)."
            }
        },
        "required": ["queries"]
    }
}

WEB_SCHEMAS = [
    web_search_scheme, read_webpage_scheme, get_habr_articles_scheme, 
    get_habr_news_scheme, deep_research_scheme
]