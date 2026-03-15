# Файл: C:\Users\ivanc\Desktop\AAF\aaf.py 

import sys
import subprocess
import os
import shutil
import argparse

# --- ЦВЕТА ---
G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
C = "\033[96m"
W = "\033[0m"

# Проверка базовой зависимости для генерации YAML
try:
    import yaml
except ImportError:
    print(f"{Y}Устанавливаю PyYAML...{W}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyYAML"])
    import yaml

# =====================================================================
# ШАБЛОНЫ ФАЙЛОВ ДЛЯ НОВЫХ АГЕНТОВ
# =====================================================================

DEFAULT_ENV = """
# База данных (Не меняйте URL, изоляция происходит на уровне схем автоматически)
SQL_DB_URL=postgresql+asyncpg://postgres:postgres@postgres_db:5432/agent_core_db

# Основной провайдер LLM (OpenAI-совместимый)
API_URL=https://generativelanguage.googleapis.com/v1beta/openai/

# API Ключи (Rotator автоматически переключает их при лимитах 429)
LLM_API_KEY_1=
LLM_API_KEY_2=
# LLM_API_KEY_3=
# ...и так далее, система поддерживает любое количество ключей

# API ключи для инструментов (Web Search и Weather)
TAVILY_API_KEY=
OPENWEATHER_API_KEY=

# Настройки официального Telegram аккаунта агента
TG_API_ID_AGENT=
TG_API_HASH_AGENT=
"""

DEFAULT_SETTINGS_YAML = """
identity:
  agent_name: "{agent_name}"
  admin_name: "AdminName"
  admin_tg_id: 123456789 

llm:
  model_name: "gemini-flash-latest"
  vision_model: "gemini-3.1-flash-lite-preview"
  available_models:
    - "gemini-3.1-pro-high"
    - "gemini-flash-latest"
    - "gpt-5.4"
    - "claude-opus-4-6"
  temperature: 0.7
  max_react_steps: 15

  limits:
    max_file_read_chars: 80000
    max_web_read_chars: 15000
    image_max_size: [1500, 1500]

  context_depth:
      event_driven: { thoughts_limit: 5, actions_limit: 10, dialogue_limit: 30 }
      proactivity: { thoughts_limit: 5, actions_limit: 20, dialogue_limit: 30 }
      thoughts: { thoughts_limit: 10, actions_limit: 30, dialogue_limit: 40 }

swarm:
  sybagent_model: "gemini-3.1-flash-lite-preview"
  max_sybagent_steps: 10

rhythms:
  proactivity_interval_sec: 900
  thoughts_interval_sec: 1800
  min_proactivity_cooldown_sec: 120
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
    local_path: "src/layer00_utils/local_models/models--BAAI--bge-m3"
  workspace_garbage_collector:
    temp_files_ttl_hours: 48

telegram:
  agent_session_name: "agent_session"
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

AGENT_SDK_PY = """
import urllib.request
import json
import os

STATE_FILE = "sandbox_state.json"
MASTER_AGENT = os.getenv("MASTER_AGENT", "agent_core")
IN_DOCKER = os.path.exists('/.dockerenv')
HOST = MASTER_AGENT if IN_DOCKER else "127.0.0.1"
LISTENER_URL = f"http://{HOST}:18790/alert"

def send_alert(message: str):
    try:
        data = json.dumps({"message": message}).encode('utf-8')
        req = urllib.request.Request(LISTENER_URL, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=3) as response:
            pass 
    except Exception as e:
        print(f"Failed to send alert to Agent '{MASTER_AGENT}': {e}")

def save_state(key: str, value):
    state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except Exception:
            pass
    state[key] = value
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=4)

def load_state(key: str, default=None):
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                return state.get(key, default)
        except Exception:
            pass
    return default 
"""


# =====================================================================
# ЛОГИКА УТИЛИТЫ
# =====================================================================


def check_and_download_models():
    """Проверяет наличие тяжелых моделей и скачивает их при необходимости"""
    
    # 1. Проверка Embedding модели (BAAI/bge-m3)
    model_path = os.path.join("src", "layer00_utils", "local_models", "models--BAAI--bge-m3")
    if not os.path.exists(model_path):
        print(f"{Y}[!] Embedding модель не найдена. Начинаю загрузку (около 2.5 ГБ)...{W}")
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            print(f"{Y}Устанавливаю huggingface_hub...{W}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub"])
            from huggingface_hub import snapshot_download
        
        snapshot_download(
            repo_id="BAAI/bge-m3",
            local_dir=os.path.join("src", "layer00_utils", "local_models", "models--BAAI--bge-m3"),
            local_dir_use_symlinks=False
        )
        print(f"{G}[V] Embedding модель успешно загружена.{W}")

    # 2. Проверка Vosk модели (для распознавания речи)
    vosk_path = os.path.join("src", "layer00_utils", "vosk_model", "vosk-model-small-ru-0.22")
    if not os.path.exists(vosk_path):
        print(f"{Y}[!] Модель Vosk не найдена. Начинаю загрузку...{W}")
        os.makedirs(os.path.dirname(vosk_path), exist_ok=True)
        
        # Скачиваем через curl или powershell (чтобы не тянуть лишние либы)
        import zipfile
        import urllib.request
        
        url = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
        zip_path = "src/layer00_utils/vosk_model/model.zip"
        
        print(f"{C}Скачивание Vosk с {url}...{W}")
        urllib.request.urlretrieve(url, zip_path)
        
        print(f"{C}Распаковка...{W}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall("src/layer00_utils/vosk_model/")
        
        os.remove(zip_path)
        print(f"{G}[V] Модель Vosk готова.{W}")


def check_docker():
    try:
        subprocess.run(["docker", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception:
        print(f"{R}[X] Docker не запущен или не установлен!{W}")
        sys.exit(1)

def run_cmd(cmd, hide_output=False):
    if hide_output:
        subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        subprocess.run(cmd, shell=True)

def auto_migrate_v1():
    """Переносит данные монолита в мульти-агентную структуру (создает агента VEGA)"""
    if os.path.exists("workspace") and not os.path.exists("Agents"):
        print(f"\n{C}=== Обнаружена старая архитектура монолита! ==={W}")
        print(f"{Y}Начинаю автоматическую миграцию в мульти-агентный режим (v1.1.0)...{W}")
        
        vega_path = "Agents/VEGA"
        os.makedirs(vega_path, exist_ok=True)
        
        # Переносим workspace
        if os.path.exists("workspace"):
            shutil.move("workspace", f"{vega_path}/workspace")
        # Переносим config
        if os.path.exists("config"):
            shutil.move("config", f"{vega_path}/config")
        # Переносим .env
        if os.path.exists(".env"):
            shutil.move(".env", f"{vega_path}/.env")
        # Переносим логи
        if os.path.exists("src/logs"):
            os.makedirs(f"{vega_path}/logs", exist_ok=True)
            for f in os.listdir("src/logs"):
                shutil.move(os.path.join("src/logs", f), os.path.join(f"{vega_path}/logs", f))
            shutil.rmtree("src/logs")
            
        print(f"{G}[V] Данные успешно мигрированы в профиль 'VEGA'!{W}\n")
        generate_docker_compose()

def generate_docker_compose():
    """Генерирует идеальный docker-compose.yml на основе папок в Agents/"""
    compose = {
        "version": "3.8",
        "services": {
            "postgres_db": {
                "image": "postgres:15-alpine",
                "restart": "always",
                "environment": {
                    "POSTGRES_USER": "postgres",
                    "POSTGRES_PASSWORD": "postgres",
                    "POSTGRES_DB": "agent_core_db"
                },
                "volumes": ["agent_pg_data:/var/lib/postgresql/data"]
            },
            "sandbox_engine": {
                "image": "docker:24-dind",
                "restart": "unless-stopped",
                "privileged": True,
                "environment": {"DOCKER_TLS_CERTDIR": ""},
                "command": "--host=tcp://0.0.0.0:2375",
                "volumes": ["./Agents:/app/Agents"]
            }
        },
        "volumes": {"agent_pg_data": None}
    }

    agents_dir = "Agents"
    if os.path.exists(agents_dir):
        for agent_name in os.listdir(agents_dir):
            agent_path = os.path.join(agents_dir, agent_name)
            if os.path.isdir(agent_path):
                # DNS-имя в сети Docker (например: agent_vega)
                alias = f"agent_{agent_name.lower()}"
                
                compose["services"][alias] = {
                    "build": ".",
                    "depends_on": ["postgres_db", "sandbox_engine"],
                    "restart": "unless-stopped",
                    "env_file": [f"./Agents/{agent_name}/.env"],
                    "environment": [
                        f"AGENT_NAME={agent_name}",
                        "DOCKER_HOST=tcp://sandbox_engine:2375"
                    ],
                    "networks": {
                        "default": {"aliases": [alias]}
                    },
                    "volumes": [
                        f"./Agents/{agent_name}:/app/Agents/{agent_name}",
                        "./src:/app/src",
                        "./src/layer00_utils/local_models:/app/src/layer00_utils/local_models"
                    ]
                }

    with open("docker-compose.yml", "w", encoding="utf-8") as f:
        f.write("# AUTO-GENERATED BY aaf.py. DO NOT EDIT DIRECTLY.\n")
        f.write("# Используйте `python aaf.py generate` для обновления этого файла.\n\n")
        yaml.dump(compose, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

def print_agent_setup_guide(name):
    print(f"\n{G}=================================================={W}")
    print(f"{G}      🚀 ПРОФИЛЬ {name.upper()} ГОТОВ К НАСТРОЙКЕ {W}")
    print(f"{G}=================================================={W}")
    
    print(f"{Y}[!] ШАГ 1: API КЛЮЧИ И МОДЕЛИ{W}")
    print(f"    Отредактируйте: {C}Agents/{name}/.env{W}")
    print( "    Указать API-ключи.")

    print(f"\n{Y}[!] ШАГ 2: АВТОРИЗАЦИЯ ТЕЛЕГРАМ{W}")
    print(f"    Выполните: {C}python aaf.py auth {name}{W}") 
    print("     (Это создаст файл сессии .session)")
    print(f"    Либо положите уже готовый файл .session в Agents/{name}/workspace/_data/telegram_sessions, предварительно переименовав файл в 'agent_session.session'.")

    print(f"\n{Y}[!] ШАГ 3: КОНФИГУРАЦИЯ СИСТЕМЫ{W}")
    print(f"    Файл: {C}Agents/{name}/config/settings.yaml{W}")
    print( "    Укажите ваше имя и ID вашего аккаунта в Telegram. По желанию можно изменить LLM модель и прочие параметры.")

    print(f"\n{Y}[!] ШАГ 4: PERSONALITY PROMPT{W}")
    print(f"    Файл: {C}Agents/{name}/config/personality/*.md{W}")
    print( "    Откройте три файла .md и определите роль агента, его стиль общения и задачи.")

    print(f"\n{Y}[!] ШАГ 5: ЗАПУСК{W}")
    print(f"    Команда: {C}python aaf.py start {name}{W}")
    
    print(f"{G}=================================================={W}\n")

def create_agent(name: str):
    name = name.upper()
    agent_dir = os.path.join("Agents", name)
    
    if os.path.exists(agent_dir):
        print(f"{R}[X] Ошибка: Агент с именем '{name}' уже существует!{W}")
        return

    print(f"{C}=== Создание профиля агента '{name}' ==={W}")
    
    # Структура папок
    os.makedirs(os.path.join(agent_dir, "config/personality"), exist_ok=True)
    os.makedirs(os.path.join(agent_dir, "workspace/_data/telegram_sessions"), exist_ok=True)
    os.makedirs(os.path.join(agent_dir, "workspace/temp"), exist_ok=True)
    os.makedirs(os.path.join(agent_dir, "workspace/sandbox"), exist_ok=True)
    os.makedirs(os.path.join(agent_dir, "logs"), exist_ok=True)

    # Генерация файлов
    with open(os.path.join(agent_dir, ".env"), "w", encoding="utf-8") as f:
        f.write(DEFAULT_ENV.strip())
        
    with open(os.path.join(agent_dir, "config/settings.yaml"), "w", encoding="utf-8") as f:
        f.write(DEFAULT_SETTINGS_YAML.replace("{agent_name}", name).strip())
        
    for md_file in ["SOUL.md", "COMMUNICATION_STYLE.md", "EXAMPLES_OF_STYLE.md"]:
        with open(os.path.join(agent_dir, f"config/personality/{md_file}"), "w", encoding="utf-8") as f:
            f.write("<!-- Опишите характер агента в этом файле -->\n")

    # Забрасываем Agent SDK в песочницу
    with open(os.path.join(agent_dir, "workspace/sandbox/agent_sdk.py"), "w", encoding="utf-8") as f:
        f.write(AGENT_SDK_PY.strip())

    generate_docker_compose()
    print_agent_setup_guide(name=name)

def cmd_auth(agent_name: str):
    agent_name = agent_name.upper()
    agent_dir = os.path.join("Agents", agent_name)
    
    if not os.path.exists(agent_dir):
        print(f"{R}[X] Ошибка: Профиль агента '{agent_name}' не найден!{W}")
        return
        
    print(f"\n{C}=== Авторизация Telegram для агента '{agent_name}' ==={W}")
    print(f"{Y}[i] Если у вас уже есть готовый файл сессии Telethon (agent_session.session),")
    print(f"просто положите его в папку: Agents/{agent_name}/workspace/_data/telegram_sessions/")
    print(f"В таком случае эта авторизация не потребуется.{W}\n")
    
    # Читаем .env агента напрямую
    env_path = os.path.join(agent_dir, ".env")
    api_id = ""
    api_hash = ""
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TG_API_ID_AGENT="):
                    api_id = line.split("=", 1)[1].strip()
                elif line.startswith("TG_API_HASH_AGENT="):
                    api_hash = line.split("=", 1)[1].strip()
                    
    if not api_id or not api_hash:
        print(f"{R}[X] Ошибка: TG_API_ID_AGENT и/или TG_API_HASH_AGENT не заполнены в файле {env_path}{W}")
        print(f"{Y}Пожалуйста, впишите их туда, сохраните файл и повторите команду.{W}")
        return
        
    try:
        api_id = int(api_id)
    except ValueError:
        print(f"{R}[X] Ошибка: TG_API_ID_AGENT должен состоять только из цифр!{W}")
        return

    # Динамический импорт Telethon только тогда, когда он реально нужен
    try:
        from telethon import TelegramClient
    except ImportError:
        print(f"{Y}Устанавливаю Telethon для локальной авторизации...{W}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "telethon"])
        from telethon import TelegramClient

    session_dir = os.path.join(agent_dir, "workspace/_data/telegram_sessions")
    os.makedirs(session_dir, exist_ok=True)
    
    session_path = os.path.join(session_dir, "agent_session")
    
    print(f"{G}Запуск клиента Telethon... Следуйте инструкциям на экране.{W}")
    
    # Telethon client.start() синхронно запросит номер и код в консоли
    client = TelegramClient(session_path, api_id, api_hash)
    client.start()
    
    print(f"\n{G}[V] Авторизация успешно завершена! Файл сессии сохранен.{W}")
    print(f"Теперь вы можете запустить агента: {C}python aaf.py start {agent_name}{W}")
    
    client.disconnect()

def cmd_status():
    check_docker()
    print(f"\n{C}=== AAF Swarm Status ==={W}")
    
    agents = [d for d in os.listdir("Agents") if os.path.isdir(os.path.join("Agents", d))] if os.path.exists("Agents") else []
    if not agents:
        print("Агенты не найдены. Используйте 'python aaf.py create <NAME>'.")
        return
        
    # Парсим вывод docker ps
    result = subprocess.run(["docker", "ps", "--format", "{{.Names}}|{{.Status}}"], capture_output=True, text=True)
    running_containers = {line.split('|')[0]: line.split('|')[1] for line in result.stdout.strip().split('\n') if line}
    
    print(f"{'AGENT NAME':<15} | {'STATUS':<20} | {'LLM MODEL':<25}")
    print("-" * 65)
    
    for agent in agents:
        alias = f"agent_{agent.lower()}"
        status = running_containers.get(alias, f"{R}Offline{W}")
        if "Up" in status:
            status = f"{G}{status}{W}"
            
        model = "Unknown"
        settings_path = os.path.join("Agents", agent, "config/settings.yaml")
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith("model_name:"):
                        model = line.split(":")[1].strip().replace('"', '').replace("'", "")
                        break
                        
        print(f"{agent:<15} | {status:<29} | {C}{model:<25}{W}")
    print("\n")
def process_command(args_list):
    """Обрабатывает список аргументов (из консоли или интерактивного ввода)"""
    parser = argparse.ArgumentParser(description="AAF Swarm Manager (v1.1.0)", exit_on_error=False)
    parser.add_argument("command", choices=["status", "create", "auth", "start", "stop", "logs", "generate", "help", "exit", "quit"], help="Команда для выполнения")
    parser.add_argument("agent", nargs="?", help="Имя агента (или 'all')")
    
    try:
        args = parser.parse_args(args_list)
    except SystemExit:
        # argparse пытается сделать sys.exit при неверной команде, перехватываем
        return True
    
    if args.command in ["exit", "quit"]:
        return False
        
    if args.command == "help":
        print(f"\n{C}Доступные команды:{W}")
        print(f"  {G}status{W}               - Показать статус всех агентов")
        print(f"  {G}create <NAME>{W}        - Создать профиль нового агента")
        print(f"  {G}auth <NAME>{W}          - Авторизовать Telegram для агента")
        print(f"  {G}start <NAME | all>{W}   - Запустить агента (или всех)")
        print(f"  {G}stop <NAME | all>{W}    - Остановить агента (или всех)")
        print(f"  {G}logs <NAME>{W}          - Смотреть логи агента в реальном времени")
        print(f"  {G}generate{W}             - Пересобрать docker-compose.yml")
        print(f"  {G}exit{W}                 - Выйти из AAF Manager\n")
        return True

    if args.command == "status":
        cmd_status()
        
    elif args.command == "generate":
        generate_docker_compose()
        print(f"{G}[V] docker-compose.yml пересобран.{W}")

    elif args.command == "create":
        if not args.agent:
            print(f"{R}Укажите имя агента: create <NAME>{W}")
            return True
        create_agent(args.agent)

    elif args.command == "auth":
        if not args.agent:
            print(f"{R}Укажите имя агента: auth <NAME>{W}")
            return True
        cmd_auth(args.agent)

    elif args.command == "start":
        check_and_download_models()
        check_docker()
        generate_docker_compose()
        if not args.agent or args.agent.lower() == "all":
            print(f"{Y}Запускаем ВСЮ инфраструктуру и ВСЕХ агентов...{W}")
            run_cmd("docker compose up -d --build")
        else:
            alias = f"agent_{args.agent.lower()}"
            print(f"{C}Запускаем агента {args.agent.upper()}...{W}")
            run_cmd(f"docker compose up -d --build {alias}")

    elif args.command == "stop":
        check_docker()
        if not args.agent or args.agent.lower() == "all":
            print(f"{Y}Останавливаем ВСЮ систему...{W}")
            run_cmd("docker compose down")
        else:
            alias = f"agent_{args.agent.lower()}"
            print(f"{Y}Останавливаем агента {args.agent.upper()}...{W}")
            run_cmd(f"docker compose stop {alias}")

    elif args.command == "logs":
        check_docker()
        if not args.agent:
            print(f"{R}Укажите имя агента: logs <NAME>{W}")
            return True
        alias = f"agent_{args.agent.lower()}"
        # В интерактивном режиме логи лучше прерывать по Ctrl+C и возвращаться в меню
        print(f"{Y}Нажмите Ctrl+C для выхода из логов...{W}")
        try:
            run_cmd(f"docker compose logs {alias} -f")
        except KeyboardInterrupt:
            print(f"\n{C}Выход из просмотра логов.{W}")

    return True

def interactive_mode():
    """Запускает интерактивную оболочку"""
    print(f"{C}========================================{W}")
    print(f"{G}            AAF Manager                 {W}")
    print(f"{C}========================================{W}")
    print("Введите 'help' для списка команд или 'exit' для выхода.\n")
    
    import shlex
    while True:
        try:
            user_input = input(f"{C}AAF > {W}").strip()
            if not user_input:
                continue
                
            # shlex.split правильно разбивает строку, учитывая кавычки
            args_list = shlex.split(user_input)
            
            should_continue = process_command(args_list)
            if not should_continue:
                print(f"{Y}Выход из AAF Manager.{W}")
                break
                
        except KeyboardInterrupt:
            print(f"\n{Y}Выход из AAF Manager.{W}")
            break
        except Exception as e:
            print(f"{R}Ошибка: {e}{W}")

def main():
    auto_migrate_v1() # Тихая миграция при старте, если нужно
    
    # Если скрипт запущен без аргументов -> запускаем интерактивную консоль
    if len(sys.argv) == 1:
        interactive_mode()
    else:
        # Иначе обрабатываем как обычную консольную команду
        process_command(sys.argv[1:])

if __name__ == "__main__":
    main()