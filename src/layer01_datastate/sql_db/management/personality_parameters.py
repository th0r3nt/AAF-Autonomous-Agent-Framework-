from sqlalchemy import select, delete
from src.layer01_datastate.sql_db.sql_db import async_session_factory
from src.layer01_datastate.sql_db.sql_models import PersonalityTrait
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog_decorator import watchdog_decorator
from src.layer00_utils.watchdog.watchdog import sql_db_module


# ----------------------------------------------------------------------------------------------
# ТАБЛИЦА: PersonalityTrait (Мета-программирование личности)

@watchdog_decorator(sql_db_module)
async def get_formatted_personality() -> str:
    """Служебная: отдает список черт характера для инъекции в системный промпт"""
    try:
        async with async_session_factory() as session:
            query = select(PersonalityTrait).order_by(PersonalityTrait.created_at)
            result = await session.execute(query)
            traits = result.scalars().all()

            if not traits:
                return ""
            
            lines = [f"- {t.trait} (Причина: {t.reason} | ID: {t.id})" for t in traits]
            return "\n".join(lines)
    except Exception as e:
        system_logger.error(f"Ошибка при получении черт личности: {e}")
        return ""

@watchdog_decorator(sql_db_module)
async def manage_personality_trait(action: str, trait: str = None, trait_id: int = None, reason: str = None) -> str:
    """CRUD для управления чертами характера (вызывается через навык)"""
    try:
        async with async_session_factory() as session:
            if action == "add":
                if not trait or not reason:
                    return "Ошибка: Для добавления черты необходимо передать 'trait' и 'reason'."
                new_trait = PersonalityTrait(trait=trait, reason=reason)
                session.add(new_trait)
                await session.commit()
                system_logger.info(f"[Personality] Добавлена новая черта: {trait}")
                return f"Новая черта характера успешно добавлена. ID: {new_trait.id}"
                
            elif action == "remove":
                if not trait_id:
                    return "Ошибка: Для удаления необходимо передать 'trait_id'."
                stmt = delete(PersonalityTrait).where(PersonalityTrait.id == trait_id)
                result = await session.execute(stmt)
                await session.commit()
                if result.rowcount > 0:
                    system_logger.info(f"[Personality] Черта ID {trait_id} удалена.")
                    return f"Черта характера ID {trait_id} успешно удалена."
                return f"Черта с ID {trait_id} не найдена."
                
            elif action == "get_all":
                query = select(PersonalityTrait).order_by(PersonalityTrait.created_at)
                result = await session.execute(query)
                traits = result.scalars().all()
                if not traits:
                    return "Список приобретенных черт характера пуст."
                return "Текущие черты характера:\n" + "\n".join([f"ID: {t.id} | {t.trait}" for t in traits])
            else:
                return "Ошибка: Неизвестное действие. Используйте 'add', 'remove' или 'get_all'."
    except Exception as e:
        return f"Ошибка БД при управлении личностью: {e}"