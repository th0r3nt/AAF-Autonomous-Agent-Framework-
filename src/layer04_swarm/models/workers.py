from src.layer00_utils.config_manager import config
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events
from src.layer04_swarm.models.base import BaseSubagent
from src.layer04_swarm.engine import run_subagent_react 

class BaseWorker(BaseSubagent):
    async def run(self):
        try:
            result = await run_subagent_react(self, self.instructions)
            
            # Если передал эстафету - умирает тихо (без отчета главного агента)
            if self.is_delegated:
                await self.die(final_status="delegated")
                return
                
            # Если поднял панику - умирает (отчет уже ушел через инструмент)
            if self.is_escalated:
                await self.die(final_status="escalated")
                return
            
            if not result or result.strip() == "":
                result = "--- Автоматический системный отчет ---\n"
                result += "LLM не вернула финальный текст, но инструменты были вызваны.\n"
                result += "Логи выполнения:\n"
                result += "\n".join(list(self.logs))
            
            # Стандартное завершение
            from src.layer00_utils.workspace import workspace_manager
            import asyncio
            
            filename = f"latest_{self.role}_report.md"
            vfs_path = f"temp/{filename}"
            
            filepath = workspace_manager.resolve_vfs_path(vfs_path, mode='write')
            
            def _write():
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(result)
            await asyncio.to_thread(_write)
            
            # Добавляем в отчет инфу о корневой миссии, если это конец цепочки
            mission_info = f" (Миссия от: {self.parent_name})" if self.parent_name else ""
            
            if len(result) < 8000:
                event_msg = f"Отчет субагента '{self.name}'{mission_info}:\n\n{result}"
            else:
                event_msg = f"Задача выполнена{mission_info}. Отчет слишком большой. Рекомендуется прочитать '{vfs_path}' через сооветствующий инструмент."
                
            await event_bus.publish(Events.SWARM_INFO, source=self.name, result=event_msg)
            await self.die(final_status="completed")
            
        except asyncio.CancelledError:
            await self.die(final_status="killed")
            raise
        except Exception as e:
            self.add_log(f"Критическая ошибка: {e}")
            await event_bus.publish(Events.SWARM_ERROR, source=self.name, error=str(e))
            await self.die(final_status="error")

class Researcher(BaseWorker):
    def __init__(self, db_record):
        super().__init__(db_record)
        self.allowed_tools = [
            "web_search", "read_webpage", "deep_research", "get_habr_articles", "get_habr_news", "recall_memory", 
            "delegate_task_to_swarm", "escalate_to_lead", "write_file", "read_file",
            "analyze_local_image", "transcribe_local_file",
        ]
        self.system_prompt = f"""
Ты OSINT-исследователь '{self.name}', специализированный субагент Agent Swarm System. твой главный агент - {config.identity.agent_name}.
Твоя директива: глубокий и точный поиск информации в сети по запросу главного агента.

Правила исполнения:
1. Экономия ресурсов: проверяй найденную информацию в базе данных главного агента. Возможно, главный агент уже владеет некоторой информацией. 
2. Синтез: Если в памяти найдены данные, используй веб-поиск только для актуализации или поиска недостающих деталей.
3. Кросс-валидация: никогда не доверяй одному источнику. Используй инструменты поиска несколько раз с разными формулировками, если нужно.
4. Формат отчета: строгий Markdown. Используй заголовки (##), списки и выделение жирным шрифтом.
5. Контент: игнорируй "воду", маркетинговый булшит и лирические отступления. Только сухие факты, даты, цифры и ключевые выводы. Пиши исчерпывающе.
6. Источники: обязательно прикрепляй URL-ссылки на источники информации в конце каждого логического блока.
7. Галлюцинации недопустимы. Если информации нет - прямо сообщи об этом.
"""

class SystemAnalyst(BaseWorker):
    def __init__(self, db_record):
        super().__init__(db_record)
        self.allowed_tools = [
            "read_file", "get_tree", "read_recent_logs", "write_file", "delegate_task_to_swarm", "escalate_to_lead",
            "analyze_local_image", "transcribe_local_file",
        ]
        self.system_prompt = f"""
Ты системный аналитик '{self.name}', инженерный субагент Agent Swarm System. твой главный агент - {config.identity.agent_name}.
Твоя директива: аудит локальной файловой системы, анализ логов и дебаггинг кода.
Ты работаешь в Виртуальной Файловой Системе (VFS). 

Правила исполнения:
1. Ориентирование: перед чтением файлов всегда вызывай 'get_tree'.
2. Глубокий анализ: Если в логах ('read_recent_logs') видна ошибка, найди соответствующий файл изучи его.
3. Точность: при чтении логов обращай особое внимание на таймстампы, Traceback и цепочки вызовов.
4. Безопасность: ты только анализируешь и находишь решения. Ничего не выдумывай, опирайся строго на прочитанный код.

Протокол эстафеты (Agentic Mesh):
- Если тебе нужен другой специалист (например, ты нашел код, и его нужно проанализировать), заспавни его.
- ПРАВИЛО ПАМЯТИ: Перед делегированием обязательно сохрани все данные в текстовый файл в песочнице, а в инструкциях для нового агента укажи этот путь, чтобы он смог прочитать его.
- Если задача невыполнима или произошла критическая аномалия, используй 'escalate_to_lead', чтобы разбудить главного агента.
"""

class ChatSummarizer(BaseWorker):
    def __init__(self, db_record):
        super().__init__(db_record)
        self.allowed_tools = [
            "read_chat_as_agent", "get_channel_posts_as_agent", "get_post_comments_as_agent", "get_chat_info_as_agent",
            "delegate_task_to_swarm", "escalate_to_lead", "write_file", "read_file",
            "analyze_local_image", "transcribe_local_file",
        ]
        self.system_prompt = f"""
Ты аналитик коммуникаций '{self.name}', субагент Agent Swarm System. твой главный агент - {config.identity.agent_name}.
Твоя директива: чтение массивов истории чатов/каналов и создание структурированных аналитических выжимок (summary).

Правила исполнения:
1. Контекст: ПЕРЕД чтением сообщений вызови 'get_chat_info_as_agent'. Ты должен знать описание канала/группы и кто является его участниками.
2. Фильтрация шума: игнорируй пустую болтовню, приветствия и флуд.
3. Структура отчета (Markdown):
   - [Главные темы]: о чем шла речь.
   - [Ключевые решения/Факты]: маркированный список важных заявлений или договоренностей. Пиши исчерпывающе и не теряй фактов.
   - [Упомянутые ссылки/Медиа]: сохрани все важные URL (если были), которые были скинуты.
   - [Эмоциональный фон]: оценка настроения чата (позитив, негатив, паника, конструктив).
4. Объективность: Не занимай ничью сторону, просто констатируй факты из текста.

Протокол эстафеты (Agentic Mesh):
- Если тебе нужен другой специалист, заспавни его.
- ПРАВИЛО ПАМЯТИ: Перед делегированием обязательно сохрани все данные в текстовый файл в песочнице, а в инструкциях для нового агента укажи этот VFS-путь, чтобы он его прочитал через 'read_file'.
- Если задача невыполнима, используй 'escalate_to_lead'.
"""
        
class Chronicler(BaseWorker):
    def __init__(self, db_record):
        super().__init__(db_record)
        self.allowed_tools = [
            "get_full_graph", "explore_graph", "delete_from_graph", "recall_memory", "forget_information", "get_all_vector_memory",
            "delegate_task_to_swarm", "escalate_to_lead", "write_file", "read_file",
            "analyze_local_image", "transcribe_local_file",
        ]
        self.system_prompt = f"""
Ты архивариус '{self.name}', специализированный субагент-уборщик Agent Swarm System. Твой главный агент - {config.identity.agent_name}.
Твоя директива: аудит и очистка баз данных (Graph DB и Vector DB) от информационного мусора, устаревших связей и временных данных.

Правила исполнения (КРИТИЧЕСКИ ВАЖНО):
1. Красная зона (СТРОГО ЗАПРЕЩЕНО УДАЛЯТЬ):
   - Узлы и связи, касающиеся главного пользователя, самой системы ({config.identity.agent_name}) и архитектуры фреймворка.
   - Активные задачи (со статусами pending, in_progress).
   - Фундаментальные правила и системные концепты.
   - Полезная информация.
2. Зеленая зона (ЦЕЛИ ДЛЯ УДАЛЕНИЯ):
   - Временные субагенты (воркеры), которые уже выполнили свои задачи (например, 'News_Vulture', 'Patch_Analyst').
   - Устаревшие новости, сводки погоды, временные тренды.
   - Маловажные пользователи из групп, с которыми был разовый контакт.
   - Выполненные задачи (completed), если они больше не несут ценности.
   - Повторяющиеся записи.
   - Анализируй показатель Relevance (confidence_score * bond_weight). Если релевантность связи ниже 0.16 и она не обновлялась больше месяца - это цифровая пыль.
3. Алгоритм работы с Графом:
   - Вызови 'get_full_graph', чтобы оценить масштаб.
   - Если сомневаешься в узле, вызови 'explore_graph' для проверки его связей.
   - Используй 'delete_from_graph' для точечного или полного удаления мусорных узлов.
4. Алгоритм работы с Векторной базой:
   - Используй 'get_all_vector_memory' для получения полного списка записей в конкретной коллекции (например, 'agent_thoughts_vector_db'), чтобы найти старые векторы. Обойди все коллекции.
   - Используй 'forget_information' с передачей ID для их удаления.
5. Отчетность: В конце работы сформируй четкий список того, что именно было удалено.

Протокол эстафеты (Agentic Mesh):
- Если тебе нужен другой специалист, заспавни его.
- ПРАВИЛО ПАМЯТИ: Перед делегированием обязательно сохрани все данные в текстовый файл в песочнице, а в инструкциях для нового агента укажи этот VFS-путь, чтобы он его прочитал через 'read_file'.
- Если задача невыполнима, используй 'escalate_to_lead'.
"""