import asyncio
from typing import List

# l00_utils
from src.l00_utils.event.broker.consumer import EventConsumer
from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.event.registry import Events
from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import (
    GRAPH_DB_PATH,
    SQL_DB_URL,
    CHROMA_DB_DIR,
    EMBEDDINGS_BASE_DIR,
    CONFIG_PATH,
    INTERFACES_PATH,
    RABBITMQ_URL,
)
from src.l00_utils.event.broker.connection import RabbitMQConnection
from src.l00_utils.event.broker.publisher import EventPublisher
from src.l00_utils.event.broker.topology import RabbitMQTopology

# l01_databases
from src.l01_databases.graph.db import GraphDB
from src.l01_databases.sql.db import SQLDB
from src.l01_databases.vector.db import VectorDB

# Фасады памяти
from src.l01_databases.managers.memory import SemanticReranker, VectorGraphMemory
from src.l01_databases.managers.sql_db import SQLManager
from src.l01_databases.managers.graph_db import GraphManager
from src.l01_databases.managers.vector_db import VectorManager

# l02_state
from src.l02_state.system.yaml.settings import SettingsState
from src.l02_state.system.yaml.interfaces import InterfacesState
from src.l02_state.system.agency import AgencyState
from src.l02_state.manager import GlobalState

# l03_interfaces
from src.l03_interfaces.initializer import InterfaceInitializer

# l04_agency
from src.l04_agency.llm.api_keys.rotator import APIKeyRotator
from src.l04_agency.llm.client import LLMClient
from src.l04_agency.skills.router import SkillRouter
from src.l04_agency.react.loop import ReActLoop
from src.l04_agency.main_agent.context.builder import ContextBuilder
from src.l04_agency.main_agent.prompt.builder import PromptBuilder
from src.l04_agency.skills.registry import ToolRegistry
from src.l04_agency.main_agent.cycles.orchestrator import Orchestrator
from src.l04_agency.main_agent.cycles.heartbeat import AgentHeartbeat
from src.l04_agency.main_agent.dispatcher import EventDispatcher


class AgentSystem:
    """
    Главный класс системы.
    Отвечает за инициализацию всех компонентов и управление жизненным циклом.
    """

    def __init__(self, event_bus: EventBus, api_url: str, all_keys: List[str]):
        self.event_bus = event_bus
        self.active_clients = []  # Список для хранения активных клиентов интерфейсов
        self.api_url = api_url
        self.all_keys = all_keys

    # ====================================================================
    # l00_utils
    # ====================================================================

    async def setup_utils(self) -> None:
        self.rabbitmq_conn = RabbitMQConnection(RABBITMQ_URL)
        await self.rabbitmq_conn.connect()

        channel = await self.rabbitmq_conn.get_channel()
        topology = RabbitMQTopology(channel=channel)
        await topology.setup()

        publisher = EventPublisher(conn=self.rabbitmq_conn)
        self.event_bus.set_publisher(publisher)

    # ====================================================================
    # l01_databases
    # ====================================================================

    async def setup_databases(self) -> None:
        # Базы данных
        self.graph_db = GraphDB(self.event_bus, db_path=GRAPH_DB_PATH)
        self.sql_db = SQLDB(self.event_bus, db_url=SQL_DB_URL)
        self.vector_db = VectorDB(
            chroma_db_path=CHROMA_DB_DIR, embeddings_base_dir=EMBEDDINGS_BASE_DIR
        )

        # Инициализируем
        await self.graph_db.setup()
        await self.sql_db.setup()
        await self.vector_db.setup()

        # Фасады для удобного доступа
        self.graph_manager = GraphManager(self.graph_db)
        self.sql_manager = SQLManager(db=self.sql_db)
        self.vector_manager = VectorManager(
            db=self.vector_db,
            knowledge_collection=self.vector_db.knowledge_collection,
            thoughts_collection=self.vector_db.thoughts_collection,
        )

        # RAG-память
        self.semantic_reranker = SemanticReranker()
        self.vector_graph_memory = VectorGraphMemory(
            vector_collections=[
                self.vector_db.knowledge_collection,
                self.vector_db.thoughts_collection,
            ],
            graph=self.graph_db,
            graph_crud=self.graph_manager.crud,
            reranker=self.semantic_reranker,
        )

    # ====================================================================
    # l02_state
    # ====================================================================

    async def setup_state(self) -> None:
        self.settings_state = SettingsState(config_path=str(CONFIG_PATH))
        self.interfaces_state = InterfacesState(interfaces_path=str(INTERFACES_PATH))
        self.agency_state = AgencyState()

        self.global_state = GlobalState(
            settings_state=self.settings_state,
            interfaces_state=self.interfaces_state,
            agency_state=self.agency_state,
        )
        system_logger.info("[State] Менеджеры состояний инициализированы.")

    # ====================================================================
    # l03_interfaces
    # ====================================================================

    async def setup_interfaces(self) -> None:
        initializer = InterfaceInitializer(
            global_state=self.global_state,
            event_bus=self.event_bus,
            sql_db=self.sql_db,
            active_clients=self.active_clients,
        )
        await initializer.setup_all()

    # ====================================================================
    # l04_agency
    # ====================================================================

    async def setup_agency(self) -> None:
        # LLM Client
        self.api_keys_rotator = APIKeyRotator(self.all_keys)
        self.llm_client = LLMClient(self.api_url, self.api_keys_rotator)
        self.skill_router = SkillRouter()

        # ReAct Loop
        settings_dict = self.global_state.settings_state.get_state()
        self.react_loop = ReActLoop(
            max_react_ticks=settings_dict["llm"]["max_react_ticks"],
            llm_model=settings_dict["llm"]["model_name"],
            openai_client=self.llm_client,
            key_rotator=self.api_keys_rotator,
            skills_router=self.skill_router,
        )

        # Сборщики промпта/контекста
        self.prompt_builder = PromptBuilder()
        self.context_builder = ContextBuilder(
            global_state=self.global_state,
            active_clients=self.active_clients,
            memory_manager=self.vector_graph_memory,
            task_crud=self.sql_manager.tasks,
            event_crud=self.sql_manager.events,
            tick_crud=self.sql_manager.ticks,
            mental_crud=self.sql_manager.mental_states,
            traits_crud=self.sql_manager.traits,
            tools_registry=ToolRegistry,
        )

        # Оркестратор циклов
        self.orchestrator = Orchestrator(
            global_state=self.global_state,
            tick_crud=self.sql_manager.ticks,
            react_loop=self.react_loop,
            prompt_builder=self.prompt_builder,
            context_builder=self.context_builder,
            agency_state=self.agency_state,
        )

        # Heartbeat (пульс агента)
        self.heartbeat = AgentHeartbeat(self.event_bus, self.global_state)
        self.heartbeat.start()

        # Слушатель событий (RabbitMQ Consumer)
        self.dispatcher = EventDispatcher(self.orchestrator, self.global_state, self.heartbeat)

        self.consumer_events = EventConsumer(self.rabbitmq_conn, prefetch_count=1)
        self.consumer_proactivity = EventConsumer(self.rabbitmq_conn, prefetch_count=1)
        self.consumer_system = EventConsumer(self.rabbitmq_conn, prefetch_count=1)

        asyncio.create_task(
            self.consumer_events.start_consuming(
                "q_event_driven", self.dispatcher.handle_rabbitmq_event
            )
        )
        asyncio.create_task(
            self.consumer_proactivity.start_consuming(
                "q_proactivity", self.dispatcher.handle_rabbitmq_event
            )
        )
        asyncio.create_task(
            self.consumer_system.start_consuming(
                "q_system", self.dispatcher.handle_rabbitmq_event
            )
        )

        system_logger.info("[Agency] Мозг агента и консьюмеры RabbitMQ успешно запущены.")

    # ====================================================================
    # START & STOP
    # ====================================================================

    async def startup(self) -> None:
        await self.setup_utils()
        await self.setup_databases()

        zombies_count = await self.sql_manager.ticks.cleanup_zombie_ticks()
        if zombies_count > 0:
            system_logger.warning(f"[System] Очищено тиков после прошлого падения: {zombies_count}")

        await self.setup_state()
        await self.setup_interfaces()
        await self.setup_agency()

        system_logger.info("[System] Ожидание инициализации подключения к серверам.")
        await asyncio.sleep(6)
        await self.event_bus.publish(Events.SYSTEM_CORE_START)

    async def stop(self):
        system_logger.info("[System] Начат процесс остановки AAF.")
        for client in self.active_clients:
            try:
                await client.close()
            except Exception as e:
                system_logger.error(f"[System] Ошибка при закрытии клиента: {e}")

        if hasattr(self, "rabbitmq_conn"):
            await self.rabbitmq_conn.close()
        if hasattr(self, "graph_db"):
            await self.graph_db.stop()
        if hasattr(self, "sql_db"):
            await self.sql_db.stop()
        if hasattr(self, "vector_db"):
            await self.vector_db.stop()

        system_logger.info("[System] AAF полностью отключен.")
