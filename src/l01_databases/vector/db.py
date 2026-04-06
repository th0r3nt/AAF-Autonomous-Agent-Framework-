import chromadb
import chromadb.utils.embedding_functions as embedding_functions
import warnings

from src.l01_databases.vector.collections import VectorCollection
from src.l00_utils.managers.logger import system_logger

from src.l01_databases.managers.memory import SemanticReranker

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message=".*Could not reconstruct embedding function.*",
)


class VectorDB:
    def __init__(self, chroma_db_path: str, embedding_model_path: str):
        self.chroma_db_path = chroma_db_path
        self.embedding_model_path = embedding_model_path

        self.embedding_model = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.embedding_model_path, device="cpu"
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
        system_logger.info(f"[Vector DB] База данных инициализирована ({self.chroma_db_path}).")
