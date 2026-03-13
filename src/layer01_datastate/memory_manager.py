import asyncio
from config.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer01_datastate.vector_db.vector_db_management import (
    raw_find_entries_in_vector_db, 
    add_new_entry_in_vector_db, 
    delete_entries_in_vector_db,
    get_all_entries_in_vector_db
)
from src.layer01_datastate.sql_db.management.mental_state import upsert_mental_entity, remove_mental_essence
from src.layer01_datastate.sql_db.management.long_term_tasks import create_task, update_task_full, delete_task, get_all_tasks
from src.layer01_datastate.sql_db.management.search_logs import deep_search_logs
from src.layer01_datastate.sql_db.management.agent_actions import get_raw_recent_actions, get_raw_recent_thoughts
from src.layer01_datastate.sql_db.management.dialogue import get_raw_recent_dialogue
from src.layer01_datastate.sql_db.management.personality_parameters import manage_personality_trait

class MemoryManager:
    """
    Фасад для управления всеми типами памяти агента.
    Скрывает низкоуровневую логику SQL и ChromaDB, предоставляя чистый API для LLM.
    """

    async def recall_memory(self, queries: list) -> str:
        """Асинхронный поиск сразу по всем векторным коллекциям"""
        system_logger.info(f"[MemoryManager] Извлечение воспоминаний по запросам: {queries}")
        
        collections = ["user_vector_db", "agent_vector_db", "agent_thoughts_vector_db"]
        tasks = []
        
        # Формируем задачи: каждый запрос ищем в каждой коллекции
        for query in queries:
            for col in collections:
                tasks.append(raw_find_entries_in_vector_db(col, query, 3))
                
        # Делаем асинхронный залп
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Собираем всё в один плоский список и отсеиваем ошибки
        all_results = []
        for res in results_lists:
            if isinstance(res, list):
                all_results.extend(res)

        if not all_results:
            return "В векторной памяти ничего не найдено по данным запросам."

        # Удаляем дубликаты (по ID записи)
        unique_results = {item['id']: item for item in all_results}.values()
        
        # Сортируем по релевантности (чем меньше distance, тем точнее совпадение)
        sorted_results = sorted(unique_results, key=lambda x: x['distance'])

        # Маппинг для красивого вывода
        col_tags = {
            "user_vector_db": "[ИНФОРМАЦИЯ О ГЛАВНОМ ПОЛЬЗОВАТЕЛЕ (user_vector_db)]",
            "agent_vector_db": "[БАЗА ЗНАНИЙ (agent_vector_db)]",
            "agent_thoughts_vector_db": "[ИНТРОСПЕКЦИЯ (agent_thoughts_vector_db)]"
        }

        # Формируем красивый текст
        formatted_lines = ["Результаты из ассоциативной памяти (отсортировано по релевантности):"]
        for res in sorted_results[:10]: # Возвращаем топ-10 лучших совпадений
            tag = col_tags.get(res['collection'], "[НЕИЗВЕСТНО]")
            formatted_lines.append(
                f"{tag} (ID: '{res['id']}' | Дата: {res['date']} | Схожесть: {res['distance']:.3f}): {res['text']}"
            )

        return "\n\n".join(formatted_lines)

    async def memorize_information(self, topic: str, text: str) -> str:
        """Запись фактов и мыслей с маршрутизацией по топикам"""
        topic_map = {
            "user_fact": "user_vector_db",
            "system_knowledge": "agent_vector_db",
            "introspection": "agent_thoughts_vector_db"
        }
        
        target_collection = topic_map.get(topic)
        if not target_collection:
            return f"Ошибка: Неизвестный топик '{topic}'. Доступные: {list(topic_map.keys())}"
            
        # Вызываем синхронную функцию добавления в отдельном потоке
        result = await add_new_entry_in_vector_db(target_collection, text)
        system_logger.info(f"[MemoryManager] Новая запись в {target_collection}.")
        return result

    async def forget_information(self, collection_name: str, ids: list) -> str:
        """Удаляет устаревшие записи из векторной базы"""
        if collection_name not in ["user_vector_db", "agent_vector_db", "agent_thoughts_vector_db"]:
            return "Ошибка: Неверное имя коллекции."
            
        result = await delete_entries_in_vector_db(collection_name, ids)
        return result
    
    async def get_all_vector_memory(self, collection_name: str) -> str:
        """Возвращает все записи из указанной векторной коллекции"""
        if collection_name not in ["user_vector_db", "agent_vector_db", "agent_thoughts_vector_db"]:
            return "Ошибка: Неверное имя коллекции."
            
        # Функция синхронная, поэтому запускаем в отдельном потоке, чтобы не блочить Event Loop
        result = await asyncio.to_thread(get_all_entries_in_vector_db, collection_name)
        return result

    async def manage_entity(self, action: str, name: str, category: str = None, tier: str = None, description: str = None, status: str = None, context: str = None, rules: str = None) -> str:
        """Единый пульт управления Картиной мира (Mental State)"""
        if action == "delete":
            return await remove_mental_essence(name)
        elif action == "upsert":
            return await upsert_mental_entity(
                name=name, category=category, tier=tier, 
                description=description, status=status, 
                context=context, rules=rules
            )
        else:
            return "Ошибка: Неизвестное действие. Используйте 'upsert' или 'delete'."

    async def manage_task(self, action: str, task_id: int = None, description: str = None, status: str = None, term: str = None, context: str = None) -> str:
        """Единый диспетчер задач"""
        if action == "get_all":
            return await get_all_tasks()
            
        elif action == "create":
            if not description:
                return "Ошибка: Для создания задачи требуется 'description'."
            return await create_task(description, status or "pending", term)
            
        elif action == "update":
            if not task_id:
                return "Ошибка: Для обновления требуется 'task_id'."
            return await update_task_full(task_id, task_description=description, status=status, term=term, context=context)
            
        elif action == "delete":
            if not task_id:
                return "Ошибка: Для удаления требуется 'task_id'."
            return await delete_task(task_id)
            
        else:
            return "Ошибка: Неизвестное действие. Используйте 'create', 'update', 'delete' или 'get_all'."

    async def deep_history_search(self, target: str, query: str = None, action_type: str = None, source: str = None, days_ago: int = None, limit: int = 50) -> str:
        """Машина времени для логов и диалогов"""
        return await deep_search_logs(
            target=target, query=query, action_type=action_type, 
            source=source, days_ago=days_ago, limit=limit
        )
    async def get_formatted_thoughts(self, limit: int) -> str:
        """Возвращает последние мысли для жесткого буфера контекста"""
        thoughts = await get_raw_recent_thoughts(limit=limit)
        if not thoughts:
            return "Нет недавних мыслей."
            
        lines = []
        for t in reversed(thoughts): # Переворачиваем, чтобы старые были сверху
            time_str = t.created_at.strftime('%H:%M:%S')
            text = t.details.get('text', '')
            lines.append(f"[{time_str}] [ИНТРОСПЕКЦИЯ]: {text}")
        return "\n".join(lines)

    async def get_chronicle_timeline(self, limit: int = 50) -> str:
        """Синтезирует единую хронологию"""
        actions, dialogues, thoughts = await asyncio.gather(
            get_raw_recent_actions(limit=limit),
            get_raw_recent_dialogue(limit=limit),
            get_raw_recent_thoughts(limit=limit),
            return_exceptions=True
        )
        
        main_pool = []
        if not isinstance(actions, Exception): 
            main_pool.extend(actions)
        if not isinstance(dialogues, Exception): 
            main_pool.extend(dialogues)
        if not isinstance(thoughts, Exception): 
            main_pool.extend(thoughts)
        
        # Сортируем строго по времени и обрезаем
        main_pool.sort(key=lambda x: x.created_at)
        timeline = main_pool[-limit:] if main_pool else []

        if not timeline:
            return "Хронология пуста."

        formatted_lines = []
        for item in timeline:
            time_str = item.created_at.strftime('%H:%M:%S')
            
            if hasattr(item, 'action_type'):
                if item.action_type == "memorize_information" and item.details.get("topic") == "introspection":
                    text = item.details.get('text', '')
                    formatted_lines.append(f"[{time_str}] [ИНТРОСПЕКЦИЯ]: {text}")
                else:
                    details_str = str(item.details)
                    if len(details_str) > 150: 
                        details_str = details_str[:150] + "..."
                    formatted_lines.append(f"[{time_str}] [ДЕЙСТВИЕ | {item.action_type}]: {details_str}")
                    
            elif hasattr(item, 'actor'):
                if item.actor == "System":
                    formatted_lines.append(f"[{time_str}] ⚙️ [СИСТЕМА]: {item.message}")
                elif item.actor == config.identity.agent_name:
                    formatted_lines.append(f"[{time_str}] 🤖 [{config.identity.agent_name} -> {item.source}]: {item.message}")
                else:
                    formatted_lines.append(f"[{time_str}] 👤 [{item.actor} -> {item.source}]: {item.message}")

        return "\n".join(formatted_lines)
    
    async def manage_personality(self, action: str, trait: str = None, trait_id: int = None, reason: str = None) -> str:
        """Управление приобретенными чертами характера"""
        return await manage_personality_trait(action, trait, trait_id, reason)
    
    async def get_raw_memories(self, queries: list) -> list[dict]:
        """Служебная функция для G-RAG: получает сырые словари из вектора без форматирования"""
        collections = ["user_vector_db", "agent_vector_db", "agent_thoughts_vector_db"]
        tasks = []
        
        # Убираем пустые строки и None
        valid_queries = [q for q in queries if q and str(q).strip()]
        if not valid_queries:
            return []

        for query in valid_queries:
            for col in collections:
                tasks.append(raw_find_entries_in_vector_db(col, query, 3))
                
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        all_results = []
        for res in results_lists:
            if isinstance(res, list):
                all_results.extend(res)
        return all_results

    def format_raw_memories(self, all_results: list[dict]) -> str:
        """Форматирует сырые результаты с жесткой дедупликацией по ID"""
        if not all_results:
            return "В векторной памяти ничего не найдено."

        # Удаляем дубликаты (по ID записи)
        unique_results = {item['id']: item for item in all_results}.values()
        sorted_results = sorted(unique_results, key=lambda x: x['distance'])

        col_tags = {
            "user_vector_db": "[ИНФОРМАЦИЯ О ГЛАВНОМ ПОЛЬЗОВАТЕЛЕ (user_vector_db)]",
            "agent_vector_db": "[БАЗА ЗНАНИЙ (agent_vector_db)]",
            "agent_thoughts_vector_db": "[ИНТРОСПЕКЦИЯ (agent_thoughts_vector_db)]"
        }

        formatted_lines = ["Результаты из ассоциативной памяти (отсортировано по релевантности):"]
        for res in sorted_results[:12]: # Увеличили лимит до 12, так как инфы стало больше
            tag = col_tags.get(res['collection'], "[НЕИЗВЕСТНО]")
            formatted_lines.append(
                f"{tag} (ID: '{res['id']}' | Дата: {res['date']} | Схожесть: {res['distance']:.3f}): {res['text']}"
            )

        return "\n\n".join(formatted_lines)


memory_manager = MemoryManager()