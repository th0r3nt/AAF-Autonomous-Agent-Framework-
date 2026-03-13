from sqlalchemy import desc, select, update, delete
from src.layer01_datastate.sql_db.sql_db import async_session_factory
from src.layer01_datastate.sql_db.sql_models import LongTermTask
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog_decorator import watchdog_decorator
from src.layer00_utils.watchdog.watchdog import sql_db_module



# ----------------------------------------------------------------------------------------------
# ТАБЛИЦА: LongTermTask (долсрочные задачи агента)

@watchdog_decorator(sql_db_module)
async def create_task(task_description: str, status: str = "pending", term: str = None) -> str:
    """Создание новой задачи"""
    try:
        async with async_session_factory() as session:
            new_task = LongTermTask(
                task_description=task_description,
                status=status,
                term=term
            )
            session.add(new_task)
            await session.commit()
            await session.refresh(new_task)
            
            term_info = f" | Term: {new_task.term}" if new_task.term else ""
            msg = f"Задача создана — ID: {new_task.id} | Status: {new_task.status}{term_info} | Task: {new_task.task_description}"
            system_logger.debug(msg)
            return msg
    except Exception as e:
        system_logger.error(f"Ошибка при создании задачи: {e}")
        return f"Ошибка: {e}"
    
@watchdog_decorator(sql_db_module)
async def update_task_status(task_id: int, new_status: str) -> str:
    """Обновление статуса задачи по ID"""
    try:
        async with async_session_factory() as session:
            stmt = update(LongTermTask).where(LongTermTask.id == task_id).values(status=new_status).returning(LongTermTask)
            result = await session.execute(stmt)
            updated_task = result.scalar_one_or_none()
            await session.commit()
            
            if updated_task:
                msg = f"Статус обновлен — ID: {updated_task.id} | New Status: [{updated_task.status}] | Task: {updated_task.task_description}"
                system_logger.debug(msg)
                return msg
            else:
                return f"Задача с ID {task_id} не найдена."
            
    except Exception as e:
        system_logger.error(f"Ошибка при обновлении задачи {task_id}: {e}")
        return f"Ошибка: {e}"

@watchdog_decorator(sql_db_module)
async def get_all_tasks() -> str:
    """Получить список всех задач"""
    try:
        async with async_session_factory() as session:
            query = select(LongTermTask).order_by(desc(LongTermTask.created_at))
            result = await session.execute(query)
            tasks = result.scalars().all()

            if not tasks:
                return "Список задач пуст."

            formatted_list = []
            for t in tasks:
                term_info = f" | Срок/Периодичность: {t.term}" if t.term else ""
                time_str = t.created_at.strftime('%Y-%m-%d %H:%M')
                
                task_str = f"[{time_str}] ID: {t.id} | Status: {t.status}{term_info} | Task: {t.task_description}"
                if t.context:
                    ctx_str = t.context
                    if len(ctx_str) > 100:
                        ctx_str = ctx_str[:100] + "... [Обрезано]"
                    task_str += f"\n   * Context: {ctx_str}"
                    
                formatted_list.append(task_str)
                
            return "\n".join(formatted_list)
    except Exception as e:
        system_logger.error(f"Ошибка при получении всех задач: {e}")
        return f"Ошибка: {e}"
        
@watchdog_decorator(sql_db_module)
async def get_tasks_by_status(status: str) -> str:
    """Получить задачи по конкретному статусу"""
    try:
        async with async_session_factory() as session:
            query = select(LongTermTask).where(LongTermTask.status == status).order_by(desc(LongTermTask.created_at))
            result = await session.execute(query)
            tasks = result.scalars().all()

            if not tasks:
                return f"Задач со статусом '{status}' не найдено."

            formatted_list = []
            for t in tasks:
                term_info = f" | Срок: {t.term}" if t.term else ""
                time_str = t.created_at.strftime('%Y-%m-%d %H:%M')
                formatted_list.append(f"[{time_str}] ID: {t.id} | Status: {t.status}{term_info} | Task: {t.task_description}")
                
            return "\n".join(formatted_list)
    except Exception as e:
        system_logger.error(f"Ошибка при поиске задач по статусу: {e}")
        return f"Ошибка: {e}"
    
@watchdog_decorator(sql_db_module)
async def delete_task(task_id: int) -> str:
    """Удалить задачу по ID"""
    try:
        async with async_session_factory() as session:
            stmt = delete(LongTermTask).where(LongTermTask.id == task_id)
            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount > 0:
                msg = f"Задача ID: {task_id} успешно удалена."
                system_logger.debug(msg)
                return msg
            else:
                return f"Задача ID: {task_id} не найдена для удаления."
    except Exception as e:
        system_logger.error(f"Ошибка при удалении задачи: {e}")
        return f"Ошибка: {e}"
    
@watchdog_decorator(sql_db_module)
async def update_task_context(task_id: int, new_context: str) -> str:
    """Обновление контекста (заметок) задачи по ID"""
    try:
        async with async_session_factory() as session:
            stmt = update(LongTermTask).where(LongTermTask.id == task_id).values(context=new_context).returning(LongTermTask)
            result = await session.execute(stmt)
            updated_task = result.scalar_one_or_none()
            await session.commit()
            
            if updated_task:
                msg = f"Контекст задачи обновлен — ID: {updated_task.id} | New Context: [{updated_task.context}]"
                system_logger.debug(msg)
                return msg
            else:
                return f"Задача с ID {task_id} не найдена."
            
    except Exception as e:
        system_logger.error(f"Ошибка при обновлении контекста задачи {task_id}: {e}")
        return f"Ошибка: {e}"
    
@watchdog_decorator(sql_db_module)
async def update_task_full(task_id: int, **kwargs) -> str:
    """Обновляет любые переданные поля задачи разом"""
    try:
        async with async_session_factory() as session:
            update_data = {k: v for k, v in kwargs.items() if v is not None}
            if not update_data:
                return "Нет данных для обновления задачи."

            stmt = update(LongTermTask).where(LongTermTask.id == task_id).values(**update_data).returning(LongTermTask)
            result = await session.execute(stmt)
            updated_task = result.scalar_one_or_none()
            await session.commit()
            
            if updated_task:
                return f"Задача ID {updated_task.id} успешно обновлена."
            return f"Задача с ID {task_id} не найдена."
    except Exception as e:
        system_logger.error(f"Ошибка при полном обновлении задачи {task_id}: {e}")
        return f"Ошибка базы данных: {e}"
    
