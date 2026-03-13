import kuzu
import asyncio
from src.layer00_utils.logger import system_logger
from config.config_manager import config
from src.layer00_utils.watchdog.watchdog import graph_db_module
from src.layer01_datastate.event_bus.event_bus import event_bus
from src.layer01_datastate.event_bus.events import Events

GRAPH_DB_PATH = config.memory.kuzu_db_path

# Глобальные переменные для базы и соединения
db = None
conn = None

def _init_kuzu_sync():
    """Синхронная инициализация KuzuDB и создание схемы (если её нет)"""
    global db, conn
    # os.makedirs(GRAPH_DB_PATH, exist_ok=True)
    
    db = kuzu.Database(GRAPH_DB_PATH)
    conn = kuzu.Connection(db)
    
    # Проверяем наличие таблиц. Если их нет — создаем.
    # В KuzuDB нет "CREATE TABLE IF NOT EXISTS", поэтому ловим ошибку
    try:
        conn.execute("MATCH (n:Concept) RETURN n LIMIT 1")
    except RuntimeError:
        system_logger.info("[Graph DB] Создание схемы графа (Nodes: Concept, Edges: Link)...")

        # Таблица узлов. Primary Key - имя узла (для удобного поиска)
        conn.execute("CREATE NODE TABLE Concept(name STRING, type STRING, PRIMARY KEY (name))")
        
        # Таблица связей
        conn.execute("CREATE REL TABLE Link(FROM Concept TO Concept, base_type STRING, context STRING, updated_at STRING)")

async def setup_graph_db():
    """Асинхронная обертка для старта базы"""
    try:
        await asyncio.to_thread(_init_kuzu_sync)
        system_logger.info("[Graph DB] База данных успешно подключена.")
        await event_bus.publish(Events.SYSTEM_MODULE_HEARTBEAT, module_name=graph_db_module, status="ON")
        
        # Подписываемся на остановку системы
        event_bus.subscribe(Events.STOP_SYSTEM, stop_graph_db)
    except Exception as e:
        system_logger.error(f"[Graph DB] Ошибка инициализации KuzuDB: {e}")
        await event_bus.publish(Events.SYSTEM_MODULE_ERROR, module_name=graph_db_module, status="ERROR", error_msg=str(e))

async def stop_graph_db(*args, **kwargs):
    """Корректное закрытие графовой БД"""
    global db, conn
    if conn:
        conn.close()
    if db:
        db.close()
    system_logger.info("[Graph DB] База данных сохранена и остановлена.")