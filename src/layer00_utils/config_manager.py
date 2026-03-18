import yaml
from pathlib import Path
from pydantic import BaseModel
from typing import List, Tuple
from src.layer00_utils.env_manager import AGENT_NAME

class IdentityConfig(BaseModel):
    agent_name: str
    admin_name: str
    admin_tg_id: int
    
class LimitsConfig(BaseModel):
    max_file_read_chars: int
    max_web_read_chars: int
    action_details_max_chars: int
    image_max_size: Tuple[int, int]

class ContextDepthItem(BaseModel):
    thoughts_limit: int
    actions_limit: int
    dialogue_limit: int

class ContextDepthConfig(BaseModel):
    event_driven: ContextDepthItem
    proactivity: ContextDepthItem
    thoughts: ContextDepthItem

class LLMConfig(BaseModel):
    model_config = {"protected_namespaces": ()} # Это заставит Pydantic заткнуться про "model_"
    
    model_name: str
    is_main_model_multimodal: bool
    multimodal_model: str
    available_models: List[str]
    temperature: float
    max_react_steps: int
    limits: LimitsConfig
    context_depth: ContextDepthConfig

class RhythmsConfig(BaseModel):
    proactivity_interval_sec: int
    thoughts_interval_sec: int
    telemetry_poll_sec: int
    weather_poll_sec: int
    min_proactivity_cooldown_sec: int
    reduction_medium_sec: int
    reduction_low_sec: int

class TelegramConfig(BaseModel):
    agent_session_name: str
    ignored_users: List[int]

class EmbeddingModelConfig(BaseModel):
    name: str
    local_path: str

class GarbageCollectorConfig(BaseModel):
    temp_files_ttl_hours: int

class SwarmConfig(BaseModel):
    sybagent_model: str
    max_sybagent_steps: int
    report_max_chars: int

class GraphRagConfig(BaseModel):
    max_direct_edges: int
    max_indirect_edges: int

class VectorRagConfig(BaseModel):
    max_results: int

class MentalStateConfig(BaseModel):
    active_focus_ttl_hours: int

class MemoryConfig(BaseModel):
    mental_state: MentalStateConfig

    chroma_db_path: str
    similarity_threshold: float
    embedding_model: EmbeddingModelConfig
    vector_rag: VectorRagConfig

    kuzu_db_path: str
    graph_rag: GraphRagConfig

    workspace_garbage_collector: GarbageCollectorConfig

class SystemFlags(BaseModel):
    enable_proactivity: bool
    enable_thoughts: bool
    dump_llm_context: bool
    headless_mode: bool

class SystemConfig(BaseModel):
    weather_city: str
    logging_level: str
    log_retention_days: int
    flags: SystemFlags

# Главный класс, объединяющий всё
class AppConfig(BaseModel):
    identity: IdentityConfig
    llm: LLMConfig
    swarm: SwarmConfig
    rhythms: RhythmsConfig
    telegram: TelegramConfig
    memory: MemoryConfig
    system: SystemConfig

def load_config() -> AppConfig:
    current_dir = Path(__file__).resolve()
    src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
    project_root = src_dir.parent if src_dir else current_dir.parents[2]
    
    # Динамический путь до конфига для каждого отдельного агента
    yaml_path = project_root / "Agents" / AGENT_NAME / "config" / "settings.yaml"

    if not yaml_path.exists():
        raise FileNotFoundError(
            f"\nФайл конфигурации не найден по пути: {yaml_path}\n"
            f"Убедитесь, что профиль агента '{AGENT_NAME}' создан корректно."
        )

    with open(yaml_path, "r", encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)

    return AppConfig(**yaml_data)

config = load_config()