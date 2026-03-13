import datetime
from sqlalchemy import desc, select, cast, String
from src.layer01_datastate.sql_db.sql_db import async_session_factory
from src.layer01_datastate.sql_db.sql_models import AgentAction, Dialogue
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog_decorator import watchdog_decorator
from src.layer00_utils.watchdog.watchdog import sql_db_module

@watchdog_decorator(sql_db_module)
async def deep_search_logs(target: str, query: str = None, action_type: str = None, source: str = None, days_ago: int = None, limit: int = 50) -> str:
    """Машина времени для поиска по логам действий и диалогов (с умным поиском по словам)"""
    try:
        async with async_session_factory() as session:
            now = datetime.datetime.now(datetime.timezone.utc)
            
            # Вспомогательная функция для умного поиска
            def apply_smart_search(stmt, column, search_query):
                if not search_query:
                    return stmt
                # Очищаем запрос от пунктуации и бьем на слова
                clean_query = search_query.replace("'", "").replace('"', "").replace("#", "").strip()
                words = [w for w in clean_query.split() if len(w) > 2] # Игнорируем предлоги
                
                # Ищем каждое слово независимо (AND)
                for word in words:
                    stmt = stmt.where(cast(column, String).ilike(f"%{word}%"))
                return stmt

            if target == "dialogue":
                stmt = select(Dialogue)
                stmt = apply_smart_search(stmt, Dialogue.message, query)
                
                if source: 
                    stmt = stmt.where(Dialogue.source == source)
                if days_ago: 
                    stmt = stmt.where(Dialogue.created_at >= now - datetime.timedelta(days=days_ago))
                
                stmt = stmt.order_by(desc(Dialogue.created_at)).limit(limit)
                result = await session.execute(stmt)
                records = result.scalars().all()
                
                if not records:
                    return f"Ничего не найдено в истории диалогов по запросу '{query}'."
                
                return "Найденная история диалогов:\n" + "\n".join(
                    [f"[{r.created_at.strftime('%Y-%m-%d %H:%M')}] [Source: {r.source}] {r.actor}: {r.message}" for r in reversed(records)]
                )
                
            elif target == "actions":
                stmt = select(AgentAction)
                if action_type: 
                    stmt = stmt.where(AgentAction.action_type == action_type)
                    
                stmt = apply_smart_search(stmt, AgentAction.details, query)
                
                if days_ago: 
                    stmt = stmt.where(AgentAction.created_at >= now - datetime.timedelta(days=days_ago))
                
                stmt = stmt.order_by(desc(AgentAction.created_at)).limit(limit)
                result = await session.execute(stmt)
                records = result.scalars().all()
                
                if not records:
                    return f"Ничего не найдено в логах действий по запросу '{query}'."
                
                return "Найденные логи действий:\n" + "\n".join(
                    [f"[{r.created_at.strftime('%Y-%m-%d %H:%M')}] | Type: {r.action_type} | Details: {str(r.details)[:300]}" for r in reversed(records)]
                )
            else:
                return "Ошибка: Неверный target. Нужно использовать 'dialogue' или 'actions'."
    except Exception as e:
        system_logger.error(f"Ошибка глубокого поиска логов: {e}")
        return f"Ошибка базы данных: {e}"