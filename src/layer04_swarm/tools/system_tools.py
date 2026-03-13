from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events
from src.layer01_datastate.sql_db.management.swarm_state import update_subagent_memory, get_subagent_memory


# =================================================
# СХЕМЫ ИНСТРУМЕНТОВ
# =================================================

trigger_alert_scheme = {
    "type": "function",
    "function": {
        "name": "trigger_swarm_alert",
        "description": "Экстренно разбудить главного агента, если сработал триггер.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Подробный отчет о том, что случилось."}
            },
            "required": ["message"]
        }
    }
}

set_memory_scheme = {
    "type": "function",
    "function": {
        "name": "set_memory_key",
        "description": "Записать значение в твой личный JSON-блокнот. Используй для сохранения ID последних сообщений, дат или промежуточных выводов.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Ключ (например, 'last_msg_id')"},
                "value": {"type": "string", "description": "Значение для сохранения"}
            },
            "required": ["key", "value"]
        }
    }
}

get_memory_scheme = {
    "type": "function",
    "function": {
        "name": "get_memory_key",
        "description": "Достать значение из твоего личного JSON-блокнота по ключу.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Ключ, который нужно прочитать"}
            },
            "required": ["key"]
        }
    }
}

delegate_scheme = {
    "type": "function",
    "function": {
        "name": "delegate_task_to_swarm",
        "description": "Передать выполнение задачи другому специалисту (эстафета). ПРАВИЛО: перед вызовом сохрани собранные данные в файл (write_local_file) и передай имя файла в инструкциях новому агенту.",
        "parameters": {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string", 
                    "enum": ["Researcher", "SystemAnalyst", "ChatSummarizer", "Chronicler"], 
                    "description": "Роль нового агента."
                },
                "instructions": {
                    "type": "string", 
                    "description": "Подробное ТЗ для нового агента. Обязательно укажи, какой файл из песочницы ему нужно прочитать."
                }
            },
            "required": ["role", "instructions"]
        }
    }
}

escalate_scheme = {
    "type": "function",
    "function": {
        "name": "escalate_to_lead",
        "description": "Экстренно прервать работу и разбудить главного агента, если задача невыполнима, нет данных или произошла критическая аномалия.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string", 
                    "description": "Подробная причина эскалации."
                }
            },
            "required": ["reason"]
        }
    }
}

system_tools_schemas = [trigger_alert_scheme, set_memory_scheme, get_memory_scheme, delegate_scheme, escalate_scheme]


# =================================================
# ЛОГИКА
# =================================================

async def trigger_swarm_alert(subagent, message: str) -> str:
    await event_bus.publish(Events.SWARM_ALERT, source=subagent.name, alert=message)
    return "Тревога успешно отправлена Главному Агенту."

async def set_memory_key(subagent, key: str, value: str) -> str:
    await update_subagent_memory(subagent.name, key, value)
    subagent.memory_state[key] = value # Обновляем локально для скорости
    return f"Значение '{value}' по ключу '{key}' успешно сохранено."

async def get_memory_key(subagent, key: str) -> str:
    mem = await get_subagent_memory(subagent.name)
    subagent.memory_state = mem # Синхронизируем
    val = mem.get(key)
    if val is None:
        return f"Ключ '{key}' не найден в памяти."
    return str(val)

async def delegate_task_to_swarm(subagent, role: str, instructions: str) -> str:
    """Спавнит потомка и передает ему эстафету"""
    depth = getattr(subagent, 'chain_depth', 0)
    
    if depth >= 3:
        return "Ошибка: Достигнут лимит делегирования (Depth 3). Вы обязаны завершить задачу самостоятельно."
    
    if role == "WebMonitor":
        return "Ошибка: Создание бессмертных демонов запрещено. Выберите другую роль."

    import uuid
    short_id = str(uuid.uuid4())[:6]
    new_name = f"{role}_{short_id}"

    # Определяем корень миссии. Если родителя нет, значит текущий агент и есть корень.
    root_parent = getattr(subagent, 'parent_name', None) or subagent.name

    from src.layer04_swarm.manager import swarm_manager
    await swarm_manager.spawn_child_subagent(
        role=role,
        name=new_name,
        instructions=instructions,
        parent_name=root_parent,
        chain_depth=depth + 1
    )
    
    subagent.is_delegated = True # Флаг для движка
    return f"Успех: Задача передана агенту {new_name}. Миссия: {root_parent}. Ваши вычислительные ресурсы возвращены в общий пул ядра. Сейчас вы будете отключены. Спасибо за службу."

async def escalate_to_lead(subagent, reason: str) -> str:
    """Поднимает панику и будит Вегу"""
    root_parent = getattr(subagent, 'parent_name', None) or subagent.name
    message = f"[Эскалация от {subagent.name} | Миссия: {root_parent}]:\n{reason}"
    
    await event_bus.publish(Events.SWARM_ALERT, source=subagent.name, alert=message)
    subagent.is_escalated = True # Флаг для движка
    return "Эскалация успешно отправлена главному агенту. Работа завершается."

system_tools_registry = {
    "trigger_swarm_alert": trigger_swarm_alert,
    "set_memory_key": set_memory_key,
    "get_memory_key": get_memory_key,
    "delegate_task_to_swarm": delegate_task_to_swarm,
    "escalate_to_lead": escalate_to_lead
}