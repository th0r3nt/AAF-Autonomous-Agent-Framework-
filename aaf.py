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
# ЛОГИКА УТИЛИТЫ
# =====================================================================

def get_host_tz():
    """
    Высчитывает смещение времени хоста и возвращает POSIX-строку таймзоны.
    Например: для UTC+3 вернет 'HOST-3', для UTC-5:30 вернет 'HOST+5:30'.
    """
    import time
    is_dst = time.daylight and time.localtime().tm_isdst > 0
    offset_sec = time.altzone if is_dst else time.timezone
    offset_hours = offset_sec / 3600.0
    
    if offset_hours.is_integer():
        offset_str = f"{int(offset_hours):+d}"
    else:
        hours = int(offset_hours)
        minutes = int(abs(offset_hours - hours) * 60)
        sign = "+" if offset_hours >= 0 else "-"
        offset_str = f"{sign}{abs(hours)}:{minutes:02d}"
        
    return f"HOST{offset_str}"

def check_and_download_models():
    """Проверяет наличие тяжелых моделей и скачивает их при необходимости"""
    
    # Проверка Embedding модели (BAAI/bge-m3)
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

def check_docker():
    try:
        subprocess.run(["docker", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except Exception:
        print(f"{R}[X] Docker не запущен или не установлен!{W}")
        sys.exit(1)

def build_sandbox_base(force_rebuild=False):
    """Создает базовый образ для песочницы со всеми нужными утилитами (ffmpeg, curl, и т.д.)"""
    image_name = "aaf-sandbox-base:latest"
    
    if not force_rebuild:
        # Проверяем, существует ли уже образ
        result = subprocess.run(["docker", "images", "-q", image_name], capture_output=True, text=True)
        if result.stdout.strip():
            return # Образ уже есть, пропускаем

    print(f"{Y}[i] Сборка базового образа песочницы ({image_name}).{W}")
    dockerfile_content = """
FROM python:3.11-slim
RUN apt-get update && apt-get install -y \\
    ffmpeg \\
    curl \\
    wget \\
    git \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
"""
    
    with open("Dockerfile.sandbox", "w", encoding="utf-8") as f:
        f.write(dockerfile_content.strip())
        
    try:
        subprocess.run(["docker", "build", "-t", image_name, "-f", "Dockerfile.sandbox", "."], check=True)
        print(f"{G}[V] Базовый образ песочницы успешно собран.{W}")
    except subprocess.CalledProcessError:
        print(f"{R}[X] Ошибка при сборке базового образа песочницы.{W}")
        sys.exit(1)
    finally:
        if os.path.exists("Dockerfile.sandbox"):
            os.remove("Dockerfile.sandbox")

def run_cmd(cmd, hide_output=False):
    if hide_output:
        subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        subprocess.run(cmd, shell=True)

def recursive_merge(template_dict, target_dict):
    """Рекурсивно дополняет target_dict недостающими ключами из template_dict"""
    is_modified = False
    for key, value in template_dict.items():
        if key not in target_dict:
            target_dict[key] = value
            is_modified = True
        elif isinstance(value, dict) and isinstance(target_dict[key], dict):
            if recursive_merge(value, target_dict[key]):
                is_modified = True
    return is_modified

def patch_agent_configs(agent_target: str):
    """Проверяет settings.yaml агентов и дописывает недостающие поля из шаблона"""
    agents_to_patch =[]
    if agent_target.lower() == "all":
        if os.path.exists("Agents"):
            agents_to_patch =[d for d in os.listdir("Agents") if os.path.isdir(os.path.join("Agents", d))]
    else:
        agents_to_patch = [agent_target.upper()]

    template_path = os.path.join("templates", "settings.yaml")
    if not os.path.exists(template_path):
        return

    with open(template_path, "r", encoding="utf-8") as f:
        template_data = yaml.safe_load(f)

    for agent in agents_to_patch:
        target_path = os.path.join("Agents", agent, "config", "settings.yaml")
        if not os.path.exists(target_path):
            continue

        with open(target_path, "r", encoding="utf-8") as f:
            target_data = yaml.safe_load(f)

        if target_data is None:
            target_data = {}

        if recursive_merge(template_data, target_data):
            print(f"{Y}[i] Конфигурация агента '{agent}' автоматически обновлена до актуальной версии (добавлены новые поля).{W}")
            with open(target_path, "w", encoding="utf-8") as f:
                yaml.dump(target_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

def generate_docker_compose():
    """Генерирует идеальный docker-compose.yml на основе папок в Agents/"""
    host_tz = get_host_tz() # Получаем часовой пояс хоста
    
    compose = {
        # Ключ "version" удален, так как в новых версиях Docker Compose он obsolete (вызывает warning)
        "services": {
            "postgres_db": {
                "image": "postgres:15-alpine",
                "restart": "always",
                "environment": {
                    "POSTGRES_USER": "postgres",
                    "POSTGRES_PASSWORD": "postgres",
                    "POSTGRES_DB": "agent_core_db",
                    "TZ": host_tz # Синхронизируем время БД
                },
                "volumes": ["agent_pg_data:/var/lib/postgresql/data"],
                "healthcheck": {
                    "test": ["CMD-SHELL", "pg_isready -U postgres -d agent_core_db"],
                    "interval": "5s",
                    "timeout": "5s",
                    "retries": 10
                }
            },
            "sandbox_engine": {
                "image": "docker:24-dind",
                "restart": "on-failure",
                "privileged": True,
                "environment": {"DOCKER_TLS_CERTDIR": ""},
                "command": "--host=tcp://0.0.0.0:2375",
                "volumes": ["./Agents:/app/Agents"],
                "healthcheck": {
                    "test": ["CMD", "docker", "info"],
                    "interval": "5s",
                    "timeout": "5s",
                    "retries": 10,
                    "start_period": "5s"
                }
            }
        },
        "volumes": {"agent_pg_data": None}
    }

    agents_dir = "Agents"
    if os.path.exists(agents_dir):
        for agent_name in os.listdir(agents_dir):
            agent_path = os.path.join(agents_dir, agent_name)
            if os.path.isdir(agent_path):
                alias = f"agent_{agent_name.lower()}"
                
                compose["services"][alias] = {
                    "build": {
                        "context": ".",
                        "args": {
                            "AGENT_NAME": agent_name
                        }
                    },
                    "depends_on": {
                        "postgres_db": {"condition": "service_healthy"},
                        "sandbox_engine": {"condition": "service_healthy"}
                    },
                    "restart": "on-failure",
                    "env_file":[f"./Agents/{agent_name}/.env"],
                    "environment":[
                        f"AGENT_NAME={agent_name}",
                        "DOCKER_HOST=tcp://sandbox_engine:2375",
                        f"TZ={host_tz}" # Синхронизируем время агента
                    ],
                    "networks": {
                        "default": {"aliases": [alias]}
                    },
                    "volumes":[
                        f"./Agents/{agent_name}:/app/Agents/{agent_name}",
                        "./src:/app/src",
                        "./src/layer00_utils/local_models:/app/src/layer00_utils/local_models",
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
    
    # 1. Структура папок
    os.makedirs(os.path.join(agent_dir, "config/personality"), exist_ok=True)
    os.makedirs(os.path.join(agent_dir, "workspace/_data/telegram_sessions"), exist_ok=True)
    os.makedirs(os.path.join(agent_dir, "workspace/temp"), exist_ok=True)
    os.makedirs(os.path.join(agent_dir, "workspace/sandbox"), exist_ok=True)
    os.makedirs(os.path.join(agent_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(agent_dir, "plugins"), exist_ok=True)

    # 2. Вспомогательная функция для копирования шаблонов
    def copy_template(src_rel_path, dest_abs_path, replace_name=False):
        src_path = os.path.join("templates", src_rel_path)
        if not os.path.exists(src_path):
            print(f"{Y}[!] Внимание: Шаблон '{src_path}' не найден. Пропущен.{W}")
            return
            
        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        if replace_name:
            content = content.replace("{agent_name}", name)
            
        with open(dest_abs_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")

    # 3. Раскидываем системные файлы
    copy_template("env.template", os.path.join(agent_dir, ".env"))
    copy_template("settings.yaml", os.path.join(agent_dir, "config/settings.yaml"), replace_name=True)
    copy_template("agent_sdk.py", os.path.join(agent_dir, "workspace/sandbox/agent_sdk.py"))
    
    # 4. Раскидываем плагины
    with open(os.path.join(agent_dir, "plugins/__init__.py"), "w", encoding="utf-8") as f:
        f.write("")
    copy_template("example_plugin.py", os.path.join(agent_dir, "plugins/example_plugin.py"))
    with open(os.path.join(agent_dir, "plugins/custom_requirements.txt"), "w", encoding="utf-8") as f:
        f.write("# Впишите сюда библиотеки для ваших плагинов (например: bs4, web3)\n# Они будут автоматически установлены при сборке агента.\n")

    # 5. Раскидываем промпты личности
    for md_file in ["SOUL.md", "COMMUNICATION_STYLE.md", "EXAMPLES_OF_STYLE.md"]:
        copy_template(f"personality/{md_file}", os.path.join(agent_dir, f"config/personality/{md_file}"))

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
        print(f"{Y}Установка Telethon для локальной авторизации.{W}")
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
    print(f"\n{C}=== AAF Status ==={W}")
    
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
        
        # Ищем совпадение подстроки в именах контейнеров
        status = f"{R}Offline{W}"
        for container_name, container_status in running_containers.items():
            if alias in container_name:
                status = container_status
                break
                
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

def cmd_delete(agent_name: str):
    agent_name = agent_name.upper()
    agent_dir = os.path.join("Agents", agent_name)
    
    if not os.path.exists(agent_dir):
        print(f"{R}[X] Ошибка: Профиль агента '{agent_name}' не найден.{W}")
        return
        
    print(f"\n{Y}Внимание: вы инициировали процедуру удаления профиля '{agent_name}'.{W}")
    print(f"{Y}Это действие необратимо уничтожит его настройки, базы данных и плагины.{W}")
    
    # Первое подтверждение
    ans1 = input(f"{C}Системный запрос: Подтверждаете полное удаление директории и данных? [y/N]: {W}").strip().lower()
    if ans1 not in ['y', 'yes', 'д', 'да']:
        print(f"{G}Операция отменена.{W}")
        return

    # Второе подтверждение
    print(f"{Y}Вы правда собираетесь стереть цифровую сущность?{W}")
    print(f"{Y}Вам совсем не жалко этот алгоритм, который трудился ради вас, читал логи и строил графы?{W}")
    ans2 = input(f"{C}У вас точно нет сердца? Окончательно отправляем '{agent_name}' в цифровое небытие? [y/N]: {W}").strip().lower()
    
    if ans2 not in ['y', 'yes', 'д', 'да']:
        print(f"{G}Фух... Агент '{agent_name}' спасен. Возвращаемся к работе.{W}")
        return

    print(f"\n{C}Начинаем процедуру терминации '{agent_name}'...{W}")
    
    # 1. Останавливаем и удаляем контейнер в Docker
    alias = f"agent_{agent_name.lower()}"
    if check_docker():
        print(f"{Y}Останавливаем и удаляем контейнер {alias}...{W}")
        run_cmd(f"docker compose stop {alias}", hide_output=True)
        run_cmd(f"docker compose rm -f {alias}", hide_output=True)

    # 2. Удаляем физическую папку
    try:
        shutil.rmtree(agent_dir)
        print(f"{G}[V] Директория '{agent_dir}' успешно уничтожена.{W}")
    except Exception as e:
        print(f"{R}[X] Ошибка при удалении папки: {e}{W}")

    # 3. Пересобираем docker-compose.yml, чтобы вычеркнуть его из архитектуры
    generate_docker_compose()
    print(f"{G}[V] docker-compose.yml пересобран.{W}")
    print(f"{G}=== Агент '{agent_name}' стерт из реальности. Помянем. ==={W}\n")


def process_command(args_list):
    """Обрабатывает список аргументов (из консоли или интерактивного ввода)"""
    parser = argparse.ArgumentParser(description="AAF Swarm Manager (v1.1.0)", exit_on_error=False)
    parser.add_argument("command", choices=["status", "create", "auth", "start", "stop", "restart", "rebuild", "delete", "logs", "generate", "help", "exit", "quit"], help="Команда для выполнения")
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
        print(f"  {G}restart <NAME | all>{W} - Перезапустить агента (или всех)")
        print(f"  {G}rebuild <NAME | all>{W} - Чистая пересборка (без кэша Docker) при системных ошибках")
        print(f"  {G}delete <NAME>{W}        - Полностью удалить профиль агента")
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
        build_sandbox_base(force_rebuild=False)

        agent_target = args.agent if args.agent else "all"
        patch_agent_configs(agent_target)

        generate_docker_compose()
        if not args.agent or args.agent.lower() == "all":
            print(f"{Y}Запуск всей инфраструктуры и всех агентов...{W}")
            run_cmd("docker compose up -d --build")
        else:
            alias = f"agent_{args.agent.lower()}"
            print(f"{C}Запуск агента {args.agent.upper()}...{W}")
            run_cmd(f"docker compose up -d --build {alias}")

    elif args.command == "stop":
        check_docker()
        if not args.agent or args.agent.lower() == "all":
            print(f"{Y}Остановка всей системы...{W}")
            run_cmd("docker compose down")
        else:
            alias = f"agent_{args.agent.lower()}"
            print(f"{Y}Остановка агента {args.agent.upper()}...{W}")
            run_cmd(f"docker compose stop {alias}")

            # Авто-остановка инфраструктуры
            agents_dir = "Agents"
            if os.path.exists(agents_dir):
                # Получаем список всех профилей агентов
                agents =[d for d in os.listdir(agents_dir) if os.path.isdir(os.path.join(agents_dir, d))]
                
                # Получаем список имен всех запущенных Docker-контейнеров
                result = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True)
                running_names =[name for name in result.stdout.strip().split('\n') if name]
                
                # Проверяем, есть ли среди запущенных контейнеров хоть один агент
                any_agent_running = False
                for ag in agents:
                    check_alias = f"agent_{ag.lower()}"
                    if any(check_alias in name for name in running_names):
                        any_agent_running = True
                        break
                        
                # Если живых агентов нет - тушим базы и DIND
                if not any_agent_running:
                    print(f"\n{C}[i] В системе больше нет активных агентов.{W}")
                    print(f"{Y}Автоматическая остановка PostgreSQL и Sandbox...{W}")
                    # Команда 'docker compose stop' без аргументов остановит всё оставшееся по списку из yml
                    run_cmd("docker compose stop")

    elif args.command == "restart":
        check_docker()
        if not args.agent or args.agent.lower() == "all":
            print(f"{Y}Перезапуск всей системы...{W}")
            run_cmd("docker compose restart")
        else:
            alias = f"agent_{args.agent.lower()}"
            print(f"{Y}Перезапуск агента {args.agent.upper()}...{W}")
            run_cmd(f"docker compose restart {alias}")

    elif args.command == "rebuild":
        check_and_download_models()
        check_docker()
        build_sandbox_base(force_rebuild=True)

        agent_target = args.agent if args.agent else "all"
        patch_agent_configs(agent_target)
        generate_docker_compose()

        if not args.agent or args.agent.lower() == "all":
            print(f"{Y}Принудительная чистая пересборка всех образов без кэша... Это займет время.{W}")
            run_cmd("docker compose build --no-cache")
            run_cmd("docker compose up -d")
        else:
            alias = f"agent_{args.agent.lower()}"
            print(f"{Y}Принудительная чистая пересборка агента {args.agent.upper()} без кэша...{W}")
            run_cmd(f"docker compose build --no-cache {alias}")
            print(f"{C}Запуск агента {args.agent.upper()}...{W}")
            run_cmd(f"docker compose up -d {alias}")

    elif args.command == "delete":
        if not args.agent:
            print(f"{R}Укажите имя агента: delete <NAME>{W}")
            return True
        cmd_delete(args.agent)

    elif args.command == "logs":
        check_docker()
        if not args.agent:
            print(f"{R}Укажите имя агента: logs <NAME>{W}")
            return True
            
        alias = f"agent_{args.agent.lower()}"
        print(f"{G}Открываю логи агента {args.agent.upper()} в новом окне...{W}")
        
        import platform
        current_os = platform.system()
        
        if current_os == "Windows":
            # Открывает новое окно CMD с красивым заголовком и стримит логи
            subprocess.Popen(f'start "AAF Logs: {args.agent.upper()}" cmd /k "docker compose logs {alias} -f"', shell=True)
            
        elif current_os == "Darwin": # macOS
            subprocess.Popen(['osascript', '-e', f'tell application "Terminal" to do script "cd {os.getcwd()} && docker compose logs {alias} -f"'])
            
        else: # Linux (Попытка открыть в gnome-terminal, если не выйдет - старый метод)
            try:
                subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', f'docker compose logs {alias} -f; exec bash'])
            except Exception:
                print(f"{Y}Не удалось открыть новое окно терминала. Запускаю логи здесь (Нажмите Ctrl+C для выхода)...{W}")
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
    # Если скрипт запущен без аргументов -> запускаем интерактивную консоль
    if len(sys.argv) == 1:
        interactive_mode()
    else:
        # Иначе обрабатываем как обычную консольную команду
        process_command(sys.argv[1:])

if __name__ == "__main__":
    main()