import os
from dotenv import load_dotenv
import sys
import yaml
from pathlib import Path
from pydantic import BaseModel, ValidationError, Field
from src.l00_utils.managers.logger import system_logger

load_dotenv()

# ==========================================
# ВЛОЖЕННЫЕ МОДЕЛИ НАСТРОЕК
# ==========================================


class IdentityConfig(BaseModel):
    agent_name: str


class ContextDepthTickConfig(BaseModel):
    number_of_ticks: int = Field(alias="haha", default=30)


class ContextDepthConfig(BaseModel):
    event_driven: ContextDepthTickConfig
    proactivity: ContextDepthTickConfig
    consolidation: ContextDepthTickConfig


class LLMConfig(BaseModel):
    model_name: str
    available_models: list[str]
    temperature: float
    max_react_ticks: int = Field(alias="max_react_steps", default=15)
    context_depth: ContextDepthConfig
    is_main_model_multimodal: bool
    multimodal_model: str


class RhythmsConfig(BaseModel):
    proactivity_interval_sec: int
    min_proactivity_cooldown_sec: int
    reduction_medium_sec: int
    reduction_low_sec: int
    reduction_background_sec: int = Field(default=30)
    consolidation_interval_sec: int = Field(alias="consolidation", default=3600)


class VectorRAGConfig(BaseModel):
    max_results: int


class GraphRAGConfig(BaseModel):
    max_direct_edges: int
    max_indirect_edges: int


class MemoryConfig(BaseModel):
    similarity_threshold: float
    vector_rag: VectorRAGConfig
    graph_rag: GraphRAGConfig
    reranker_model: str


class SystemFlagsConfig(BaseModel):
    enable_proactivity: bool = True
    enable_consolidation: bool = True
    dump_llm_context: bool = True


class SystemConfig(BaseModel):
    logging_level: str
    flags: SystemFlagsConfig


# ==========================================
# ИНТЕРФЕЙСЫ
# ==========================================


class ApiInterfaceConfig(BaseModel):
    enabled: bool
    agent_account: bool = False


class HabrInterfaceConfig(ApiInterfaceConfig):
    tracked_hubs: list[str] = Field(default_factory=lambda: ["news"])


class ApiInterfaces(BaseModel):
    habr: HabrInterfaceConfig
    github: ApiInterfaceConfig
    reddit: ApiInterfaceConfig


class EmailInterfaceConfig(BaseModel):
    enabled: bool
    agent_account: bool = False


class SystemInterfaceConfig(BaseModel):
    enabled: bool


class TelegramUserbotConfig(BaseModel):
    enabled: bool
    status_tag: str = "none"


class TelegramBotConfig(BaseModel):
    enabled: bool


class TelegramInterfaces(BaseModel):
    userbot: TelegramUserbotConfig
    bot: TelegramBotConfig


class VfsInterfaceConfig(BaseModel):
    enabled: bool
    madness_level: int = 0
    env_access: bool = False
    db_access: bool = False


class WebBrowserConfig(BaseModel):
    enabled: bool
    headless: bool = True
    max_tabs: int = 5


class WebHttpConfig(BaseModel):
    enabled: bool


class WebSearchConfig(BaseModel):
    enabled: bool


class WebInterfaces(BaseModel):
    browser: WebBrowserConfig
    http: WebHttpConfig
    search: WebSearchConfig


class InterfacesConfig(BaseModel):
    api: ApiInterfaces
    email: EmailInterfaceConfig
    system: SystemInterfaceConfig
    telegram: TelegramInterfaces
    vfs: VfsInterfaceConfig
    web: WebInterfaces


# ==========================================
# ГЛАВНАЯ МОДЕЛЬ
# ==========================================


class Settings(BaseModel):
    identity: IdentityConfig
    llm: LLMConfig
    rhythms: RhythmsConfig
    memory: MemoryConfig
    system: SystemConfig
    interfaces: InterfacesConfig


# ==========================================
# ИНИЦИАЛИЗАЦИЯ СИСТЕМНЫХ ПУТЕЙ
# ==========================================

current_dir = Path(__file__).resolve()
src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
project_root = src_dir.parent if src_dir else current_dir.parents[3]

LOGS_DIR = project_root / "logs"

# Конфиги пользователя
CONFIG_PATH = project_root / "agent" / "config" / "settings.yaml"
INTERFACES_PATH = project_root / "agent" / "config" / "interfaces.yaml"

# URL по умолчанию для локального RabbitMQ (guest:guest)
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# Базы данных
GRAPH_DB_PATH = str(project_root / "agent" / "data" / "kuzu_db")
CHROMA_DB_DIR = str(project_root / "agent" / "data" / "chroma_db")

# Дефолтный fallback на SQLite, если в .env не указали базу
SQL_DB_URL = os.getenv("SQL_DB_URL", "sqlite+aiosqlite:///agent/data/agent_db.sqlite")

# Локальные модели
EMBEDDING_MODEL_PATH = str(project_root / "src" / "l00_utils" / "local" / "embedding")


def load_settings() -> Settings:
    if not CONFIG_PATH.exists():
        system_logger.error(
            f"Критическая ошибка: Файл конфигурации не найден по пути: {CONFIG_PATH}"
        )
        sys.exit(1)

    if not INTERFACES_PATH.exists():
        system_logger.error(
            f"Критическая ошибка: Файл интерфейсов не найден по пути: {INTERFACES_PATH}"
        )
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f_settings, open(
        INTERFACES_PATH, "r", encoding="utf-8"
    ) as f_interfaces:
        try:
            yaml_settings = yaml.safe_load(f_settings) or {}
            yaml_interfaces = yaml.safe_load(f_interfaces) or {}

            # Внедряем интерфейсы внутрь основного словаря
            yaml_settings["interfaces"] = yaml_interfaces

            return Settings(**yaml_settings)

        except yaml.YAMLError as e:
            system_logger.error(f"[Config] Ошибка парсинга YAML файла: {e}")
            sys.exit(1)
        except ValidationError as e:
            system_logger.error(
                f"[Config] Ошибка валидации настроек (неверные типы или отсутствуют ключи):\n{e}"
            )
            sys.exit(1)


settings = load_settings()
