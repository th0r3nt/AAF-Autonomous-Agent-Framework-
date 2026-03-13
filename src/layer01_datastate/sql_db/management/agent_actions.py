from sqlalchemy import desc, select
from src.layer01_datastate.sql_db.sql_db import async_session_factory
from src.layer01_datastate.sql_db.sql_models import AgentAction
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog_decorator import watchdog_decorator
from src.layer00_utils.watchdog.watchdog import sql_db_module


# ----------------------------------------------------------------------------------------------
# ТАБЛИЦА: AgentAction (логгирование вызова функций агента)

@watchdog_decorator(sql_db_module)
async def create_agent_action(action_type: str, details: dict) -> str:
    """Создание новой записи действия агента"""
    try:
        async with async_session_factory() as session:
            new_action = AgentAction(
                action_type=action_type, 
                details=details
            )
            session.add(new_action)
            await session.commit()
            await session.refresh(new_action)
            
            msg = f"Действие создано — ID: {new_action.id} | Тип: {new_action.action_type} | Детали: {new_action.details}"
            system_logger.debug(msg)
            return msg
    except Exception as e:
        system_logger.error(f"Ошибка при создании действия агента: {e}")
        return f"Ошибка при создании действия: {e}"

@watchdog_decorator(sql_db_module)
async def get_recent_agent_actions(limit: int = 15) -> str:
    """Получить последние N записей действий агента в виде строки (с обрезкой длинных аргументов)"""
    try:
        async with async_session_factory() as session:
            query = select(AgentAction).order_by(desc(AgentAction.created_at)).limit(limit)
            result = await session.execute(query)
            actions = result.scalars().all()

            if not actions:
                return "Список действий агента пуст."

            formatted_actions = []
            for a in reversed(actions):
                # Игнорируем ненужные действия
                if a.action_type in ["mark_chat_as_read_as_agent"]:
                    continue
                time_str = a.created_at.strftime('%Y-%m-%d %H:%M:%S') 
                
                # Обрезаем детали, чтобы не засорять контекст LLM
                limit = 100
                details_str = str(a.details)
                if len(details_str) > limit:
                    details_str = details_str[:limit] + "... [Обрезано]"
                    
                formatted_actions.append(f"[{time_str}] | Type: {a.action_type} | Details: {details_str}")
            
            return "\n".join(formatted_actions)
        
    except Exception as e:
        system_logger.error(f"Ошибка при получении действий: {e}")
        return f"Ошибка: {e}"
    
@watchdog_decorator(sql_db_module)
async def get_raw_recent_actions(limit: int = 40):
    """Служебная: отдает сырые объекты действий"""
    async with async_session_factory() as session:
        query = select(AgentAction).order_by(desc(AgentAction.created_at)).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()
    
@watchdog_decorator(sql_db_module)
async def get_raw_recent_thoughts(limit: int = 5):
    """Служебная: отдает сырые объекты последних мыслей (AgentAction -> memorize_information)"""
    async with async_session_factory() as session:
        # Берем с запасом (limit * 3), так как мы будем фильтровать их в Python по топику
        stmt = select(AgentAction).where(AgentAction.action_type == 'memorize_information').order_by(desc(AgentAction.created_at)).limit(limit * 3)
        result = await session.execute(stmt)
        actions = result.scalars().all()
        
        # Оставляем только те, где topic == 'introspection'
        thoughts = [a for a in actions if a.details and a.details.get('topic') == 'introspection']
        
        return thoughts[:limit]
