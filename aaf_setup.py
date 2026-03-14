import sys
import subprocess
import os
import shutil
import asyncio
from pathlib import Path
import warnings

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TQDM_DISABLE"] = "1"
warnings.filterwarnings("ignore")

G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
C = "\033[96m"
W = "\033[0m"

DEFAULT_SETTINGS_YAML = """
identity:
  agent_name: "AgentName"
  admin_name: "AdminName"
  admin_tg_id: 123456789 # Замените на свой ID (@getmyid_bot)

llm:
  model_name: "gemini-flash-latest"
  vision_model: "gemini-3.1-flash-lite-preview"
  available_models:
    - "gemini-3.1-pro-high"
    - "gemini-flash-latest"
    - "gemini-3.1-flash-lite-preview"
    - "gpt-5.4"
    - "claude-opus-4-6"
  temperature: 0.7
  max_react_steps: 15

  limits:
    max_file_read_chars: 80000
    max_web_read_chars: 15000
    image_max_size: [1500, 1500]

  context_depth:
      event_driven:
        thoughts_limit: 5 # Количество записей интроспекции, которые попадают в контекст
        actions_limit: 10 # Лог последних действий, n последних
        dialogue_limit: 30 # Записи глобального диалога
      proactivity:
        thoughts_limit: 5
        actions_limit: 20
        dialogue_limit: 30
      thoughts:
        thoughts_limit: 10
        actions_limit: 20
        dialogue_limit: 40

swarm:
  sybagent_model: "gemini-3.1-flash-lite-preview"
  max_sybagent_steps: 10

rhythms:
  proactivity_interval_sec: 900
  thoughts_interval_sec: 1800
  min_proactivity_cooldown_sec: 600 # Увеличили до 10 минут
  reduction_medium_sec: 120
  reduction_low_sec: 60
  telemetry_poll_sec: 60
  weather_poll_sec: 1800

memory:
  chroma_db_path: "workspace/_data/chroma_db/"
  similarity_threshold: 0.43
  kuzu_db_path: "workspace/_data/kuzu_db"
  embedding_model: 
    name: "BAAI/bge-m3"
    local_path: "src/layer00_utils/local_models/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181"
  workspace_garbage_collector:
    temp_files_ttl_hours: 48

telegram:
  agent_session_name: "agent_session"
  agent_nickname: "username"
  ignored_users: [708513, 777000]

hardware:
  weather_city: "Moscow"
  voice:
    tts_voice: "ru-RU-SvetlanaNeural"
    stt_model_path: "src/layer00_utils/vosk_model/vosk-model-small-ru-0.22"
    sample_rate: 16000

system:
  logging_level: "INFO"
  log_retention_days: 14
  flags:
    enable_proactivity: true            
    enable_thoughts: true               
    dump_llm_context: true
    headless_mode: true  
"""

def install_dependencies():
    print(f"{C}=== Шаг 0: Проверка зависимостей хоста ==={W}")
    required = {"dotenv": "python-dotenv", "telethon": "telethon", "sentence_transformers": "sentence-transformers"}
    missing = [pip_name for imp, pip_name in required.items() if subprocess.run([sys.executable, "-c", f"import {imp}"], capture_output=True).returncode != 0]

    if missing:
        print(f"{Y}Устанавливаю библиотеки: {', '.join(missing)}{W}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        print(f"{G}[V] Библиотеки установлены!{W}")

def check_docker():
    print(f"\n{C}=== Шаг 0.5: Проверка Docker ==={W}")
    try:
        subprocess.run(["docker", "--version"], check=True, stdout=subprocess.PIPE)
        print(f"{G}[V] Docker обнаружен!{W}")
        return True
    except Exception:
        print(f"{R}[X] Docker не найден! Установите Docker Desktop.{W}")
        return False

def setup_structure():
    print(f"\n{C}=== Шаг 1: Создание структуры и конфигов ==={W}")
    Path("workspace/_data").mkdir(parents=True, exist_ok=True)
    Path("config/personality").mkdir(parents=True, exist_ok=True)
    
    settings_path = Path("config/settings.yaml")
    if not settings_path.exists():
        settings_path.write_text(DEFAULT_SETTINGS_YAML, encoding="utf-8")
        print(f"{G}[V] Создан файл config/settings.yaml{W}")

    env_path = Path(".env")
    env_example = Path(".env.example")
    
    if not env_path.exists():
        if env_example.exists():
            shutil.copy(env_example, env_path)
            print(f"{Y}[!] Создан файл .env из шаблона .env.example. Заполните его и перезапустите скрипт.{W}")

    for md_file in ["SOUL.md", "COMMUNICATION_STYLE.md", "EXAMPLES_OF_STYLE.md"]:
        p = Path(f"config/personality/{md_file}")
        if not p.exists():
            p.write_text(f"<!-- Заполните настройки характера в файле {md_file} -->\n", encoding="utf-8")
            print(f"{G}[V] Создан пустой шаблон {md_file}{W}")

    return True

def download_models():
    print(f"\n{C}=== Шаг 2: Загрузка NLP моделей ==={W}")
    try:
        from sentence_transformers import SentenceTransformer
        print("Загрузка BAAI/bge-m3 в src/layer00_utils/local_models (может занять пару минут)...")
        SentenceTransformer("BAAI/bge-m3", cache_folder="src/layer00_utils/local_models")
        print(f"{G}[V] Модель памяти загружена!{W}")
    except Exception as e:
        print(f"{R}[X] Ошибка скачивания: {e}{W}")

async def auth_telegram():
    print(f"\n{C}=== Шаг 3: Авторизация Telegram ==={W}")
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    if not os.getenv("TG_API_ID_AGENT"):
        print(f"{R}[X] В .env не заполнен TG_API_ID_AGENT!{W}")
        return

    sys.path.append(str(Path(__file__).resolve().parent))
    try:
        from src.layer02_sensors.telegram.agent_account.client import agent_client
        await agent_client.start()
        print(f"{G}[V] Telegram сессия успешно создана!{W}")
        await agent_client.disconnect()
    except Exception as e:
        print(f"{R}[X] Ошибка авторизации: {e}{W}")

async def main():
    print(f"{C}================================================={W}")
    print(f"{C}   Autonomous Agent Framework - Setup Utility    {W}")
    print(f"{C}================================================={W}\n")
    
    install_dependencies()
    if not check_docker() or not setup_structure(): 
        return
    download_models()
    await auth_telegram()
    
    print(f"\n{G}УСТАНОВКА ЗАВЕРШЕНА!{W}")
    print(f"{Y}1. Настройте config/settings.yaml и config/personality/*.md{W}")
    print(f"{Y}2. Запустите: {G}docker-compose up -d --build{W}\n")

if __name__ == "__main__":
    asyncio.run(main())