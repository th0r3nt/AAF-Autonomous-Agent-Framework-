from sqlalchemy import select, update
from src.layer01_datastate.sql_db.sql_db import async_session_factory
from src.layer01_datastate.sql_db.sql_models import SubagentState
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog_decorator import watchdog_decorator
from src.layer00_utils.watchdog.watchdog import sql_db_module

@watchdog_decorator(sql_db_module)
async def create_or_reset_subagent(name: str, role: str, instructions: str, trigger_condition: str = None, interval_sec: int = None, parent_name: str = None, chain_depth: int = 0) -> SubagentState:
    """Создает нового субагента или воскрешает старого с очисткой памяти"""
    try:
        async with async_session_factory() as session:
            query = select(SubagentState).where(SubagentState.name == name)
            result = await session.execute(query)
            existing = result.scalar_one_or_none()

            if existing:
                existing.role = role
                existing.instructions = instructions
                existing.trigger_condition = trigger_condition
                existing.interval_sec = interval_sec
                existing.parent_name = parent_name
                existing.chain_depth = chain_depth
                existing.status = "running"
                existing.memory_state = {} 
                agent_obj = existing
                system_logger.debug(f"[SQL DB] Субагент '{name}' перезаписан.")
            else:
                new_agent = SubagentState(
                    name=name,
                    role=role,
                    instructions=instructions,
                    trigger_condition=trigger_condition,
                    interval_sec=interval_sec,
                    parent_name=parent_name,
                    chain_depth=chain_depth,
                    status="running",
                    memory_state={}
                )
                session.add(new_agent)
                agent_obj = new_agent
                system_logger.debug(f"[SQL DB] Создан субагент '{name}' (Роль: {role}).")
            
            await session.commit()
            await session.refresh(agent_obj)
            return agent_obj
    except Exception as e:
        system_logger.error(f"Ошибка при создании субагента: {e}")
        raise e

@watchdog_decorator(sql_db_module)
async def update_subagent_status(name: str, new_status: str):
    """Обновляет статус (completed, killed, error, sleeping, running)"""
    try:
        async with async_session_factory() as session:
            stmt = update(SubagentState).where(SubagentState.name == name).values(status=new_status)
            await session.execute(stmt)
            await session.commit()
    except Exception as e:
        system_logger.error(f"Ошибка при обновлении статуса субагента: {e}")

@watchdog_decorator(sql_db_module)
async def update_subagent_memory(name: str, key: str, value: any):
    """Записывает ключ-значение в JSON-блокнот субагента"""
    try:
        async with async_session_factory() as session:
            query = select(SubagentState).where(SubagentState.name == name)
            result = await session.execute(query)
            agent = result.scalar_one_or_none()

            if agent:
                # Копируем словарь, меняем, отдаем обратно (особенность SQLAlchemy JSONB)
                new_memory = dict(agent.memory_state)
                new_memory[key] = value
                agent.memory_state = new_memory
                
                await session.commit()
    except Exception as e:
        system_logger.error(f"Ошибка при обновлении памяти субагента: {e}")

@watchdog_decorator(sql_db_module)
async def get_subagent_memory(name: str) -> dict:
    """Возвращает весь JSON-блокнот субагента"""
    try:
        async with async_session_factory() as session:
            query = select(SubagentState).where(SubagentState.name == name)
            result = await session.execute(query)
            agent = result.scalar_one_or_none()
            return agent.memory_state if agent else {}
    except Exception:
        return {}

@watchdog_decorator(sql_db_module)
async def get_active_subagents() -> list[SubagentState]:
    """Для менеджера: получить всех, кто должен работать после рестарта ПК"""
    try:
        async with async_session_factory() as session:
            query = select(SubagentState).where(SubagentState.status.in_(["running", "sleeping"]))
            result = await session.execute(query)
            return list(result.scalars().all())
    except Exception:
        return []
    
@watchdog_decorator(sql_db_module)
async def update_subagent_config(name: str, instructions: str = None, trigger_condition: str = None, interval_sec: int = None) -> bool:
    """Точечно обновляет параметры субагента в БД (для горячей перезагрузки)"""
    try:
        async with async_session_factory() as session:
            query = select(SubagentState).where(SubagentState.name == name)
            result = await session.execute(query)
            agent = result.scalar_one_or_none()

            if agent:
                if instructions is not None:
                    agent.instructions = instructions
                if trigger_condition is not None:
                    agent.trigger_condition = trigger_condition
                if interval_sec is not None:
                    agent.interval_sec = interval_sec
                
                await session.commit()
                return True
            return False
    except Exception as e:
        system_logger.error(f"Ошибка при обновлении конфига субагента '{name}': {e}")
        return False