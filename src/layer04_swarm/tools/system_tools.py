from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events
from src.layer01_datastate.sql_db.management.swarm_state import update_subagent_memory, get_subagent_memory

# =================================================
# СИСТЕМНЫЕ СИГНАТУРЫ ДЛЯ СУБАГЕНТОВ (L0)
# =================================================

system_tools_l0_manifest = [
    "- `aaf://swarm/trigger_swarm_alert(message: str)` -> Экстренно разбудить главного агента, если сработал триггер.",
    "- `aaf://swarm/set_memory_key(key: str, value: str)` -> Записать значение в твой личный JSON-блокнот.",
    "- `aaf://swarm/get_memory_key(key: str)` -> Достать значение из твоего личного JSON-блокнота по ключу.",
    "- `aaf://swarm/delegate_task_to_swarm(role: 'Researcher'|'SystemAnalyst'|'ChatSummarizer'|'Chronicler', instructions: str)` -> Передать выполнение задачи другому специалисту.",
    "- `aaf://swarm/escalate_to_lead(reason: str)` -> Экстренно прервать работу и разбудить главного агента, если задача невыполнима."
]

# =================================================
# ЛОГИКА
# =================================================

async def trigger_swarm_alert(subagent, message: str) -> str:
    await event_bus.publish(Events.SWARM_ALERT, source=subagent.name, alert=message)
    return "Тревога успешно отправлена Главному Агенту."

async def set_memory_key(subagent, key: str, value: str) -> str:
    await update_subagent_memory(subagent.name, key, value)
    subagent.memory_state[key] = value 
    return f"Значение '{value}' по ключу '{key}' успешно сохранено."

async def get_memory_key(subagent, key: str) -> str:
    mem = await get_subagent_memory(subagent.name)
    subagent.memory_state = mem 
    val = mem.get(key)
    if val is None:
        return f"Ключ '{key}' не найден в памяти."
    return str(val)

async def delegate_task_to_swarm(subagent, role: str, instructions: str) -> str:
    depth = getattr(subagent, 'chain_depth', 0)
    
    if depth >= 3:
        return "Ошибка: Достигнут лимит делегирования (Depth 3). Вы обязаны завершить задачу самостоятельно."
    
    if role == "WebMonitor":
        return "Ошибка: Создание бессмертных демонов запрещено. Выберите другую роль."

    import uuid
    short_id = str(uuid.uuid4())[:6]
    new_name = f"{role}_{short_id}"

    root_parent = getattr(subagent, 'parent_name', None) or subagent.name

    from src.layer04_swarm.manager import swarm_manager
    await swarm_manager.spawn_child_subagent(
        role=role,
        name=new_name,
        instructions=instructions,
        parent_name=root_parent,
        chain_depth=depth + 1
    )
    
    subagent.is_delegated = True
    return f"Успех: Задача передана агенту {new_name}. Миссия: {root_parent}. Ваши вычислительные ресурсы возвращены в общий пул ядра. Сейчас вы будете отключены. Спасибо за службу."

async def escalate_to_lead(subagent, reason: str) -> str:
    root_parent = getattr(subagent, 'parent_name', None) or subagent.name
    message = f"[Эскалация от {subagent.name} | Миссия: {root_parent}]:\n{reason}"
    
    await event_bus.publish(Events.SWARM_ALERT, source=subagent.name, alert=message)
    subagent.is_escalated = True 
    return "Эскалация успешно отправлена главному агенту. Работа завершается."

# Реестр привязан к URI
system_tools_registry = {
    "aaf://swarm/trigger_swarm_alert": trigger_swarm_alert,
    "aaf://swarm/set_memory_key": set_memory_key,
    "aaf://swarm/get_memory_key": get_memory_key,
    "aaf://swarm/delegate_task_to_swarm": delegate_task_to_swarm,
    "aaf://swarm/escalate_to_lead": escalate_to_lead
}