from typing import List
from sqlalchemy import desc, select, not_, or_
from src.layer01_datastate.sql_db.sql_db import async_session_factory
from src.layer01_datastate.sql_db.sql_models import Dialogue
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog_decorator import watchdog_decorator
from src.layer00_utils.watchdog.watchdog import sql_db_module


# ----------------------------------------------------------------------------------------------
# ТАБЛИЦА: Dialogue (история диалогов)

@watchdog_decorator(sql_db_module)
async def create_dialogue_entry(actor: str, message: str, source: str) -> str:
    """Создание новой записи диалога"""
    try:
        async with async_session_factory() as session:
            new_entry = Dialogue(
                actor=actor, 
                message=message, 
                source=source
            )
            session.add(new_entry)
            await session.commit()
            await session.refresh(new_entry)
            
            msg = f"Сообщение сохранено - ID: {new_entry.id} | Source: {new_entry.source} | {new_entry.actor}: {new_entry.message}"
            system_logger.debug(msg)
            return msg
    except Exception as e:
        system_logger.error(f"Ошибка при создании записи диалога: {e}")
        return f"Ошибка: {e}"

@watchdog_decorator(sql_db_module)
async def get_recent_dialogue(limit: int = 20, exclude_groups: bool = False, exclude_keywords: list = None) -> List[Dialogue]:
    """Вспомогательная функция: получить объекты последних записей диалога"""
    try:
        async with async_session_factory() as session:
            query = select(Dialogue)
            
            if exclude_groups:
                query = query.where(
                    or_(
                        not_(Dialogue.source.startswith("tg_agent_group_")),
                        Dialogue.actor == "V.E.G.A."
                    )
                )
                
            # Проходимся по списку и исключаем всё, что совпадает
            if exclude_keywords:
                for kw in exclude_keywords:
                    if kw: # Защита от пустых строк
                        query = query.where(not_(Dialogue.source.icontains(kw)))
                
            query = query.order_by(desc(Dialogue.created_at)).limit(limit)
            result = await session.execute(query)
            return result.scalars().all()
    except Exception as e:
        system_logger.error(f"Ошибка при получении диалогов: {e}")
        return []

@watchdog_decorator(sql_db_module)
async def get_clear_recent_dialogue(limit: int = 20, exclude_keywords: list = None) -> str:
    """Возвращает отформатированную строку с историей диалога (БЕЗ спама из групп и БЕЗ текущего чата)"""
    history = await get_recent_dialogue(limit, exclude_groups=True, exclude_keywords=exclude_keywords)
    if not history:
        return "(История диалогов пуста)"

    lines = []
    for entry in reversed(history): 
        time_str = entry.created_at.strftime('%Y-%m-%d %H:%M:%S')
        lines.append(f"[{time_str}] [Source: {entry.source}] {entry.actor}: {entry.message}")
        
    return "\n".join(lines)

@watchdog_decorator(sql_db_module)
async def get_dialogue_by_source(source: str, limit: int = 20) -> str:
    """Возвращает историю диалога для конкретного чата/источника"""
    try:
        async with async_session_factory() as session:
            query = select(Dialogue).where(Dialogue.source == source).order_by(desc(Dialogue.created_at)).limit(limit)
            result = await session.execute(query)
            history = result.scalars().all()

            if not history:
                return "История диалога пуста."

            lines =[]
            for entry in reversed(history): # Переворачиваем, чтобы старые были сверху
                lines.append(f"[{entry.created_at.strftime('%Y-%m-%d %H:%M')}] {entry.actor}: {entry.message}")
                
            return "\n".join(lines)
    except Exception as e:
        system_logger.error(f"Ошибка при получении диалога по source '{source}': {e}")
        return "Ошибка получения истории."
    
@watchdog_decorator(sql_db_module)
async def get_raw_recent_dialogue(limit: int = 40):
    """Служебная: отдает сырые объекты диалогов (без спама из групп)"""
    async with async_session_factory() as session:
        query = select(Dialogue).where(not_(Dialogue.source.startswith("tg_agent_group_"))).order_by(desc(Dialogue.created_at)).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()
