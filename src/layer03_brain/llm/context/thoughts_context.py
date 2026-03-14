import asyncio
from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog import watchdog
from src.layer00_utils.workspace import workspace_manager
from src.layer01_datastate.memory_manager import memory_manager
from src.layer01_datastate.global_state.global_state_monitoring import global_state_monitoring
from src.layer01_datastate.sql_db.management.mental_state import get_all_mental_states
from src.layer01_datastate.sql_db.management.dialogue import get_clear_recent_dialogue
from src.layer01_datastate.sql_db.management.long_term_tasks import get_all_tasks
from src.layer01_datastate.sql_db.management.agent_actions import get_recent_agent_actions
from src.layer01_datastate.graph_db.graph_db_management import get_recent_graph_updates, explore_graph, get_associated_node_names
from src.layer03_brain.agent.skills.telegram.logic import get_unread_tg_summary
from src.layer03_brain.llm.context.helpers import _safe_get, _get_macro_architecture_map, extract_graph_anchors_from_text, SUPERNODES
from src.layer03_brain.llm.client import key_manager

async def build_thoughts_context() -> str:
    """Собирает контекст для цикла интроспекции (с поддержкой Graph-RAG)"""
    from src.layer03_brain.agent.engine.engine import brain_engine
    try:
        # -----------------------------------------------------------------------------------
        # 1. Получаем базовый контекст

        limits = config.llm.context_depth.thoughts

        results = await asyncio.gather(
            global_state_monitoring.get_global_state(),  
            memory_manager.get_formatted_thoughts(limit=limits.thoughts_limit),
            get_recent_agent_actions(limit=limits.actions_limit),
            get_clear_recent_dialogue(limit=limits.dialogue_limit),
            watchdog.get_system_modules_report(),        
            get_all_mental_states(),
            get_unread_tg_summary(),
            get_all_tasks(),
            _get_macro_architecture_map(),
            get_recent_graph_updates(limit=15),
            asyncio.to_thread(workspace_manager.get_sandbox_files_list),
            return_exceptions=True
        )
        
        global_state = _safe_get(results[0])
        recent_thoughts = _safe_get(results[1])
        recent_actions = _safe_get(results[2])
        recent_dialogues = _safe_get(results[3])
        system_health = _safe_get(results[4]) 
        mental_state = _safe_get(results[5]) 
        unread_tg = _safe_get(results[6])   
        tasks = _safe_get(results[7])
        macro_architecture_map = _safe_get(results[8])
        recent_graph_updates = _safe_get(results[9])
        sandbox_files = _safe_get(results[10])


        # -----------------------------------------------------------------------------------
        # 2. GRAPH-RAG: Поиск скрытых паттернов в недавних событиях
        
        # Склеиваем последние диалоги и действия, чтобы найти там сущности
        recent_text_for_analysis = f"{recent_actions}\n{recent_dialogues}"
        raw_anchors = await extract_graph_anchors_from_text(recent_text_for_analysis)
        anchors = [a for a in raw_anchors if a not in SUPERNODES]

        graph_context = "Нет релевантных связей для недавних событий."
        associated_nodes = []

        if anchors:
            graph_tasks = [explore_graph(anchor) for anchor in anchors[:5]]
            graph_results = await asyncio.gather(*graph_tasks, return_exceptions=True)

            graph_lines = []
            for res in graph_results:
                if not isinstance(res, Exception) and "не найден" not in res and "нет связей" not in res:
                    graph_lines.append(res)
            if graph_lines:
                graph_context = "\n\n".join(graph_lines)

            # Достаем соседей для Вектора
            associated_nodes = await get_associated_node_names(anchors[:5], limit_per_node=2)


        # -----------------------------------------------------------------------------------
        # 3. GRAPH-RAG: Векторный поиск по ассоциациям
        
        vector_queries = ["Анализ паттернов, рефлексия, выводы"]
        if associated_nodes:
            system_logger.info(f"[Graph-RAG | Thoughts] Интуитивная связь с узлами: {associated_nodes}. Векторный поиск расширен.")
            vector_queries.extend(associated_nodes)

        vector_context = await memory_manager.recall_memory(vector_queries)


        # -----------------------------------------------------------------------------------
        # 4. Выдаем результат

        return f"""
## SYSTEM ARCHITECTURE (твоя система)
{macro_architecture_map}

## SYSTEM HEALTH (Отчет Watchdog о состоянии системных модулей и процессов)
{system_health}

## SYSTEM SETTINGS (Текущие настройки твоей системы)
- LLM-модель (твое ядро): {config.llm.model_name}
- Состояние API: {key_manager.get_api_status_string()}
- Температура: {config.llm.temperature}
- Max ReAct Steps: {config.llm.max_react_steps}
- Интервал вызова цикла проактивности: {brain_engine.proactivity_interval} сек.
- Интервал вызова цикла интроспекции: {brain_engine.thoughts_interval} сек.

## MENTAL STATE (Твоя картина мира)
{mental_state}

## GLOBAL STATE
{global_state}

## SANDBOX FILES (Текущие файлы в песочнице)
{sandbox_files}

## RECENT AGENT THOUGHTS (Твои последние мысли)
{recent_thoughts}

## RECENT AGENT ACTIONS (Твои недавние действия)
{recent_actions}

## GLOBAL DIALOGUE HISTORY (Внешняя среда)
{recent_dialogues}

## LONG-TERM TASKS (Долгосрочные задачи)
{tasks}

## UNREAD TELEGRAM MESSAGES (Непрочитанные сообщения в Telegram (если есть))
{unread_tg}

## RECENT GRAPH DB UPDATES (Последние изменения связей)
{recent_graph_updates}

## FROM GRAPH DB (Связи, упомянутые в недавних событиях)
{graph_context}

## ASSOCIATIVE MEMORY (Векторный поиск + Graph-RAG ассоциации)
{vector_context}
"""

    except Exception as e:
        system_logger.error(f"Ошибка при формировании контекста интроспекции: {e}")
        return "Критическая ошибка интроспекции."