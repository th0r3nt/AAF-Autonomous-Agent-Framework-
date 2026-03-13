import yaml
from pathlib import Path
from pydantic import BaseModel
from typing import List, Tuple

class IdentityConfig(BaseModel):
    agent_name: str
    admin_name: str
    admin_tg_id: int
    
class LimitsConfig(BaseModel):
    max_file_read_chars: int
    max_web_read_chars: int
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
    agent_nickname: str
    ignored_users: List[int]

class EmbeddingModelConfig(BaseModel):
    name: str
    local_path: str

class GarbageCollectorConfig(BaseModel):
    temp_files_ttl_hours: int

class SwarmConfig(BaseModel):
    minion_model: str
    max_minion_steps: int

class MemoryConfig(BaseModel):
    chroma_db_path: str
    kuzu_db_path: str
    similarity_threshold: float
    embedding_model: EmbeddingModelConfig
    workspace_garbage_collector: GarbageCollectorConfig

class VoiceConfig(BaseModel):
    tts_voice: str
    stt_model_path: str
    sample_rate: int

class HardwareConfig(BaseModel):
    weather_city: str
    voice: VoiceConfig

class SystemFlags(BaseModel):
    enable_proactivity: bool
    enable_thoughts: bool
    dump_llm_context: bool
    headless_mode: bool

class SystemConfig(BaseModel):
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
    hardware: HardwareConfig
    system: SystemConfig

def load_config() -> AppConfig:
    current_dir = Path(__file__).resolve().parent
    yaml_path = current_dir / "settings.yaml"

    if not yaml_path.exists():
        raise FileNotFoundError(
            "\nФайл конфигурации не найден!\n"
            "Пожалуйста, скопируйте файл 'config/settings.example.yaml' в 'config/settings.yaml'\n"
            "и настройте его под себя."
        )

    with open(yaml_path, "r", encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)

    return AppConfig(**yaml_data)

config = load_config()