import re
import os
import math
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

from sentence_transformers import CrossEncoder

from src.l03_interfaces.type.base import BaseInstrument
from src.l00_utils.managers.config import settings
from src.l00_utils.managers.logger import system_logger
from src.l01_databases.vector.collections import VectorCollection
from src.l01_databases.graph.db import GraphDB
from src.l01_databases.graph.management.crud import GraphCRUD

from src.l04_agency.skills.registry import skill


class SemanticReranker:
    """Отвечает за загрузку реранкер модели и семантическую оценку текстов."""

    def __init__(self):
        self.model_name = settings.memory.reranker_model
        self.base_path = self._get_base_path()
        self.model = self._load_model()

    def _get_base_path(self) -> Path:
        current_dir = Path(__file__).resolve()
        src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
        if src_dir:
            return src_dir / "l00_utils" / "local" / "cross_encoder"
        return current_dir.parents[3] / "src" / "l00_utils" / "local" / "cross_encoder"

    def _load_model(self) -> CrossEncoder:
        try:
            folder_name = self.model_name.replace("/", "_")
            local_path = os.path.join(self.base_path, folder_name)
            system_logger.info(f"[Reranker] Инициализация локальной модели: {local_path}")

            return CrossEncoder(local_path, max_length=512)
        except Exception as e:
            system_logger.error(f"[Reranker] Ошибка инициализации: {e}")
            return None

    def get_score(self, query: str, text: str) -> float:
        """Возвращает оценку релевантности от 0.0 до 1.0"""
        if not self.model:
            return 0.5  # Фолбэк, если модель не загрузилась

        raw_score = self.model.predict([query, text])
        return 1 / (1 + math.exp(-raw_score))  # Сигмоида


class VectorGraphMemory(BaseInstrument):
    def __init__(
        self,
        vector_collections: List[VectorCollection],
        graph: GraphDB,
        graph_crud: GraphCRUD,
        reranker: "SemanticReranker",  # Инжектим зависимость
    ):
        super().__init__()  # Обязательно дергаем init родителя

        self.vector_collections = vector_collections
        self.graph = graph
        self.graph_crud = graph_crud
        self.reranker = reranker  # Класс памяти больше не создает модель сам!

    def sync_recall_memory(self, query: str) -> str:
        """Синхронно ищет переданную информацию в базах данных."""
        system_logger.info(f"[Vector-Graph-RAG] Старт поиска для запроса: '{query}'")

        anchors = self._extract_anchors(query)

        # Передаем лимиты из настроек
        v_limit = settings.memory.vector_rag.max_results

        vector_candidates = self._find_vector_entry_points(query, top_k=v_limit)
        graph_start_nodes = self._find_graph_entry_points(anchors)

        graph_candidates = self._expand_graph(graph_start_nodes)
        enrichment_candidates = self._vector_enrichment(graph_start_nodes)

        all_candidates = vector_candidates + graph_candidates + enrichment_candidates

        # Финальный срез тоже делаем динамическим (чтобы реранкер не пропустил лишнего)
        # Сумма лимитов Вектора и прямых графов - отличный размер для итогового контекста
        final_top_n = (
            settings.memory.vector_rag.max_results + settings.memory.graph_rag.max_direct_edges
        )

        return self._rerank_and_filter(query, all_candidates, top_n=final_top_n)

    @skill()
    async def recall_memory(self, query: str) -> str:
        """Ищет переданную информацию в базах данных."""
        return await asyncio.to_thread(self.sync_recall_memory, query)

    # ==========================================
    # ВНУТРЕННИЕ МЕТОДЫ (для recall_memory)
    # ==========================================

    def _extract_anchors(self, query: str) -> List[str]:
        """
        Вытаскивает якоря/сущности из запроса.
        """
        # Убираем пунктуацию и переводим в нижний регистр
        words = re.findall(r"\b\w+\b", query.lower())

        # Базовый список стоп-слов, чтобы не искать в графе союзы и местоимения
        stop_words = {
            "что",
            "как",
            "где",
            "когда",
            "зачем",
            "почему",
            "это",
            "для",
            "на",
            "по",
            "со",
            "из",
            "там",
            "тут",
            "мне",
            "тебе",
            "ему",
            "нам",
        }

        # Оставляем только слова длиннее 2 символов, не являющиеся стоп-словами
        anchors = [w for w in words if w not in stop_words and len(w) > 2]
        return list(set(anchors))  # Убираем дубликаты

    def _find_vector_entry_points(
        self, search_text: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Векторный поиск (сырые данные без форматирования).
        """
        if top_k is None:
            top_k = settings.memory.vector_rag.max_results

        candidates = []
        for v_col in self.vector_collections:
            try:
                if v_col.collection.count() == 0:
                    continue

                res = v_col.collection.query(query_texts=[search_text], n_results=top_k)

                if res and "documents" in res and res["documents"]:
                    for i in range(len(res["documents"][0])):
                        candidates.append(
                            {
                                "text": res["documents"][0][i],
                                "date": res["metadatas"][0][i].get("creation_date", ""),
                                "distance": res["distances"][0][
                                    i
                                ],  # В ChromaDB дистанция (меньше - лучше)
                                "source": f"vector_{v_col.collection.name}",
                            }
                        )
            except Exception as e:
                system_logger.error(
                    f"[Vector-Graph-RAG] Ошибка векторного поиска в {v_col.collection.name}: {e}"
                )

        return candidates

    def _find_graph_entry_points(self, anchors: List[str]) -> List[str]:
        """Поиск узлов графа, совпадающих с якорями."""
        nodes = []
        for anchor in anchors:
            # Ищем частичное совпадение якоря с ID концепта (игнорируя регистр)
            query = "MATCH (c:Concept) WHERE lower(c.id) CONTAINS lower($anchor) RETURN c.id LIMIT 3"
            try:
                res = self.graph.conn.execute(query, parameters={"anchor": anchor})
                while res.has_next():
                    nodes.append(res.get_next()[0])
            except Exception as e:
                system_logger.debug(
                    f"[Vector-Graph-RAG] Ошибка поиска якоря '{anchor}' в графе: {e}"
                )

        # Возвращаем уникальные ID узлов
        return list(set(nodes))

    def _expand_graph(self, start_nodes: List[str]) -> List[Dict[str, Any]]:
        """Графовая экспансия (1-й и 2-й порядок)."""
        expanded_facts = []
        if not start_nodes:
            return expanded_facts

        # Берем лимиты из настроек
        limit_direct = settings.memory.graph_rag.max_direct_edges
        limit_indirect = settings.memory.graph_rag.max_indirect_edges

        rels = "|".join(self.graph_crud.valid_relations)
        current_date = datetime.now().strftime("%d.%m.%Y %H:%M")

        for node in start_nodes:
            # 1-й порядок (Прямые соседи). Обрезаем список по лимиту
            facts_1st = self.graph_crud.get_neighbors(node, limit=limit_direct)
            for fact in facts_1st:
                expanded_facts.append(
                    {
                        "text": f"[Факт из Графа]: {fact}",
                        "date": current_date,
                        "distance": 0.2,
                        "source": "graph_1st_degree",
                    }
                )

            # 2-й порядок (Соседи соседей). Передаем лимит прямо в Kuzu запрос
            query_2nd = f"""
                MATCH (start:Concept {{id: $id}})-[r1:{rels}]-(mid:Concept)-[r2:{rels}]-(end:Concept)
                WHERE end.id <> $id
                RETURN mid.id, label(r2), end.id, r2.context
                LIMIT {limit_indirect}
            """

            try:
                res = self.graph.conn.execute(query_2nd, parameters={"id": node})
                while res.has_next():
                    row = res.get_next()
                    # row:[mid.id, label(r2), end.id, r2.context]
                    fact_str = f"{row[0]} --({row[1]})--> {row[2]} (Контекст: {row[3]})"
                    expanded_facts.append(
                        {
                            "text": f"[Факт из Графа 2-го порядка]: {fact_str}",
                            "date": current_date,
                            "distance": 0.4,
                            "source": "graph_2nd_degree",
                        }
                    )
            except Exception as e:
                system_logger.debug(f"[Vector-Graph-RAG] Ошибка экспансии 2-го порядка: {e}")

        return expanded_facts

    def _vector_enrichment(self, graph_nodes: List[str]) -> List[Dict[str, Any]]:
        """Векторное обогащение на основе найденных узлов графа."""
        if not graph_nodes:
            return []

        # Формируем обогащенный запрос из имен узлов
        enrichment_query = " ".join(graph_nodes)
        system_logger.debug(
            f"[Vector-Graph-RAG] Векторное обогащение по узлам: {enrichment_query}"
        )

        # Делаем неглубокий поиск (top 2), чтобы не раздувать контекст
        return self._find_vector_entry_points(enrichment_query, top_k=2)

    def _rerank_and_filter(
        self, query: str, candidates: List[Dict[str, Any]], top_n: int = 10
    ) -> str:
        """Реранкинг с делегированием оценки внешнему реранкеру."""
        if not candidates:
            return "Релевантная информация в памяти не найдена."

        unique_cands = {c["text"]: c for c in candidates}
        cands_list = list(unique_cands.values())

        for c in cands_list:
            text = c["text"]
            decay_factor = self._calculate_time_decay(c.get("date", ""))

            # Делегируем семантическую логику внедренному классу
            semantic_score = self.reranker.get_score(query, text)

            # Если модель вернула 0.5 как фолбэк, мы можем учесть distance из БД
            if semantic_score == 0.5 and "distance" in c:
                semantic_score = max(0.0, 1.0 - c["distance"])

            c["final_score"] = semantic_score * decay_factor

        cands_list.sort(key=lambda x: x["final_score"], reverse=True)
        top_cands = cands_list[:top_n]

        formatted_result = []
        for c in top_cands:
            source = c["source"].upper()
            date = c.get("date", "Дата неизвестна")
            formatted_result.append(f"[{source} | {date}] {c['text']}")

        return "\n".join(formatted_result)

    def _calculate_time_decay(self, date_str: str) -> float:
        """Вычисляет коэффициент актуальности записи (1.0 - свежая, 0.5 - очень старая)."""
        if not date_str:
            return 1.0

        try:
            record_date = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
            days_passed = (datetime.now() - record_date).days

            if days_passed <= 0:
                return 1.0

            # Экспоненциальное затухание (период полураспада ~30 дней)
            decay = math.exp(-0.023 * days_passed)

            # Ограничиваем "дно", чтобы даже старые, но идеально подходящие факты не удалялись полностью
            return max(0.5, decay)
        except Exception:
            return 1.0
