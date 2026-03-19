import asyncio
import ast
import textwrap
import re
from pathlib import Path

from src.layer00_utils.config_manager import config
from src.layer00_utils.watchdog.watchdog import watchdog
from src.layer00_utils.workspace import workspace_manager
from src.layer00_utils.logger import system_logger
from src.layer00_utils.sandbox_env.deployments import get_active_deployments_status

from src.layer01_datastate.event_bus.events import EventConfig
from src.layer01_datastate.memory_manager import memory_manager
from src.layer01_datastate.global_state.global_state_monitoring import global_state_monitoring
from src.layer01_datastate.sql_db.management.mental_state import get_all_mental_states
from src.layer01_datastate.sql_db.management.dialogue import get_clear_recent_dialogue, get_dialogue_by_source
from src.layer01_datastate.sql_db.management.long_term_tasks import get_all_tasks
from src.layer01_datastate.sql_db.management.agent_actions import get_recent_agent_actions
from src.layer01_datastate.graph_db.graph_db_management import get_graph_rag_data, get_all_node_names_async, get_recent_graph_updates

from src.layer03_brain.agent.skills.telegram.logic import get_unread_tg_summary
from src.layer04_swarm.manager import swarm_manager


class ContextBuilder:
    def __init__(self):
        # Суперузлы, которые мы игнорируем при Graph-RAG, чтобы не взорвать контекст ассоциациями
        self.SUPERNODES = {
            config.identity.agent_name.lower(), 
            config.identity.admin_name.lower()
        }

    # ========================================================================
    # СЛУЖЕБНЫЕ ХЕЛПЕРЫ
    # ========================================================================

    async def _get_macro_architecture_map(self) -> str:
        """Собирает макро-карту файлов проекта (корневые .md и папки слоев)"""
        try:
            current_dir = Path(__file__).resolve()
            src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
            
            if not src_dir.exists() or src_dir.name != "src":
                return "[Архитектурная карта недоступна]"

            lines =[
                "Системная архитектура (Макро-уровень):", 
                "Твое ядро - это фреймворк AAF (Autonomous Agent Framework) на Python.",
            ]
            
            layers = sorted([d for d in src_dir.iterdir() if d.is_dir() and d.name.startswith("layer")])
            
            for layer in layers:
                docstring = "Описание отсутствует"
                init_file = layer / "__init__.py"
                
                if init_file.exists():
                    try:
                        with open(init_file, 'r', encoding='utf-8') as f:
                            module = ast.parse(f.read())
                            doc = ast.get_docstring(module)
                            if doc:
                                docstring = doc.split('\n')[0].strip()
                    except Exception:
                        pass
                        
                lines.append(f"- src/{layer.name}/ : {docstring}")
                
            lines.append("\nПометка: чтобы увидеть полную структуру всех .py и .md файлов, используй навык get_system_architecture_map().")
            return "\n".join(lines)
        except Exception as e:
            return f"[Ошибка генерации макро-карты: {e}]"
        
    def _safe_get(self, result, default="Данные недоступны"):
        """Защищает от падения при return_exceptions=True в asyncio.gather"""
        if isinstance(result, Exception):
            system_logger.error(f"[ContextBuilder] Ошибка при сборе данных: {result}")
            return default
        return result
    
    def _format_event(self, event: EventConfig, args: tuple, kwargs: dict) -> str:
        """Описывает событие, которое заставило агента проснуться, в удобном для LLM формате"""
        kwargs = kwargs or {}
        args = args or ()
        details = []
        
        if event.name == "AGENT_NEW_INCOMING_MESSAGE_TG":
            username = kwargs.get("username", "Unknown")
            text = kwargs.get("text", "")
            msg_id = kwargs.get("message_id", "Неизвестно")
            details.append(f"[От: @{username} в Telegram] (ID сообщения: {msg_id}): {text}")
            
        elif event.name == "AGENT_NEW_MENTION_TG":
            chat = kwargs.get("chat_title", "Unknown Chat")
            chat_id = kwargs.get("chat_id", "Неизвестно") 
            username = kwargs.get("username", "Unknown")
            text = kwargs.get("text", "")
            msg_id = kwargs.get("message_id", "Неизвестно")
            details.append(f"[Telegram-упоминание в группе '{chat}' (ID чата: {chat_id}) от @{username}] (ID сообщения: {msg_id}): {text}")

        elif event.name == "SWARM_INFO":
            source = kwargs.get("source", "Неизвестный субагент")
            result = kwargs.get("result", "Нет данных")
            details.append(f"[Отчет от субагента '{source}']: \n{result}")
            
        elif event.name == "SWARM_ERROR":
            source = kwargs.get("source", "Неизвестный субагент")
            error = kwargs.get("error", "Неизвестная ошибка")
            details.append(f"[субагент '{source}' умер с ошибкой]: {error}")
            
        elif event.name == "SWARM_ALERT":
            source = kwargs.get("source", "Неизвестный субагент")
            alert = kwargs.get("alert", "Тревога")
            details.append(f"[Уведомление от субагента '{source}']: {alert}")

        elif event.name == "SANDBOX_ATTENTION_REQUIRED":
            alert_msg = kwargs.get("alert_message", "Без текста")
            details.append(f"[Уведомление от локального скрипта]: {alert_msg}")

        elif event.name == "DEPLOYMENT_CRASHED":
            project = kwargs.get("project", "Unknown")
            status = kwargs.get("status", "Unknown")
            details.append(f"Микросервис '{project}' упал. Статус: {status}.")

        elif event.name == "EXTERNAL_WEBHOOK_RECEIVED":
            topic = kwargs.get("topic_name", "Unknown")
            payload = kwargs.get("payload", "Пусто")
            details.append(f"[Входящий Webhook | Топик: {topic}]: Данные: {payload}")
            
        else:
            if args: 
                details.append(f"Данные: {args}")
            if kwargs: 
                formatted_kwargs = ", ".join([f"{k}='{v}'" for k, v in kwargs.items()])
                details.append(f"Параметры: {formatted_kwargs}")
                
        details_str = " | ".join(details) if details else "Нет деталей"
        
        return textwrap.dedent(f"""
            Входящее событие: {event.name}
            Описание: {event.description}
            Детали: {details_str}
            Уровень важности: {event.level.name}
            """).strip()

    def _extract_query_from_event(self, event: EventConfig, args: tuple, kwargs: dict) -> str:
        """Извлекает чистый текст из события для поиска по векторной БД"""
        kwargs = kwargs or {}
        args = args or ()
        
        if event.name in["AGENT_NEW_INCOMING_MESSAGE_TG", "USER_NEW_INCOMING_MESSAGE_TG", "AGENT_NEW_MENTION_TG"]:
            return kwargs.get("text", event.description)
        else:
            return event.description

    def _extract_graph_targets_from_event(self, event: EventConfig, kwargs: dict) -> list:
        """Вытаскивает имена из события для принудительного поиска в графе"""
        kwargs = kwargs or {}
        targets =[]
        if event.name in["AGENT_NEW_INCOMING_MESSAGE_TG", "AGENT_NEW_MENTION_TG", "AGENT_NEW_GROUP_MESSAGE"]:
            if "username" in kwargs and kwargs["username"] != "Unknown":
                targets.append(kwargs["username"])
            if "chat_title" in kwargs and kwargs["chat_title"] != "Unknown Chat":
                targets.append(kwargs["chat_title"])
        return targets

    def _sync_extract_anchors(self, text_lower: str, all_nodes: list) -> list:
        """Синхронный поиск известных узлов в тексте"""
        found_anchors = set()
        for node in all_nodes:
            if node.lower() in self.SUPERNODES:
                continue
                
            aliases = [node.lower()]
            if "(" in node and ")" in node:
                clean_name = re.sub(r'\(.*?\)', '', node).strip().lower()
                if clean_name:
                    aliases.append(clean_name)
                    
            for alias in aliases:
                if len(alias) <= 3:
                    if re.search(rf'\b{re.escape(alias)}\b', text_lower):
                        found_anchors.add(node)
                        break 
                else:
                    if alias in text_lower:
                        found_anchors.add(node)
                        break
        return list(found_anchors)

    async def _extract_graph_anchors_from_text(self, text: str) -> list:
        """Ищет в тексте имена узлов, которые уже существуют в Graph DB"""
        if not text:
            return[]
        all_nodes = await get_all_node_names_async()
        if not all_nodes:
            return[]
        return await asyncio.to_thread(self._sync_extract_anchors, text.lower(), all_nodes)


    # ========================================================================
    # СБОРКА БЛОКОВ И МАРШРУТИЗАЦИЯ
    # ========================================================================

    async def _fetch_base_context(self, limits, exclude_keywords: list = None) -> dict:
        """Единый метод сбора базовых данных для ВСЕХ циклов"""
        tasks = {
            "global_state": global_state_monitoring.get_global_state(),
            "mental_state": get_all_mental_states(),
            "active_deployments": get_active_deployments_status(),

            "recent_thoughts": memory_manager.get_formatted_thoughts(limit=limits.thoughts_limit),
            "recent_actions": get_recent_agent_actions(limit=limits.actions_limit),
            
            # Передаем exclude_keywords для защиты от дублирования истории
            "recent_dialogues": get_clear_recent_dialogue(limit=limits.dialogue_limit, exclude_keywords=exclude_keywords),

            "unread_tg": get_unread_tg_summary(),
            "system_health": watchdog.get_system_modules_report(),
            "tasks": get_all_tasks(),
            "swarm_status": swarm_manager.get_swarm_status(),
            "sandbox_files": asyncio.to_thread(workspace_manager.get_sandbox_files_list),
            "macro_arch": self._get_macro_architecture_map()
        }

        keys = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return {key: self._safe_get(res) for key, res in zip(keys, results)}

    async def _build_standard_rag_context(self, text_for_anchors: str, base_vector_queries: list):
        """Одноступенчатый RAG (для проактивности и интроспекции)"""
        anchors = await self._extract_graph_anchors_from_text(text_for_anchors)
        graph_context, associated_nodes = await get_graph_rag_data(anchors)
        
        vector_queries = base_vector_queries + associated_nodes
        vector_context = await memory_manager.recall_memory(vector_queries)
        
        return graph_context, vector_context

    async def _build_event_rag_context(self, search_query: str, explicit_targets: list):
        """Двухступенчатый RAG (Для Event-Driven, так как там нужен первичный поиск по смыслу)"""
        initial_memories = await memory_manager.get_raw_memories([search_query])
        initial_text = " ".join([m['text'] for m in initial_memories])

        combined_text = f"{search_query}\n{initial_text}"
        implicit_targets = await self._extract_graph_anchors_from_text(combined_text)
        all_targets = list(set(explicit_targets + implicit_targets))

        graph_context, associated_nodes = await get_graph_rag_data(all_targets)

        secondary_memories =[]
        if associated_nodes:
            secondary_memories = await memory_manager.get_raw_memories(associated_nodes)

        all_memories = initial_memories + secondary_memories
        vector_context = memory_manager.format_raw_memories(all_memories)

        return graph_context, vector_context

    def _render_markdown(self, context: dict, cycle_type: str) -> str:
        """Собирает итоговый текст для LLM на основе собранных блоков"""
        from src.layer03_brain.agent.engine.engine import brain_engine
        from src.layer03_brain.llm.client import key_manager

        system_architecture = context.get('macro_arch')
        active_deployments = context.get('active_deployments', 'Нет запущенных микросервисов.')
        system_health = context.get('system_health')
        mental_state = context.get('mental_state')
        global_state = context.get('global_state')

        recent_thoughts = context.get('recent_thoughts')
        recent_actions = context.get('recent_actions')
        recent_dialogues = context.get('recent_dialogues')

        sandbox_files = context.get('sandbox_files')
        background_events = context.get('background_events', 'Нет фоновых событий.')
        swarm_status = context.get('swarm_status')
        tasks = context.get('tasks')
        unread_tg = context.get('unread_tg')

        # Базовые блоки, которые есть у всех
        parts = f"""
## SYSTEM ARCHITECTURE (система AAF, макро-уровень)
{system_architecture}

## ACTIVE DEPLOYMENTS (микросервисы)
{active_deployments}

## SYSTEM HEALTH (Отчет Watchdog) 
{system_health}

## SYSTEM SETTINGS (текущие настройки системы AAF)
- LLM-модель (твое ядро): {config.llm.model_name}
- Состояние API: {key_manager.get_api_status_string()}
- Температура: {config.llm.temperature}
- Max ReAct Steps: {config.llm.max_react_steps}
- Интервал проактивности: {brain_engine.proactivity_interval} сек.
- Интервал интроспекции: {brain_engine.thoughts_interval} сек.

## MENTAL STATE (картина мира) 
{mental_state}

## GLOBAL STATE 
{global_state}

## RECENT AGENT THOUGHTS (последние мысли)
{recent_thoughts}

## RECENT AGENT ACTIONS (недавние действия)
{recent_actions}

## GLOBAL DIALOGUE HISTORY (внешняя среда)
{recent_dialogues}

## UNREAD TELEGRAM MESSAGES (непрочитанные сообщения)
{unread_tg}

## SANDBOX FILES (текущие файлы в Sandbox) 
{sandbox_files}

## BACKGROUND EVENTS (фоновые события) 
{background_events}

## ACTIVE SWARM PROCESSES (субагенты) 
{swarm_status}

## LONG-TERM TASKS (долгосрочные задачи) 
{tasks}
"""
        
        # ----------------------------------------------------------------
        # EVENT-DRIVEN
        # ----------------------------------------------------------------
        if cycle_type == "event_driven":
            specific_history = context.get('specific_chat_history')
            if not specific_history: 
                specific_history = "Нет специфичной истории для данного события."

            graph_context = context.get('graph_context')
            vector_context = context.get('vector_context')
            event_description = context.get('event_description')
            
            parts += f"""
## SPECIFIC CHAT HISTORY (История переписки с текущим собеседником)
{specific_history}

## FROM GRAPH DB (Прямые и косвенные связи)
{graph_context}

## ASSOCIATIVE MEMORY (Векторный поиск + Graph-RAG ассоциации)
{vector_context}

## CURRENT EVENT (входящее событие)
{event_description}
"""
            
        # ----------------------------------------------------------------
        # PROACTIVITY
        # ----------------------------------------------------------------
        elif cycle_type == "proactivity":
            graph_context = context.get('graph_context')
            vector_context = context.get('vector_context')

            parts += f"""
## FROM GRAPH DB (Связи активных объектов и задач)
{graph_context}

## ASSOCIATIVE MEMORY (Векторный поиск + Graph-RAG ассоциации)
{vector_context}
"""

        # ----------------------------------------------------------------
        # THOUGHTS
        # ----------------------------------------------------------------
        elif cycle_type == "thoughts":
            recent_graph_updates = context.get('recent_graph_updates', 'Нет новых связей.')
            graph_context = context.get('graph_context')
            vector_context = context.get('vector_context')

            parts += f"""
## RECENT GRAPH DB UPDATES (Последние изменения связей)
{recent_graph_updates}

## FROM GRAPH DB (Связи, упомянутые в недавних событиях)
{graph_context}

## ASSOCIATIVE MEMORY (Векторный поиск + Graph-RAG ассоциации)
{vector_context}
"""
        return parts.strip()


    # ========================================================================
    # ПУБЛИЧНЫЕ МЕТОДЫ (ВЫЗЫВАЮТСЯ ИЗ МОЗГА)
    # ========================================================================

    async def build_event_driven_context(self, event: EventConfig, args: tuple = None, kwargs: dict = None) -> str:
        from src.layer03_brain.events_monitoring import events_monitoring
        kwargs = kwargs or {}
        args = args or ()
        
        # 1. Защита от дублирования сообщений текущего чата в глобальной истории
        exclude_kws =[]
        chat_source = kwargs.get("chat_source")
        if chat_source:
            exclude_kws.append(chat_source.replace("tg_agent_chat_(", "").replace("tg_agent_group_(", "").replace(")", ""))
        if "chat_id" in kwargs:
            exclude_kws.append(str(kwargs["chat_id"]))
            
        limits = config.llm.context_depth.event_driven
        context = await self._fetch_base_context(limits, exclude_keywords=exclude_kws)
        
        # 2. Уникальные данные для события
        context["background_events"] = self._safe_get(await events_monitoring.get_background_events())
        context["event_description"] = self._format_event(event, args, kwargs)
        
        if chat_source:
            context["specific_chat_history"] = self._safe_get(await get_dialogue_by_source(source=chat_source, limit=20))
            
        # 3. Запускаем двухступенчатый RAG
        search_query = self._extract_query_from_event(event, args, kwargs)
        explicit_targets = self._extract_graph_targets_from_event(event, kwargs)
        
        graph_context, vector_context = await self._build_event_rag_context(search_query, explicit_targets)
        context["graph_context"] = graph_context
        context["vector_context"] = vector_context

        return self._render_markdown(context, "event_driven")

    async def build_proactivity_context(self) -> str:
        from src.layer03_brain.events_monitoring import events_monitoring
        
        limits = config.llm.context_depth.proactivity
        context = await self._fetch_base_context(limits)
        context["background_events"] = self._safe_get(await events_monitoring.get_background_events())
        
        # Ищем якоря в Картине мира, задачах и непрочитанных сообщениях
        text_for_rag = f"{context['mental_state']} \n {context['tasks']} \n {context['unread_tg']}"
        
        graph_context, vector_context = await self._build_standard_rag_context(
            text_for_anchors=text_for_rag, 
            base_vector_queries=["Анализ системы и планирование"]
        )
        context["graph_context"] = graph_context
        context["vector_context"] = vector_context
        
        return self._render_markdown(context, "proactivity")

    async def build_thoughts_context(self) -> str:
        limits = config.llm.context_depth.thoughts
        context = await self._fetch_base_context(limits)
        
        # Уникальные данные для интроспекции
        context["recent_graph_updates"] = self._safe_get(await get_recent_graph_updates(limit=15))
        
        # Ищем паттерны в недавних событиях (действия + диалоги)
        text_for_rag = f"{context['recent_actions']} \n {context['recent_dialogues']}"
        
        graph_context, vector_context = await self._build_standard_rag_context(
            text_for_anchors=text_for_rag, 
            base_vector_queries=["Анализ паттернов, рефлексия, выводы"]
        )
        context["graph_context"] = graph_context
        context["vector_context"] = vector_context
        
        return self._render_markdown(context, "thoughts")

# Экземпляр синглтона для импорта
context_builder = ContextBuilder()

# Оставляем прокси-функции для обратной совместимости с `react_management.py`
async def build_event_driven_context(event, args, kwargs):
    return await context_builder.build_event_driven_context(event, args, kwargs)

async def build_proactivity_context():
    return await context_builder.build_proactivity_context()

async def build_thoughts_context():
    return await context_builder.build_thoughts_context()