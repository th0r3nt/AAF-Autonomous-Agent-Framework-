import os
import chromadb
import chromadb.utils.embedding_functions as embedding_functions

from src.l01_databases.vector.collections import VectorCollection
from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings
from src.l01_databases.managers.memory import SemanticReranker


class VectorDB:
    def __init__(self, chroma_db_path: str, embeddings_base_dir: str):
        self.chroma_db_path = chroma_db_path
        self.embeddings_base_dir = embeddings_base_dir
        self.model_name = settings.memory.embedding_model

        # Просто собираем путь (лаунчер уже всё скачал)
        folder_name = self.model_name.replace("/", "_")
        local_model_path = os.path.join(self.embeddings_base_dir, folder_name)

        system_logger.info(f"[Vector DB] Подключение локальной модели: {local_model_path}")
        self.embedding_model = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=local_model_path, device="cpu"
        )
        self.client = chromadb.PersistentClient(path=self.chroma_db_path)

        # Реранкер для векторной памяти
        self.semantic_reranker = SemanticReranker()

        # Инициализируем коллекции
        knowledge = VectorCollection(db=self, collection_name="knowledge")
        thoughts = VectorCollection(db=self, collection_name="thoughts")

        self.knowledge_collection = knowledge.get_collection()
        self.thoughts_collection = thoughts.get_collection()

    async def stop(self):
        system_logger.info("[Vector DB] База данных остановлена.")

    async def setup(self):
        system_logger.info(
            f"[Vector DB] База данных инициализирована ({self.chroma_db_path})."
        )
