import yaml
from pathlib import Path
from huggingface_hub import snapshot_download
from huggingface_hub.utils import disable_progress_bars
from src.cli import ui
import warnings

# Скрываем ворчание HF про отсутствие токена и симлинки
warnings.filterwarnings("ignore", category=UserWarning)

# Отключаем встроенные прогресс-бары HF, чтобы они не ломали UI
disable_progress_bars()

current_dir = Path(__file__).resolve()
project_root = current_dir.parents[2]
settings_path = project_root / "agent" / "config" / "settings.yaml"

def _get_model_names():
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        
        emb_model = config.get("memory", {}).get("embedding_model", "BAAI/bge-m3")
        rerank_model = config.get("memory", {}).get("reranker_model", "corrius/cross-encoder-mmarco-mMiniLMv2-L12-H384-v1")
        return emb_model, rerank_model
    except Exception:
        return "BAAI/bge-m3", "corrius/cross-encoder-mmarco-mMiniLMv2-L12-H384-v1"

def _is_model_valid(model_dir: Path) -> bool:
    if not model_dir.exists():
        return False
    has_config = (model_dir / "config.json").exists()
    has_weights = (model_dir / "model.safetensors").exists() or (model_dir / "pytorch_model.bin").exists()
    return has_config and has_weights

def check_and_download_models():
    emb_model, rerank_model = _get_model_names()
    
    emb_dir = project_root / "src" / "l00_utils" / "local" / "embeddings" / emb_model.replace("/", "_")
    rerank_dir = project_root / "src" / "l00_utils" / "local" / "cross_encoder" / rerank_model.replace("/", "_")

    ui.info("Проверка доступности локальной Embedding модели.")
    # 1. Embedding Model
    if not _is_model_valid(emb_dir):
        ui.info(f"Локальная Embedding модель не найдена. Инициализация загрузки '{emb_model}'.")
        ui.console.print("Идет параллельная загрузка весов. Рекомендуется не закрывать терминал.\n")
        
        emb_dir.mkdir(parents=True, exist_ok=True)
        
        # Качаем с 4 потоками для скорости, возобновляя загрузку при обрыве (resume_download=True)
        try:
            snapshot_download(
                repo_id=emb_model, 
                local_dir=str(emb_dir),
                max_workers=4,
                resume_download=True
            )
            ui.success(f"Модель {emb_model} успешно инициализирована.")
        except Exception as e:
            ui.fatal(f"Критическая ошибка загрузки модели: {e}\nУбедитесь, что у вас есть 3 ГБ свободного места и стабильный интернет.")
    else:
        ui.success(f"Embedding модель '{emb_model}' успешно инициализирована.")

    ui.info("Проверка доступности локальной Reranker модели.")
    # 2. Reranker Model
    if not _is_model_valid(rerank_dir):
        ui.info(f"Локальный Reranker не найден. Инициализация загрузки '{rerank_model}'.")
        rerank_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            snapshot_download(
                repo_id=rerank_model, 
                local_dir=str(rerank_dir),
                max_workers=4,
                resume_download=True
            )
            ui.success(f"Модель {rerank_model} успешно инициализирована.")
        except Exception as e:
            ui.fatal(f"Критическая ошибка загрузки реранкера: {e}")
    else:
        ui.success(f"Reranker модель '{rerank_model}' успешно инициализирована.")