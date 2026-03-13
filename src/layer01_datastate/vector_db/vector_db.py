from pathlib import Path
import chromadb
import chromadb.utils.embedding_functions as embedding_functions
import os
import warnings

from config.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog import vector_db_module
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events

# Подавляем раздражающий варнинг ChromaDB о несовпадении старых Windows-путей внутри Docker
warnings.filterwarnings("ignore", category=UserWarning, message=".*Could not reconstruct embedding function.*")

# Получаем абсолютный корень проекта (чтобы работало и в Windows, и внутри Docker)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

CHROMA_DB_DIRECTORY = str(PROJECT_ROOT / config.memory.chroma_db_path)
LOCAL_EMBEDDING_MODEL_PATH = str(PROJECT_ROOT / config.memory.embedding_model.local_path)

embedding_model = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=LOCAL_EMBEDDING_MODEL_PATH,
    device="cpu"
)

client = chromadb.PersistentClient(path=CHROMA_DB_DIRECTORY) 

COLLECTIONS = {
    "agent_vector_db": client.get_or_create_collection(
        name="agent_vector_db", 
        embedding_function=embedding_model
    ),
    "agent_thoughts_vector_db": client.get_or_create_collection(
        name="agent_thoughts_vector_db", 
        embedding_function=embedding_model
    ),
    "user_vector_db": client.get_or_create_collection(
        name="user_vector_db", 
        embedding_function=embedding_model
    )
}

def _get_col(collection_name: str):
    if collection_name not in COLLECTIONS:
        raise ValueError(f"[Vector DB] Коллекция '{collection_name}' не найдена.")
    return COLLECTIONS[collection_name]

async def stop_vector_db(*args, **kwargs):
    system_logger.info("[Vector DB] База данных сохранена и остановлена.")

async def setup_vector_db():
    system_logger.info("[Vector DB] База данных инициализирована.")
    event_bus.subscribe(Events.STOP_SYSTEM, stop_vector_db)
    await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=vector_db_module, status="ON")