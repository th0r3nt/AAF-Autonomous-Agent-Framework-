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
async def manage_graph(source: str, target: str, base_type: str, context: str = "[Нет контекста]", confidence_score: float = 1.0, bond_weight: float = 1.0) -> str:
    def _sync_manage():
        src_resolved = _resolve_entity(source)
        tgt_resolved = _resolve_entity(target)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        query = """
        MERGE (s:Concept {name: $src_name})
        ON CREATE SET s.type = 'Unknown'
        MERGE (t:Concept {name: $tgt_name})
        ON CREATE SET t.type = 'Unknown'
        MERGE (s)-[r:Link {base_type: $rel_type}]->(t)
        ON CREATE SET r.context = $ctx, r.updated_at = $time, r.confidence_score = $conf, r.bond_weight = $weight
        ON MATCH SET r.context = $ctx, r.updated_at = $time, r.confidence_score = $conf, r.bond_weight = $weight
        """
        
        parameters = {
            "src_name": src_resolved,
            "tgt_name": tgt_resolved,
            "rel_type": base_type,
            "ctx": context,
            "time": now_str,
            "conf": float(confidence_score),
            "weight": float(bond_weight)
        }
        
        graph_db.conn.execute(query, parameters)
        
        msg = f"Граф обновлен: ({src_resolved}) - [{base_type}] -> ({tgt_resolved}) [Conf: {confidence_score}]"
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
            
        lines = ["--- Содержимое графовой базы данных ---"]
        for _, row in df.iterrows():
            lines.append(f"({row['src']}) - [{row['rel']}] -> ({row['tgt']}) | Контекст: {row['ctx']}")
            
        return "\n".join(lines)

    return await asyncio.to_thread(_sync_get)

@watchdog_decorator(graph_db_module)
async def delete_from_graph(source_node: str, target_node: str = None) -> str:
    """
    Удаляет узел (и все его связи) ИЛИ конкретную связь между двумя узлами.
    Использует эвристику (threshold=95) для прощения опечаток регистра.
    """
    def _sync_delete():
        if not graph_db.conn:
            return "Графовая база данных недоступна."
            
        # Используем _resolve_entity с высоким порогом (95%), 
        # чтобы прощать мелкие опечатки (например "openclaw" вместо "OpenClaw"),
        # но не удалить случайно "OpenAI" вместо "OpenMOSS".
        resolved_source = _resolve_entity(source_node.strip(), threshold=95)
        
        # Проверяем, существует ли узел
        res = graph_db.conn.execute("MATCH (n:Concept {name: $name}) RETURN n.name", {"name": resolved_source}).get_as_df()
        if res.empty:
            return f"Отмена удаления: Узел '{source_node}' (или похожий на него) не найден в графе. Используйте инструмент explore_graph или get_full_graph, чтобы узнать точное имя узла."
            
        # Сценарий 1: Удаляем конкретную связь между двумя узлами
        if target_node:
            resolved_target = _resolve_entity(target_node.strip(), threshold=95)
            
            # Проверяем существование второго узла
            res_tgt = graph_db.conn.execute("MATCH (n:Concept {name: $name}) RETURN n.name", {"name": resolved_target}).get_as_df()
            if res_tgt.empty:
                return f"Отмена удаления: Целевой узел '{target_node}' не найден в графе."
            
            # Оптимизация KuzuDB: используем ненаправленную связь `-[r:Link]-`
            # Это заменяет два раздельных запроса (туда и обратно) на один элегантный
            q_delete_rel = "MATCH (a:Concept {name: $src})-[r:Link]-(b:Concept {name: $tgt}) DELETE r"
            graph_db.conn.execute(q_delete_rel, {"src": resolved_source, "tgt": resolved_target})
            
            system_logger.info(f"[Graph DB] Удалена связь между '{resolved_source}' и '{resolved_target}'.")
            return f"Связи между '{resolved_source}' и '{resolved_target}' успешно очищены."
            
        # Сценарий 2: Удаляем узел полностью
        else:
            # Оптимизация KuzuDB: удаляем все связи узла (входящие и исходящие) одним ненаправленным запросом
            graph_db.conn.execute("MATCH (n:Concept {name: $name})-[r:Link]-() DELETE r", {"name": resolved_source})
            
            # И только теперь, когда связей больше нет, KuzuDB разрешит безопасно удалить сам узел
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
    Собирает глобальный пул, сортирует по Релевантности и Свежести, 
    и только потом обрезает до лимитов из конфига.
    """
    def _sync_get():
        if not graph_db.conn or not node_names:
            return "Нет релевантных связей в графе.",[]
        
        direct_pool = {}   # Используем dict для дедупликации по сигнатуре
        indirect_pool = {}
        associated_nodes = set()
        
        limit_direct = config.memory.graph_rag.max_direct_edges
        limit_indirect = config.memory.graph_rag.max_indirect_edges
        
        for name in node_names:
            resolved_name = _resolve_entity(name, threshold=85)
            
            # --- DEPTH 1 --- 
            # Ставим с запасом LIMIT на один якорь, чтобы собрать широкий пул
            query_d1 = """
            MATCH (a:Concept {name: $name})-[r:Link]-(b:Concept)
            RETURN a.name AS src, r.base_type AS rel, b.name AS tgt, r.context AS ctx, 
                   r.confidence_score AS conf, r.bond_weight AS weight, r.updated_at as time
            ORDER BY (r.confidence_score * r.bond_weight) DESC, r.updated_at DESC
            LIMIT 40
            """
            df_d1 = graph_db.conn.execute(query_d1, {"name": resolved_name}).get_as_df()
            
            if not df_d1.empty:
                for _, row in df_d1.iterrows():
                    sig = f"{row['src']}-{row['rel']}-{row['tgt']}"
                    score = round(row['conf'] * row['weight'], 2)
                    # Если такой связи еще нет, или мы нашли более свежую её версию
                    if sig not in direct_pool or direct_pool[sig]['time'] < row['time']:
                        direct_pool[sig] = {
                            "text": f"- ({row['src']}) - [{row['rel']}] - ({row['tgt']}) | Контекст: {row['ctx']} [Relevance: {score}]",
                            "score": score,
                            "time": row['time'],
                            "tgt": row['tgt']
                        }

            # --- DEPTH 2 ---
            query_d2 = """
            MATCH (a:Concept {name: $name})-[r1:Link]-(b:Concept)-[r2:Link]-(c:Concept)
            WHERE a.name <> c.name 
              AND NOT b.name IN $supernodes
              AND NOT c.name IN $supernodes
            RETURN b.name AS bridge, r2.base_type AS rel, c.name AS target, r2.context AS ctx, 
                   r2.confidence_score AS conf, r2.bond_weight AS weight, r2.updated_at as time
            ORDER BY (r2.confidence_score * r2.bond_weight) DESC, r2.updated_at DESC
            LIMIT 30
            """
            df_d2 = graph_db.conn.execute(query_d2, {"name": resolved_name, "supernodes": supernodes_list}).get_as_df()
            
            if not df_d2.empty:
                for _, row in df_d2.iterrows():
                    sig = f"{row['bridge']}-{row['rel']}-{row['target']}"
                    score = round(row['conf'] * row['weight'], 2)
                    if sig not in indirect_pool or indirect_pool[sig]['time'] < row['time']:
                        indirect_pool[sig] = {
                            "text": f"- ({row['bridge']}) - [{row['rel']}] - ({row['target']}) | Контекст: {row['ctx']} [Relevance: {score}]",
                            "score": score,
                            "time": row['time'],
                            "tgt": row['target']
                        }

        # ГЛОБАЛЬНАЯ СОРТИРОВКА И ОБРЕЗКА
        # Сортируем списки словарей по кортежу (score, time) по убыванию
        sorted_direct = sorted(direct_pool.values(), key=lambda x: (x['score'], x['time']), reverse=True)[:limit_direct]
        sorted_indirect = sorted(indirect_pool.values(), key=lambda x: (x['score'], x['time']), reverse=True)[:limit_indirect]

        # Извлекаем тексты и узлы для вектора
        final_direct = []
        final_indirect =[]
        
        for item in sorted_direct:
            final_direct.append(item['text'])
            associated_nodes.add(item['tgt'])
            
        for item in sorted_indirect:
            final_indirect.append(item['text'])
            associated_nodes.add(item['tgt'])

        context_blocks =[]
        if final_direct:
            context_blocks.append("[Прямые связи]:\n" + "\n".join(final_direct))
        if final_indirect:
            context_blocks.append("[Косвенные связи]:\n" + "\n".join(final_indirect))
            
        final_text = "\n\n".join(context_blocks) if context_blocks else "Нет релевантных связей в графе."
        
        return final_text, list(associated_nodes)

    return await asyncio.to_thread(_sync_get)