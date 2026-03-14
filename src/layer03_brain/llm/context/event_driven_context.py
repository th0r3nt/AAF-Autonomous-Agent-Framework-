import asyncio
from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog import watchdog
from src.layer00_utils.workspace import workspace_manager
from src.layer01_datastate.memory_manager import memory_manager
from src.layer01_datastate.global_state.global_state_monitoring import global_state_monitoring
from src.layer01_datastate.sql_db.management.mental_state import get_all_mental_states
from src.layer01_datastate.sql_db.management.dialogue import get_dialogue_by_source, get_clear_recent_dialogue
from src.layer01_datastate.sql_db.management.long_term_tasks import get_all_tasks
from src.layer01_datastate.sql_db.management.agent_actions import get_recent_agent_actions
from src.layer01_datastate.event_bus.events import EventConfig
from src.layer01_datastate.graph_db.graph_db_management import get_graph_rag_data
from src.layer03_brain.agent.skills.skills import get_unread_tg_summary
from src.layer03_brain.llm.context.helpers import (
    _format_event, _extract_query_from_event, _safe_get, 
    _get_macro_architecture_map, _extract_graph_targets_from_event,
    extract_graph_anchors_from_text, SUPERNODES
)
from src.layer03_brain.llm.client import key_manager
from src.layer04_swarm.manager import swarm_manager

async def build_event_driven_context(event: EventConfig, args: tuple = None, kwargs: dict = None) -> str:
    """Собирает контекст для ответа на входящее событие (Event-Driven) с поддержкой Reverse G-RAG"""
    from src.layer03_brain.agent.engine.engine import brain_engine
    from src.layer03_brain.events_monitoring import events_monitoring
    try:
        # -----------------------------------------------------------------------------------
        # 0. Определяем источник текущего чата

        chat_source = kwargs.get("chat_source") if kwargs else None
        exclude_kws = []
        if chat_source:
            exclude_kws.append(chat_source.replace("tg_agent_chat_(", "").replace("tg_agent_group_(", "").replace(")", ""))
        if kwargs and "chat_id" in kwargs:
            exclude_kws.append(str(kwargs["chat_id"]))


        # -----------------------------------------------------------------------------------
        # 1. Получаем базовый контекст

        limits = config.llm.context_depth.event_driven

        results = await asyncio.gather(
            global_state_monitoring.get_global_state(),
            get_all_mental_states(),
            memory_manager.get_formatted_thoughts(limit=limits.thoughts_limit),
            get_recent_agent_actions(limit=limits.actions_limit),
            get_clear_recent_dialogue(limit=limits.dialogue_limit, exclude_keywords=exclude_kws),
            get_unread_tg_summary(),
            watchdog.get_system_modules_report(),
            _get_macro_architecture_map(),
            get_all_tasks(),
            swarm_manager.get_swarm_status(),
            events_monitoring.get_background_events(),
            asyncio.to_thread(workspace_manager.get_sandbox_files_list),
            return_exceptions=True 
        )

        global_state = _safe_get(results[0])
        mental_state = _safe_get(results[1])
        recent_thoughts = _safe_get(results[2])
        recent_actions = _safe_get(results[3])
        recent_dialogues = _safe_get(results[4])
        unread_tg = _safe_get(results[5])
        system_health = _safe_get(results[6])
        macro_architecture_map = _safe_get(results[7])
        tasks = _safe_get(results[8])
        swarm_status = _safe_get(results[9])
        background_events = _safe_get(results[10])
        sandbox_files = _safe_get(results[11])


        # ===================================================================================
        # GRAPH-RAG КАСКАД
        # ===================================================================================
        
        # Шаг 1: Первичный Вектор (Смысл)
        search_query = _extract_query_from_event(event, args, kwargs)
        initial_memories = await memory_manager.get_raw_memories([search_query])
        initial_text = " ".join([m['text'] for m in initial_memories])

        # Шаг 2: Парсинг Якорей (Смысл -> Граф)
        # Ищем узлы и в исходном сообщении, и в том, что достали из памяти
        combined_text_for_parsing = f"{search_query}\n{initial_text}"
        
        explicit_targets = _extract_graph_targets_from_event(event, kwargs)
        implicit_targets = await extract_graph_anchors_from_text(combined_text_for_parsing)
        
        all_targets = list(set(explicit_targets + implicit_targets))
        all_targets = [t for t in all_targets if t not in SUPERNODES]

        # Шаг 3: Граф (Интуиция Depth 1 & 2)
        graph_context = "Нет релевантных связей в графе для текущего события."
        associated_nodes = []
        
        if all_targets:
            system_logger.info(f"[Graph-RAG] Извлечены узлы для анализа: {all_targets}")
            graph_context, associated_nodes = await get_graph_rag_data(all_targets)

        # Шаг 4: Вторичный Вектор (Экспансия)
        secondary_memories = []
        if associated_nodes:
            system_logger.info(f"[Graph-RAG] Интуиция сработала. Расширен поиск по узлам: {associated_nodes}")
            secondary_memories = await memory_manager.get_raw_memories(associated_nodes)

        # Склеиваем и форматируем (с дедупликацией)
        all_memories = initial_memories + secondary_memories
        vector_context = memory_manager.format_raw_memories(all_memories)

        # ===================================================================================

        event_description = _format_event(event, args, kwargs)
        specific_chat_history = ""
        if chat_source:
            specific_chat_history = await get_dialogue_by_source(source=chat_source, limit=20)

        # -----------------------------------------------------------------------------------
        # Выдаем результат
        return f"""
## SYSTEM ARCHITECTURE (твоя система, макро-уровень)
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

## BACKGROUND EVENTS (фоновые события в системе)
{background_events}

## ACTIVE SWARM PROCESSES (субагенты)
{swarm_status}

## LONG-TERM TASKS (Долгосрочные задачи)
{tasks}

## SPECIFIC CHAT HISTORY (История переписки именно с текущим собеседником/чатом)
{specific_chat_history if specific_chat_history else "Нет специфичной истории для данного события."}

## RECENT AGENT THOUGHTS (Твои последние мысли)
{recent_thoughts}

## RECENT AGENT ACTIONS (Твои недавние действия)
{recent_actions}

## GLOBAL DIALOGUE HISTORY (Внешняя среда)
{recent_dialogues}

## UNREAD TELEGRAM MESSAGES (Непрочитанные сообщения в Telegram (если есть))
{unread_tg}

## FROM GRAPH DB (Прямые и косвенные связи текущих объектов)
{graph_context}

## ASSOCIATIVE MEMORY (Векторный поиск + Graph-RAG ассоциации)
{vector_context}

## CURRENT EVENT (входящее событие)
{event_description}
"""

    except Exception as e:
        system_logger.error(f"Ошибка при формировании контекста для ответа на событие: {e}")
        return "Критическая ошибка сборки контекста."