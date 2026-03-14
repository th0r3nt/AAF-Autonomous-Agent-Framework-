import asyncio
from datetime import datetime
from rapidfuzz import process, fuzz
from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog import graph_db_module
from src.layer00_utils.watchdog.watchdog_decorator import watchdog_decorator
from src.layer01_datastate.graph_db import graph_db

supernodes_list = [
    config.identity.agent_name, 
    config.identity.admin_name
]

def _get_all_node_names() -> list:
    if not graph_db.conn:
        return []
    result = graph_db.conn.execute("MATCH (n:Concept) RETURN n.name").get_as_df()
    return result['n.name'].tolist() if not result.empty else []

def _resolve_entity(entity_name: str, threshold: int = 85) -> str:
    """
    Магия Entity Resolution: ищет похожее имя узла в графе.
    Если находит с совпадением > 85%, возвращает существующее имя.
    Если нет — возвращает исходное (будет создан новый узел).
    """
    existing_nodes = _get_all_node_names()
    if not existing_nodes:
        return entity_name

    # Ищем лучшее совпадение
    match = process.extractOne(entity_name, existing_nodes, scorer=fuzz.WRatio)
    
    if match:
        best_name, score, _ = match
        if score >= threshold:
            system_logger.debug(f"[Graph DB] Fuzzy Match: '{entity_name}' -> '{best_name}' (Score: {score:.1f})")
            return best_name
            
    return entity_name

@watchdog_decorator(graph_db_module)
async def manage_graph(source: str, target: str, base_type: str, context: str = "[Нет контекста]") -> str:
    """Связывает два узла. Автоматически создает их, если они не существуют, и обновляет время."""
    def _sync_manage():
        src_resolved = _resolve_entity(source)
        tgt_resolved = _resolve_entity(target)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # MERGE узлов, затем MERGE связи (чтобы можно было обновлять context и время)
        query = """
        MERGE (s:Concept {name: $src_name})
        ON CREATE SET s.type = 'Unknown'
        MERGE (t:Concept {name: $tgt_name})
        ON CREATE SET t.type = 'Unknown'
        MERGE (s)-[r:Link {base_type: $rel_type}]->(t)
        ON CREATE SET r.context = $ctx, r.updated_at = $time
        ON MATCH SET r.context = $ctx, r.updated_at = $time
        """
        
        parameters = {
            "src_name": src_resolved,
            "tgt_name": tgt_resolved,
            "rel_type": base_type,
            "ctx": context,
            "time": now_str
        }
        
        graph_db.conn.execute(query, parameters)
        
        msg = f"Граф обновлен: ({src_resolved}) - [{base_type}] -> ({tgt_resolved})"
        system_logger.info(f"[Graph DB] {msg}")
        return msg

    return await asyncio.to_thread(_sync_manage)

@watchdog_decorator(graph_db_module)
async def get_recent_graph_updates(limit: int = 10) -> str:
    """Возвращает последние изменения в графе"""
    def _sync_recent():
        if not graph_db.conn:
            return "Граф недоступен."
            
        query = """
        MATCH (a:Concept)-[r:Link]->(b:Concept)
        RETURN a.name AS src, r.base_type AS rel, r.context AS ctx, b.name AS tgt, r.updated_at AS time
        ORDER BY r.updated_at DESC
        LIMIT $limit
        """
        df = graph_db.conn.execute(query, {"limit": limit}).get_as_df()
        
        if df.empty:
            return "В графе пока нет связей."
            
        lines = ["Последние изменения в нейронной сети связей:"]
        for _, row in df.iterrows():
            lines.append(f"[{row['time']}] ({row['src']}) - [{row['rel']}] -> ({row['tgt']}) | Контекст: {row['ctx']}")
            
        return "\n".join(lines)

    return await asyncio.to_thread(_sync_recent)

@watchdog_decorator(graph_db_module)
async def explore_graph(query: str, depth: int = 1) -> str:
    """Ищет узел по запросу и возвращает его связи на указанную глубину"""
    def _sync_explore():
        # Резолвим имя, чтобы найти точный узел
        resolved_name = _resolve_entity(query, threshold=70) # Порог ниже для поиска
        
        # Проверяем, существует ли узел вообще
        check_query = "MATCH (n:Concept {name: $name}) RETURN n.name"
        res_df = graph_db.conn.execute(check_query, {"name": resolved_name}).get_as_df()
        if res_df.empty:
            return f"Узел, похожий на '{query}', не найден в графе."

        # Ищем соседей (направление не важно, ищем любые связи)
        # KuzuDB пока не поддерживает вывод путей переменной длины в виде графа так же просто, как Neo4j,
        # поэтому для MVP делаем жесткий запрос на глубину 1 (этого хватает в 95% случаев)
        cypher = """
        MATCH (a:Concept {name: $name})-[r:Link]-(b:Concept)
        RETURN a.name AS source, r.base_type AS rel, r.context AS ctx, b.name AS target
        """
        
        df = graph_db.conn.execute(cypher, {"name": resolved_name}).get_as_df()
        
        if df.empty:
            return f"Узел '{resolved_name}' найден, но у него пока нет связей."

        lines = [f"Граф связей для '{resolved_name}' (Глубина: 1):"]
        for _, row in df.iterrows():
            # Форматируем стрелочки для красивого вывода
            lines.append(f"- ({row['source']}) - [{row['rel']}] - ({row['target']}) | Контекст: {row['ctx']}")

        return "\n".join(lines)

    return await asyncio.to_thread(_sync_explore)

@watchdog_decorator(graph_db_module)
async def get_full_graph() -> str:
    """Возвращает абсолютно все связи из графовой базы данных"""
    def _sync_get():
        if not graph_db.conn:
            return "Графовая база данных недоступна."
            
        query = """
        MATCH (a:Concept)-[r:Link]->(b:Concept)
        RETURN a.name AS src, r.base_type AS rel, b.name AS tgt, r.context AS ctx
        """
        df = graph_db.conn.execute(query).get_as_df()
        
        if df.empty:
            return "Граф пуст. Связей нет."
            
        lines = ["--- ПОЛНЫЙ ДАМП ГРАФОВОЙ БАЗЫ ДАННЫХ ---"]
        for _, row in df.iterrows():
            lines.append(f"({row['src']}) - [{row['rel']}] -> ({row['tgt']}) | Контекст: {row['ctx']}")
            
        return "\n".join(lines)

    return await asyncio.to_thread(_sync_get)

@watchdog_decorator(graph_db_module)
async def delete_from_graph(source_node: str, target_node: str = None) -> str:
    """
    Удаляет узел (и все его связи) ИЛИ конкретную связь между двумя узлами.
    Использует строгое совпадение имен для предотвращения случайного удаления важных узлов.
    """
    def _sync_delete():
        if not graph_db.conn:
            return "Графовая база данных недоступна."
            
        # Убираем _resolve_entity, используем строго точное имя, переданное агентом
        resolved_source = source_node.strip()
        
        # Проверяем, существует ли узел с таким точным именем
        res = graph_db.conn.execute("MATCH (n:Concept {name: $name}) RETURN n.name", {"name": resolved_source}).get_as_df()
        if res.empty:
            return f"Отмена удаления: Узел с точным именем '{resolved_source}' не найден в графе. Используйте инструмент explore_graph или get_full_graph, чтобы узнать точное имя узла перед удалением."
            
        # Сценарий 1: Удаляем конкретную связь между двумя узлами
        if target_node:
            resolved_target = target_node.strip()
            
            # Проверяем существование второго узла
            res_tgt = graph_db.conn.execute("MATCH (n:Concept {name: $name}) RETURN n.name", {"name": resolved_target}).get_as_df()
            if res_tgt.empty:
                return f"Отмена удаления: Целевой узел '{resolved_target}' не найден в графе."
            
            # KuzuDB требует строгого указания направления связи при удалении.
            # Так как мы не знаем, кто на кого ссылается, бьем в обе стороны:
            q_out = "MATCH (a:Concept {name: $src})-[r:Link]->(b:Concept {name: $tgt}) DELETE r"
            q_in = "MATCH (a:Concept {name: $src})<-[r:Link]-(b:Concept {name: $tgt}) DELETE r"
            
            graph_db.conn.execute(q_out, {"src": resolved_source, "tgt": resolved_target})
            graph_db.conn.execute(q_in, {"src": resolved_source, "tgt": resolved_target})
            
            system_logger.info(f"[Graph DB] Удалена связь между '{resolved_source}' и '{resolved_target}'.")
            return f"Связи между '{resolved_source}' и '{resolved_target}' успешно очищены."
            
        # Сценарий 2: Удаляем узел полностью
        else:
            # Сначала удаляем исходящие связи (со стрелочкой ОТ узла)
            graph_db.conn.execute("MATCH (n:Concept {name: $name})-[r:Link]->() DELETE r", {"name": resolved_source})
            
            # Затем удаляем входящие связи (со стрелочкой К узлу)
            graph_db.conn.execute("MATCH ()-[r:Link]->(n:Concept {name: $name}) DELETE r", {"name": resolved_source})
            
            # И только теперь, когда связей нет, KuzuDB разрешит удалить сам узел
            graph_db.conn.execute("MATCH (n:Concept {name: $name}) DELETE n", {"name": resolved_source})
            
            system_logger.info(f"[Graph DB] Полностью удален узел '{resolved_source}' и все его связи.")
            return f"Узел '{resolved_source}' и все его связи успешно стерты из графа."

    return await asyncio.to_thread(_sync_delete)


@watchdog_decorator(graph_db_module)
async def get_associated_node_names(node_names: list, limit_per_node: int = 2) -> list:
    """Служебная функция для Graph-RAG. Возвращает имена соседних узлов"""
    def _sync_get():
        if not graph_db.conn or not node_names:
            return []
        
        associated = set()
        for name in node_names:
            resolved_name = _resolve_entity(name, threshold=85)
            
            # Ищем соседей (в любую сторону)
            query = """
            MATCH (a:Concept {name: $name})-[r:Link]-(b:Concept)
            RETURN b.name AS target
            LIMIT $limit
            """
            df = graph_db.conn.execute(query, {"name": resolved_name, "limit": limit_per_node}).get_as_df()
            
            if not df.empty:
                for _, row in df.iterrows():
                    associated.add(row['target'])
                    
        return list(associated)

    return await asyncio.to_thread(_sync_get)

@watchdog_decorator(graph_db_module)
async def get_all_node_names_async() -> list:
    """Асинхронная обертка для получения всех имен узлов (используется для поиска сущностей в тексте)"""
    return await asyncio.to_thread(_get_all_node_names)

@watchdog_decorator(graph_db_module)
async def get_graph_rag_data(node_names: list) -> tuple[str, list]:
    """
    Выполняет поиск Depth 1 и Depth 2 (Интуиция). 
    Возвращает отформатированный текст для LLM и список имен соседей для Вектора.
    """
    def _sync_get():
        if not graph_db.conn or not node_names:
            return "Нет релевантных связей в графе.", []
        
        direct_lines = []
        indirect_lines = []
        associated_nodes = set()
        
        for name in node_names:
            resolved_name = _resolve_entity(name, threshold=85)
            
            # --- DEPTH 1 (Прямые связи) ---
            query_d1 = """
            MATCH (a:Concept {name: $name})-[r:Link]-(b:Concept)
            RETURN a.name AS src, r.base_type AS rel, b.name AS tgt, r.context AS ctx
            LIMIT 5
            """
            df_d1 = graph_db.conn.execute(query_d1, {"name": resolved_name}).get_as_df()
            
            if not df_d1.empty:
                for _, row in df_d1.iterrows():
                    direct_lines.append(f"- ({row['src']}) - [{row['rel']}] - ({row['tgt']}) | Контекст: {row['ctx']}")
                    associated_nodes.add(row['tgt'])
                    
            # --- DEPTH 2 (Косвенные ассоциации с защитой от Суперузлов) ---
            query_d2 = """
            MATCH (a:Concept {name: $name})-[r1:Link]-(b:Concept)-[r2:Link]-(c:Concept)
            WHERE a.name <> c.name 
              AND NOT b.name IN $supernodes
              AND NOT c.name IN $supernodes
            RETURN a.name AS start, b.name AS bridge, c.name AS target, r2.base_type AS rel, r2.context AS ctx
            LIMIT 3
            """
            df_d2 = graph_db.conn.execute(query_d2, {"name": resolved_name, "supernodes": supernodes_list}).get_as_df()
            
            if not df_d2.empty:
                for _, row in df_d2.iterrows():
                    indirect_lines.append(f"- Через узел ({row['bridge']}) найдена связь: ({row['bridge']}) - [{row['rel']}] - ({row['target']}) | Контекст: {row['ctx']}")
                    associated_nodes.add(row['target'])
        
        # Формируем итоговый текст
        context_blocks = []
        if direct_lines:
            context_blocks.append("[Прямые связи]:\n" + "\n".join(list(set(direct_lines))))
        if indirect_lines:
            context_blocks.append("[Косвенные ассоциации (Интуиция 2-го уровня)]:\n" + "\n".join(list(set(indirect_lines))))
            
        final_text = "\n\n".join(context_blocks) if context_blocks else "Нет релевантных связей в графе."
        
        return final_text, list(associated_nodes)

    return await asyncio.to_thread(_sync_get)