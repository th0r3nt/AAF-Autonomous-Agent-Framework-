import kuzu
import asyncio
from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.event_bus import EventBus

# Список связей (FROM Concept TO Concept)
edge_types = [
    "IS_A",  # Является
    "HAS_PROPERTY",  # Имеет свойство
    "CAUSES",  # Вызывает
    "REQUIRES",  # Зависит от / Требует
    "RELATED_TO",  # Универсальная связь
]


class GraphDB:
    def __init__(self, event_bus: EventBus, db_path: str):
        self.event_bus = event_bus
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)

    def _init_kuzu(self):
        """Создает структуру графа, если её еще нет"""
        # Создаем универсальный узел Concept
        try:
            self.conn.execute(
                """
                CREATE NODE TABLE Concept (
                    id STRING, 
                    type STRING, 
                    description STRING, 
                    PRIMARY KEY (id)
                )
            """
            )
        except RuntimeError as e:
            if "already exists" in str(e).lower():
                pass
            else:
                system_logger.error(e)

        # Создаем связи от Concept до Concept
        for edge in edge_types:
            try:
                # Cвойство 'context' - чтобы LLM могла пояснить связь текстом
                self.conn.execute(
                    f"""
                    CREATE REL TABLE {edge} (
                        FROM Concept TO Concept,
                        context STRING
                    )
                """
                )
                system_logger.debug(f"[Graph DB] Связь {edge} создана.")
            except RuntimeError as e:
                if "already exists" in str(e).lower():
                    pass  # Просто игнорируем, если таблица связи уже есть
                else:
                    raise system_logger.error(e)

    async def setup(self):
        """Асинхронная обертка для старта базы."""
        try:
            await asyncio.to_thread(self._init_kuzu)
            system_logger.info("[Graph DB] Графовая база данных успешно подключена.")

        except Exception as e:
            system_logger.error(f"[Graph DB] Ошибка инициализации KuzuDB: {e}")

    async def stop(self):
        """Корректное закрытие базы."""
        if self.conn:
            self.conn.close()
        if self.db:
            self.db.close()
        system_logger.info("[Graph DB] База данных сохранена и остановлена.")
