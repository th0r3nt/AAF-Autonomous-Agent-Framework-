from src.l01_databases.graph.db import GraphDB

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings


class GraphCRUD:
    def __init__(self, db: GraphDB):
        self.db = db
        self.conn = self.db.conn

        edge_types = [
            "IS_A",  # Является
            "HAS_PROPERTY",  # Имеет свойство
            "CAUSES",  # Вызывает
            "REQUIRES",  # Зависит от / Требует
            "RELATED_TO",  # Универсальная связь
        ]

        self.valid_relations = (
            edge_types  # Список разрешенных связей, чтобы не создать SQL-инъекцию или ошибку
        )

    # ==========================================
    # 🟢 CREATE
    # ==========================================

    def add_concept(self, concept_id: str, concept_type: str, description: str = ""):
        """
        Добавляет новый узел Concept.
        Используем MERGE: если узел уже есть, он обновит его, если нет - создаст.
        """
        query = """
            MERGE (c:Concept {id: $id})
            ON CREATE SET c.type = $type, c.description = $desc
            ON MATCH SET c.type = $type, c.description = $desc
        """
        self.conn.execute(
            query,
            parameters={"id": concept_id, "type": concept_type, "desc": description},
        )
        result = f"[Graph DB] Концепт добавлен/обновлен: [{concept_id}]"
        system_logger.debug(result)
        return result

    def add_relationship(self, source_id: str, target_id: str, rel_type: str, context: str = ""):
        """
        Создает связь между двумя концептами.
        """
        if rel_type not in self.valid_relations:
            result = f"[Graph DB] Ошибка: Связи '{rel_type}' нет в схеме. Разрешены: {self.valid_relations}"
            system_logger.debug(result)
            return result

        # Имя таблицы (rel_type) подставляем через f-строку, а данные через $
        query = f"""
            MATCH (src:Concept {{id: $source_id}})
            MATCH (tgt:Concept {{id: $target_id}})
            MERGE (src)-[r:{rel_type}]->(tgt)
            ON CREATE SET r.context = $context
            ON MATCH SET r.context = $context
        """
        try:
            self.conn.execute(
                query,
                parameters={
                    "source_id": source_id,
                    "target_id": target_id,
                    "context": context,
                },
            )

            result = f"[Graph DB] Связь создана: [{source_id}] -({rel_type})-> [{target_id}]"
            system_logger.debug(result)
            return result

        except RuntimeError as e:
            result = f"[Graph DB] Ошибка при создании связи: {e}"
            system_logger.error(result)
            return result

    # ==========================================
    # 🔵 READ
    # ==========================================

    def get_concept(self, concept_id: str) -> dict:
        """
        Возвращает информацию о конкретном узле.
        """
        query = "MATCH (c:Concept {id: $id}) RETURN c.type, c.description"
        result = self.conn.execute(query, parameters={"id": concept_id})

        if result.has_next():
            data = result.get_next()
            return {"id": concept_id, "type": data[0], "description": data[1]}
        return None

    def get_neighbors(self, concept_id: str, limit: int = None) -> list:
        """
        Находит все факты, связанные с этим узлом (входящие и исходящие).
        """
        # В Kuzu можно искать сразу по нескольким таблицам связей через |
        rels = "|".join(self.valid_relations)

        if limit is None:
            limit = settings.memory.graph_rag.max_direct_edges

        # Ищем связи, исходящие ОТ нашего узла
        query_out = f"MATCH (c:Concept {{id: $id}})-[r:{rels}]->(tgt:Concept) RETURN label(r), tgt.id, r.context LIMIT {limit}"
        # Ищем связи, входящие В наш узел
        query_in = f"MATCH (src:Concept)-[r:{rels}]->(c:Concept {{id: $id}}) RETURN label(r), src.id, r.context LIMIT {limit}"

        facts = []

        # Собираем исходящие
        res_out = self.conn.execute(query_out, parameters={"id": concept_id})
        while res_out.has_next():
            rel, target, ctx = res_out.get_next()
            facts.append(f"{concept_id} --({rel})--> {target} (Context: {ctx})")

        # Собираем входящие
        res_in = self.conn.execute(query_in, parameters={"id": concept_id})
        while res_in.has_next():
            rel, source, ctx = res_in.get_next()
            facts.append(f"{source} --({rel})--> {concept_id} (Context: {ctx})")

        return facts

    # ==========================================
    # 🟡 UPDATE
    # ==========================================

    def update_concept_description(self, concept_id: str, new_description: str) -> str:
        """
        Обновляет только описание.
        """
        query = """
            MATCH (c:Concept {id: $id})
            SET c.description = $desc
        """
        self.conn.execute(query, parameters={"id": concept_id, "desc": new_description})

        result = f"[Graph DB] Описание обновлено для [{concept_id}]"
        system_logger.debug(result)
        return result

    # ==========================================
    # 🔴 DELETE
    # ==========================================

    def delete_concept(self, concept_id: str) -> str:
        """
        Полное удаление узла и связанных с ним связей.
        """
        rels = "|".join(self.valid_relations)

        # 1. Удаляем все связи (и входящие, и исходящие)
        # Синтаксис (c)-[r]-(any) без стрелочек означает связи в любом направлении
        query_del_edges = f"""
            MATCH (c:Concept {{id: $id}})-[r:{rels}]-(any:Concept)
            DELETE r
        """
        self.conn.execute(query_del_edges, parameters={"id": concept_id})

        # 2. Удаляем сам узел
        query_del_node = "MATCH (c:Concept {id: $id}) DELETE c"
        self.conn.execute(query_del_node, parameters={"id": concept_id})

        result = f"[Graph DB] Концепт [{concept_id}] и все его связи удалены."
        system_logger.debug(result)
        return result