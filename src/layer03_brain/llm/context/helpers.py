import textwrap
import re
import asyncio
import ast
from pathlib import Path
from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer01_datastate.vector_db.vector_db_management import get_all_entries_in_vector_db
from src.layer01_datastate.graph_db.graph_db_management import get_all_node_names_async
from src.layer01_datastate.event_bus.events import EventConfig

# Суперузлы, которые мы игнорируем при Graph-RAG, чтобы не взорвать контекст ассоциациями
SUPERNODES = {
    config.identity.agent_name, 
    config.identity.admin_name
}

async def _get_macro_architecture_map() -> str:
    """Собирает макро-карту файлов проекта (корневые .md и папки слоев)"""
    try:
        current_dir = Path(__file__).resolve()
        src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
        
        if not src_dir.exists() or src_dir.name != "src":
            return "[Архитектурная карта недоступна]"

        lines = [
            "Системная архитектура (Макро-уровень):", 
            "Твое ядро - это проект на Python. Система запущена через main.py.",
        ]
        
        # Ищем только папки, начинающиеся с 'layer'
        layers = sorted([d for d in src_dir.iterdir() if d.is_dir() and d.name.startswith("layer")])
        
        for layer in layers:
            docstring = "Описание отсутствует"
            init_file = layer / "__init__.py"
            
            if init_file.exists():
                try:
                    with open(init_file, 'r', encoding='utf-8') as f:
                        module = ast.parse(f.read())
                        doc = ast.get_docstring(module)
                        if doc:
                            docstring = doc.split('\n')[0].strip()
                except Exception:
                    pass
                    
            lines.append(f"- src/{layer.name}/ : {docstring}")
            
        lines.append("\nПометка: чтобы увидеть полную структуру всех .py и .md файлов, используй навык get_system_architecture_map().")
        
        return "\n".join(lines)
    except Exception as e:
        return f"[Ошибка генерации макро-карты: {e}]"

def _safe_get(result, default="Данные недоступны"):
    """Защищает от падения при return_exceptions=True в asyncio.gather"""
    if isinstance(result, Exception):
        system_logger.error(f"[ContextBuilder] Ошибка при сборе данных: {result}")
        return default
    return result

def _format_event(event: EventConfig, args: tuple, kwargs: dict) -> str:
    """Описывает событие, которое заставило агента проснуться, в удобном для LLM формате"""
    details =[]
    
    # Красиво парсим события Telegram
    if event.name in["AGENT_NEW_INCOMING_MESSAGE_TG"]:
        username = kwargs.get("username", "Unknown")
        text = kwargs.get("text", "")
        msg_id = kwargs.get("message_id", "Неизвестно")
        details.append(f"[От: @{username} в Telegram] (ID сообщения: {msg_id}): {text}")
        
    elif event.name in["AGENT_NEW_MENTION_TG"]:
        chat = kwargs.get("chat_title", "Unknown Chat")
        chat_id = kwargs.get("chat_id", "Неизвестно") 
        username = kwargs.get("username", "Unknown")
        text = kwargs.get("text", "")
        msg_id = kwargs.get("message_id", "Неизвестно")
        details.append(f"[Telegram-упоминание в группе '{chat}' (ID чата: {chat_id}) от @{username}] (ID сообщения: {msg_id}): {text}")
        
    elif event.name == "TEXT_QUERY":
        query = args[0] if args else kwargs.get("command", "")
        details.append(f"[Терминал основного ПК]: {query}")
        
    elif event.name == "VOICE_QUERY":
        query = args[0] if args else kwargs.get("query", "")
        details.append(f"[Голосовой запрос с основного ПК]: {query}")

    elif event.name == "SWARM_INFO":
        source = kwargs.get("source", "Неизвестный субагент")
        result = kwargs.get("result", "Нет данных")
        details.append(f"[Отчет от субагента '{source}']: \n{result}")
        
    elif event.name == "SWARM_ERROR":
        source = kwargs.get("source", "Неизвестный субагент")
        error = kwargs.get("error", "Неизвестная ошибка")
        details.append(f"[субагент '{source}' умер с ошибкой]: {error}")
        
    elif event.name == "SWARM_ALERT":
        source = kwargs.get("source", "Неизвестный субагент")
        alert = kwargs.get("alert", "Тревога")
        details.append(f"[Уведомление от субагента '{source}']: {alert}")

    elif event.name == "SANDBOX_ATTENTION_REQUIRED":
        alert_msg = kwargs.get("alert_message", "Без текста")
        details.append(f"[Уведомление от локального скрипта]: {alert_msg}")

    elif event.name == "EXTERNAL_WEBHOOK_RECEIVED":
        payload = kwargs.get("payload", "Пустые данные")
        details.append(f"[Внешний Webhook (POST-запрос)]: \n{payload}\n")
        
    # Дефолтный фоллбэк для системных и остальных событий (например, погоды)
    else:
        if args: 
            details.append(f"Данные: {args}")
        if kwargs: 
            # Делаем словарь чуть более читаемым
            formatted_kwargs = ", ".join([f"{k}='{v}'" for k, v in kwargs.items()])
            details.append(f"Параметры: {formatted_kwargs}")
            
    details_str = " | ".join(details) if details else "Нет деталей"
    
    return textwrap.dedent(
        f"""
        Входящее событие: {event.name}
        Описание: {event.description}
        Детали: {details_str}
        Уровень важности: {event.level.name}
        """).strip()

def _extract_query_from_event(event: EventConfig, args: tuple, kwargs: dict) -> str:
    """Извлекает чистый текст для семантического поиска, отсекая системный мусор"""
    
    # Для текстовых сообщений из ТГ ищем только по самому тексту
    if event.name in ["AGENT_NEW_INCOMING_MESSAGE_TG", "USER_NEW_INCOMING_MESSAGE_TG", "AGENT_NEW_MENTION_TG", "USER_NEW_MENTION_TG"]:
        return kwargs.get("text", event.description)
        
    # Для запросов с ПК
    elif event.name in ["TEXT_QUERY", "VOICE_QUERY"]:
        return args[0] if args else kwargs.get("command", event.description)
        
    # Для системных событий оставляем описание
    else:
        return event.description

async def _get_recent_thoughts(limit: int = 5) -> str:
    """Извлекает последние хронологические мысли агента (Поток сознания)"""
    try:
        all_thoughts_raw = await get_all_entries_in_vector_db("agent_thoughts_vector_db")
        if not all_thoughts_raw or all_thoughts_raw.startswith("Ошибка"):
            return "Нет предыдущих мыслей."
            
        lines =[line for line in all_thoughts_raw.split('\n') if line.strip() and line.startswith("ID:")]
        
        if not lines:
            return "Нет предыдущих мыслей."
            
        recent_lines = lines[-limit:]
        return "\n".join(recent_lines)
        
    except Exception as e:
        system_logger.error(f"Ошибка при получении хронологических мыслей: {e}")
        return "Ошибка получения мыслей."
    
def _extract_graph_targets_from_event(event: EventConfig, kwargs: dict) -> list:
    """Вытаскивает имена пользователей и названия чатов из события для поиска в графе"""
    targets = []
    if event.name in ["AGENT_NEW_INCOMING_MESSAGE_TG", "AGENT_NEW_MENTION_TG", "AGENT_NEW_GROUP_MESSAGE"]:
        if "username" in kwargs and kwargs["username"] != "Unknown":
            targets.append(kwargs["username"])
        if "chat_title" in kwargs and kwargs["chat_title"] != "Unknown Chat":
            targets.append(kwargs["chat_title"])
    return targets

def _extract_anchors_for_proactivity(mental_state: str, tasks: str, unread: str) -> list:
    """Парсит тексты и вытаскивает имена сущностей для автоматического поиска в графе"""
    anchors = set()
    
    # 1. Достаем сущности из ACTIVE MENTAL MEMORY
    # Ищем паттерн [Имя] (Tier: ...
    mental_matches = re.findall(r'\[(.*?)\] \(Tier:', mental_state)
    anchors.update(mental_matches)
    
    # 2. Достаем задачи, которые in_progress или pending
    # Ищем строки типа: [Время] ID: 1 | Status: in_progress | Task: Название
    for line in tasks.split('\n'):
        if "Status: in_progress" in line or "Status: pending" in line:
            # Вытаскиваем само описание задачи, берем первые 30 символов как якорь
            parts = line.split("Task: ")
            if len(parts) > 1:
                task_desc = parts[1][:30].strip()
                anchors.add(task_desc)
                
    # 3. Достаем юзернеймы из непрочитанных чатов
    # Ищем паттерн (@username)
    unread_matches = re.findall(r'\(@(.*?)\)', unread)
    for u in unread_matches:
        if u != "без_юзернейма":
            anchors.add(f"@{u}")
            
    return list(anchors)

def _sync_extract_anchors(text_lower: str, all_nodes: list) -> list:
    """Синхронная тяжелая функция для работы в отдельном потоке"""
    found_anchors = set()
    for node in all_nodes:
        if node in SUPERNODES:
            continue
            
        aliases = [node.lower()]
        if "(" in node and ")" in node:
            clean_name = re.sub(r'\(.*?\)', '', node).strip().lower()
            if clean_name:
                aliases.append(clean_name)
                
        for alias in aliases:
            if len(alias) <= 3:
                # Для коротких слов используем регулярку
                if re.search(rf'\b{re.escape(alias)}\b', text_lower):
                    found_anchors.add(node)
                    break 
            else:
                # Для длинных быстрый поиск подстроки
                if alias in text_lower:
                    found_anchors.add(node)
                    break
    return list(found_anchors)

async def extract_graph_anchors_from_text(text: str) -> list:
    """Асинхронная обертка для извлечения узлов"""
    if not text:
        return []
        
    all_nodes = await get_all_node_names_async()
    if not all_nodes:
        return []
        
    # Выносим тяжелый цикл в фоновый поток
    return await asyncio.to_thread(_sync_extract_anchors, text.lower(), all_nodes)