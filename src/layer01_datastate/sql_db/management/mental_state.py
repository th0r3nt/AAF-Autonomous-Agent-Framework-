import datetime
from sqlalchemy import desc, select, delete
from src.layer01_datastate.sql_db.sql_db import async_session_factory
from src.layer01_datastate.sql_db.sql_models import MentalStateEntity
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog_decorator import watchdog_decorator
from src.layer00_utils.watchdog.watchdog import sql_db_module


# ----------------------------------------------------------------------------------------------
# ТАБЛИЦА: MentalStateEntity (состояния разных сущностей)

@watchdog_decorator(sql_db_module)
async def add_mental_essence(name: str, description: str, status: str = "Неизвестно", category: str = "subject", tier: str = "medium") -> str:
    """Добавляет новую сущность в картину мира (ментальное состояние)"""
    try:
        async with async_session_factory() as session:
            query = select(MentalStateEntity).where(MentalStateEntity.name == name)
            result = await session.execute(query)
            if result.scalar_one_or_none():
                return f"Сущность '{name}' уже существует в базе."

            new_entity = MentalStateEntity(
                name=name,
                category=category,
                tier=tier,
                description=description,
                status=status,
                context="[Нет]",
                rules="[Нет]"
            )
            session.add(new_entity)
            await session.commit()
            
            msg = f"Сущность '{name}' успешно добавлена в картину мира (Cat: {category}, Tier: {tier})."
            system_logger.debug(msg)
            return msg
    except Exception as e:
        system_logger.error(f"Ошибка при добавлении сущности в ментальное состояние: {e}")
        return f"Ошибка: {e}"

@watchdog_decorator(sql_db_module)
async def update_mental_state(name: str, key: str, value: str) -> str:
    """Обновляет конкретный параметр (key) у сущности (name)"""
    ALLOWED_KEYS = ["description", "status", "context", "rules", "category", "tier"]
    if key not in ALLOWED_KEYS:
        return f"Ошибка: ключ '{key}' запрещен. Разрешены только: {', '.join(ALLOWED_KEYS)}"

    try:
        async with async_session_factory() as session:
            query = select(MentalStateEntity).where(MentalStateEntity.name == name)
            result = await session.execute(query)
            entity = result.scalar_one_or_none()

            if not entity:
                return f"Сущность '{name}' не найдена."

            setattr(entity, key, value)
            
            await session.commit()
            
            msg = f"Ментальное состояние обновлено: [{name}] {key} = {value}"
            system_logger.debug(msg)
            return msg
    except Exception as e:
        system_logger.error(f"Ошибка при обновлении MentalState: {e}")
        return f"Ошибка: {e}"

@watchdog_decorator(sql_db_module)
async def remove_mental_essence(name: str) -> str:
    """Удаляет сущность из картины мира"""
    if name in ["agent", "admin"]:
        return "Удаление базовых сущностей (agent, admin) категорически запрещено системой."
        
    try:
        async with async_session_factory() as session:
            stmt = delete(MentalStateEntity).where(MentalStateEntity.name == name)
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                msg = f"Сущность '{name}' стерта из картины мира (ментальное состояние)."
                system_logger.debug(msg)
                return msg
            return f"Сущность '{name}' не найдена."
    except Exception as e:
        system_logger.error(f"Ошибка при удалении MentalState: {e}")
        return f"Ошибка: {e}"

@watchdog_decorator(sql_db_module)
async def get_all_mental_states() -> str:
    """Возвращает отформатированную картину мира с делением на ACTIVE FOCUS и PERIPHERAL VISION"""
    try:
        async with async_session_factory() as session:
            query = select(MentalStateEntity).order_by(desc(MentalStateEntity.updated_at))
            result = await session.execute(query)
            entities = result.scalars().all()

            if not entities:
                return "Картина мира пуста."

            now = datetime.datetime.now(datetime.timezone.utc)
            
            active_focus = []
            peripheral_vision = []

            for e in entities:
                # Вычисляем время
                entity_time = e.updated_at
                if entity_time.tzinfo is None:
                    entity_time = entity_time.replace(tzinfo=datetime.timezone.utc)
                
                delta = now - entity_time
                hours_passed = delta.total_seconds() / 3600
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                
                if hours > 16:
                    days = hours // 16
                    time_ago = f"{days} дн. назад"
                elif hours > 0:
                    time_ago = f"{hours} ч. {minutes} мин. назад"
                else:
                    time_ago = f"{minutes} мин. назад"

                # Логика распределения: Фокус или Периферия
                is_active = False
                if e.tier in ["critical", "high"]:
                    is_active = True
                elif e.tier == "medium" and hours_passed <= 16: 
                    is_active = True
                
                if is_active:
                    # Полная карточка для Фокуса
                    block = f"[{e.name}] (Tier: {e.tier} | Category: {e.category} | Обновлено: {time_ago} ({e.updated_at.strftime('%Y-%m-%d %H:%M')}))\n"
                    block += f"* description: {e.description}\n"
                    block += f"* status: {e.status}\n"
                    block += f"* context: {e.context}\n"
                    block += f"* rules: {e.rules}\n"
                    active_focus.append(block)
                else:
                    # Кратка выжимка для Периферии
                    peripheral_vision.append(f"- [{e.name}] (Tier: {e.tier} | Cat: {e.category}): {e.description} (Обновлено: {time_ago})")
                
            # Собираем итоговую строку
            res = "### ACTIVE MENTAL MEMORY\n"
            res += "Важные сущности и те, с кем недавно было взаимодействие.\n\n"
            res += "\n".join(active_focus) if active_focus else "Пусто."
            
            res += "\n\n### BACKGROUND MENTAL MEMORY\n"
            res += "Неактивные/маловажные в данных момент сущности.\n\n"
            res += "\n".join(peripheral_vision) if peripheral_vision else "Пусто."

            return res.strip()
            
    except Exception as e:
        system_logger.error(f"[MentalState] Ошибка получения MentalState: {e}")
        return "Ошибка получения картины мира."
    
@watchdog_decorator(sql_db_module)
async def upsert_mental_entity(name: str, **kwargs) -> str:
    """Создает или обновляет сущность в Mental State (Upsert)"""
    try:
        async with async_session_factory() as session:
            query = select(MentalStateEntity).where(MentalStateEntity.name == name)
            result = await session.execute(query)
            entity = result.scalar_one_or_none()

            # Очищаем kwargs от None
            update_data = {k: v for k, v in kwargs.items() if v is not None}

            if entity:
                if not update_data:
                    return f"Сущность '{name}' найдена, но нет данных для обновления."
                for key, value in update_data.items():
                    setattr(entity, key, value)
                await session.commit()
                return f"Сущность '{name}' успешно обновлена в Mental State."
            else:
                if 'description' not in update_data:
                    return f"Ошибка: Сущность '{name}' не найдена. Для её создания обязательно передайте параметр 'description'."
                
                new_entity = MentalStateEntity(
                    name=name,
                    category=update_data.get('category', 'subject'),
                    tier=update_data.get('tier', 'medium'),
                    description=update_data['description'],
                    status=update_data.get('status', 'Неизвестно'),
                    context=update_data.get('context', '[Нет]'),
                    rules=update_data.get('rules', '[Нет]')
                )
                session.add(new_entity)
                await session.commit()
                return f"Новая сущность '{name}' успешно создана в Mental State."
    except Exception as e:
        system_logger.error(f"Ошибка при Upsert MentalState: {e}")
        return f"Ошибка базы данных: {e}"
    
