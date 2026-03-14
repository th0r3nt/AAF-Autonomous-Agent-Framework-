from src.layer01_datastate.memory_manager import (
    memory_manager
)
from src.layer01_datastate.graph_db.graph_db_management import (
    manage_graph, explore_graph, get_full_graph, delete_from_graph
)

async def recall_memory(queries: list) -> str:
    """Обертка: Асинхронный поиск по всем векторным базам"""
    return await memory_manager.recall_memory(queries)

async def memorize_information(topic: str, text: str) -> str:
    """Обертка: Сохранение информации в векторную базу по топикам"""
    return await memory_manager.memorize_information(topic, text)

async def forget_information(collection_name: str, ids: list) -> str:
    """Обертка: Удаление информации из векторной базы"""
    return await memory_manager.forget_information(collection_name, ids)

async def manage_entity(action: str, name: str, category: str = None, tier: str = None, description: str = None, status: str = None, context: str = None, rules: str = None) -> str:
    """Обертка: Управление Картиной Мира (Mental State)"""
    return await memory_manager.manage_entity(action, name, category, tier, description, status, context, rules)

async def manage_task(action: str, task_id: int = None, description: str = None, status: str = None, term: str = None, context: str = None) -> str:
    """Обертка: Диспетчер долгосрочных задач"""
    return await memory_manager.manage_task(action, task_id, description, status, term, context)

async def deep_history_search(target: str, query: str = None, action_type: str = None, source: str = None, days_ago: int = None, limit: int = 50) -> str:
    """Обертка: Поиск по старым логам действий и диалогам"""
    return await memory_manager.deep_history_search(target, query, action_type, source, days_ago, limit)

async def get_chronicle_timeline(limit: int = 50) -> str:
    """Обертка: Получение единого таймлайна событий"""
    return await memory_manager.get_chronicle_timeline(limit)

async def get_all_vector_memory(collection_name: str) -> str:
    """Обертка: Получение абсолютно всех записей из векторной базы"""
    return await memory_manager.get_all_vector_memory(collection_name)

async def manage_graph_db(source: str, target: str, base_type: str, context: str = "[Нет контекста]") -> str:
    """Обертка: Управление графом связей"""
    return await manage_graph(source, target, base_type, context)

async def explore_graph_db(query: str) -> str:
    """Обертка: Исследование графа"""
    return await explore_graph(query)

async def get_full_graph_db() -> str:
    """Обертка: Полный дамп графа"""
    return await get_full_graph()

async def delete_from_graph_db(source_node: str, target_node: str = None) -> str:
    """Обертка: Удаление из графа"""
    return await delete_from_graph(source_node, target_node)

async def manage_personality(action: str, trait: str = None, trait_id: int = None, reason: str = None) -> str:
    """Обертка: Управление личностью"""
    return await memory_manager.manage_personality(action, trait, trait_id, reason)

MEMORY_REGISTRY = {
    "recall_memory": recall_memory,
    "memorize_information": memorize_information,
    "forget_information": forget_information,
    "manage_entity": manage_entity,
    "manage_task": manage_task,
    "deep_history_search": deep_history_search,
    "get_chronicle_timeline": get_chronicle_timeline,
    "get_all_vector_memory": get_all_vector_memory,
    "manage_graph": manage_graph_db,
    "explore_graph": explore_graph_db,
    "get_full_graph": get_full_graph_db,
    "delete_from_graph": delete_from_graph_db,
    "manage_personality": manage_personality,
}