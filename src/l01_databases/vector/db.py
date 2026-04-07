import os
import warnings
from huggingface_hub import snapshot_download
import chromadb
import chromadb.utils.embedding_functions as embedding_functions

from src.l01_databases.vector.collections import VectorCollection
from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings
from src.l01_databases.managers.memory import SemanticReranker

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message=".*Could not reconstruct embedding function.*",
)

class VectorDB:
    def __init__(self, chroma_db_path: str, embeddings_base_dir: str):
        self.chroma_db_path = chroma_db_path
        self.embeddings_base_dir = embeddings_base_dir
        self.model_name = settings.memory.embedding_model

        # Проверяем и скачиваем модель
        local_model_path = self._ensure_model_downloaded()

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

    def _ensure_model_downloaded(self) -> str:
        """Проверяет наличие локальной модели. Если её нет - скачивает из HF."""
        try:
            # Заменяем слэши на подчеркивания, чтобы избежать вложенных папок (напр. BAAI_bge-m3)
            folder_name = self.model_name.replace("/", "_")
            local_path = os.path.join(self.embeddings_base_dir, folder_name)

            # Проверяем, существует ли папка и не пустая ли она
            if not os.path.exists(local_path) or not os.listdir(local_path):
                system_logger.info(f"[Vector DB] Модель не найдена. Инициализация установки '{self.model_name}' в {local_path}.")
                os.makedirs(local_path, exist_ok=True)
                
                snapshot_download(
                    repo_id=self.model_name,
                    local_dir=local_path,
                    local_dir_use_symlinks=False,
                )
                system_logger.info("[Vector DB] Модель эмбеддингов успешно скачана.")
            else:
                system_logger.debug(f"[Vector DB] Локальная модель эмбеддингов найдена: {local_path}")

            return local_path

        except Exception as e:
            system_logger.error(f"[Vector DB] Ошибка загрузки модели {self.model_name}: {e}")
            # Фолбэк: отдаем просто имя, SentenceTransformer попытается скачать в свой кэш
            return self.model_name

    async def stop(self):
        system_logger.info("[Vector DB] База данных остановлена.")

    async def setup(self):
        system_logger.info(f"[Vector DB] База данных инициализирована ({self.chroma_db_path}).")