import sys
import subprocess
import os
import shutil
import asyncio
import time
from pathlib import Path
import warnings

# Блокировка спама в терминал от ИИ-библиотек
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TQDM_DISABLE"] = "1" # Глобально убиваем прогресс-бары tqdm
warnings.filterwarnings("ignore") # Полностью глушим желтые системные варнинги

# ANSI цвета
G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
C = "\033[96m"
W = "\033[0m"

def install_dependencies():
    """Проверяет и устанавливает нужные библиотеки для работы скрипта инициализации"""
    print(f"{C}=== Шаг 0: Проверка зависимостей хоста ==={W}")
    
    required_packages = {
        "dotenv": "python-dotenv",
        "telethon": "telethon",
        "sentence_transformers": "sentence-transformers"
    }
    missing_packages = []

    for import_name, pip_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(pip_name)

    if missing_packages:
        print(f"{Y}[!] Отсутствуют нужные библиотеки: {', '.join(missing_packages)}{W}")
        print("Устанавливаю их автоматически (это займет минуту).")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_packages])
            print(f"{G}[V] Библиотеки успешно установлены!{W}")
        except Exception as e:
            print(f"{R}[X] Ошибка при установке: {e}{W}")
            print(f"Установите вручную: pip install {' '.join(missing_packages)}")
            sys.exit(1)
    else:
        print(f"{G}[V] Все зависимости для старта присутствуют.{W}")

def check_docker():
    """Проверяет наличие установленного Docker и docker-compose в системе"""
    print(f"\n{C}=== Шаг 0.5: Проверка Docker ==={W}")
    time.sleep(1)
    
    try:
        # Пытаемся вызвать docker --version
        subprocess.run(["docker", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Проверяем docker compose (или старый docker-compose)
        try:
            subprocess.run(["docker", "compose", "version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except (subprocess.CalledProcessError, FileNotFoundError):
            subprocess.run(["docker-compose", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
        print(f"{G}[V] Docker успешно обнаружен!{W}")
        return True
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"{R}[X] Критическая ошибка: Docker не найден в системе!{W}")
        print(f"{Y}AAF использует Docker-песочницу для безопасности.{W}")
        print("Пожалуйста, установите Docker Desktop: https://www.docker.com/products/docker-desktop/")
        return False

# Сначала ставим зависимости, потом импортируем их
install_dependencies()
from dotenv import load_dotenv  # noqa: E402

def check_configs():
    print(f"\n{C}=== Шаг 1: Проверка конфигурации ==={W}")
    time.sleep(1)
    
    settings_path = Path("config/settings.yaml")
    settings_example = Path("config/settings.example.yaml")
    
    if not settings_path.exists():
        if settings_example.exists():
            shutil.copy(settings_example, settings_path)
            time.sleep(1) # Даем ОС время записать файл
            print(f"{G}[V] Создан базовый config/settings.yaml.{W}")
        else:
            print(f"{R}[X] Ошибка: Не найден файл config/settings.example.yaml{W}")
            return False

    env_path = Path(".env")
    env_example = Path(".env.example")
    
    if not env_path.exists():
        if env_example.exists():
            shutil.copy(env_example, env_path)
            print(f"{Y}[!] Создан файл .env. Внесите в него API ключи и перезапустите onboard.py.{W}")
            return False
        else:
            print(f"{R}[X] Ошибка: Не найден файл .env.example{W}")
            return False

    # Принудительно читаем файл .env, перезаписывая кэш
    load_dotenv(dotenv_path=env_path, override=True)
    
    tg_id = str(os.getenv("TG_API_ID_AGENT", "")).strip()
    tg_hash = str(os.getenv("TG_API_HASH_AGENT", "")).strip()

    if not tg_id or "your_tg_api_id" in tg_id or not tg_hash or "your_tg_api_hash" in tg_hash:
        print(f"{R}[X] Ошибка: Заполните TG_API_ID_AGENT и TG_API_HASH_AGENT в файле .env!{W}")
        print("Получить их можно здесь: https://my.telegram.org/auth")
        return False

    print(f"{G}[V] Конфигурационные файлы в порядке.{W}")
    return True

def setup_personality():
    print(f"\n{C}=== Шаг 2: Настройка личности (Personality) ==={W}")
    time.sleep(3)
    
    # Используем абсолютные пути, чтобы не зависеть от того, откуда запущен скрипт
    base_path = Path(__file__).resolve().parent
    example_dir = base_path / "config" / "personality.example"
    target_dir = base_path / "config" / "personality"
    
    # Если папки вообще нет - копируем целиком
    if not target_dir.exists():
        if example_dir.exists():
            shutil.copytree(example_dir, target_dir)
            print(f"{G}[V] Шаблоны личности успешно созданы.{W}")
        else:
            print(f"{R}[X] Критическая ошибка: Не найдена папка {example_dir}{W}")
            return
    else:
        # Если папка есть, проверяем конкретные файлы (вдруг она пустая)
        files_to_check = ["SOUL.md", "COMMUNICATION_STYLE.md", "EXAMPLES_OF_STYLE.md"]
        for f in files_to_check:
            if not (target_dir / f).exists():
                shutil.copy(example_dir / f, target_dir / f)
                print(f"{G}[V] Досоздан недостающий файл: {f}{W}")
        print(f"{G}[V] Проверка файлов личности завершена.{W}")

    time.sleep(4)
    print("\n")
    print(f"\n{Y}💡 СОВЕТ: Пока идет установка, вы можете открыть следующие файлы и настроить характер агента:{W}")
    print(f" - {C}config/personality/SOUL.md{W} (кто он и какие у него цели)")
    print(f" - {C}config/personality/COMMUNICATION_STYLE.md{W} (как он общается)")
    print(f" - {C}config/personality/EXAMPLES_OF_STYLE.md{W} (примеры его ответов)")
    print(" - Советую прочитать .md файлы из папки personality.example: там находятся рекомендации по структуре промптов.")
    time.sleep(8) # Даем пользователю прочитать

def download_models():
    print(f"\n{C}=== Шаг 3: Загрузка NLP моделей ==={W}")
    
    # Отключаем варнинги и прогресс-бары для чистоты вывода
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    
    try:
        from sentence_transformers import SentenceTransformer
        
        model_name = "BAAI/bge-m3"
        cache_folder = "./local_models"
        
        print(f"Загрузка модели {model_name}...")
        print(f"{Y}(Это может занять 1-3 минуты в зависимости от интервала, пожалуйста, подождите...){W}")
        
        SentenceTransformer(model_name, cache_folder=cache_folder)
        print(f"{G}[V] Модель памяти успешно загружена!{W}")
    except Exception as e:
        print(f"{R}[X] Ошибка при скачивании модели: {e}{W}")

async def auth_telegram():
    print(f"\n{C}=== Шаг 4: Авторизация Telegram ==={W}")
    print("Настройка отдельного Telegram-аккаунта для вашего агента. Он будет работать с него.")
    time.sleep(3)
    print(f"{Y}Сейчас потребуется ввести номер телефона (отдельного аккаунта агента) и код из СМС.{W}")
    time.sleep(1)
    
    try:
        from src.layer02_sensors.telegram.agent_account.client import agent_client
        
        await agent_client.start()
        print(f"{G}[V] Telegram сессия успешно создана!{W}")
        await agent_client.disconnect()
    except Exception as e:
        print(f"{R}[X] Ошибка авторизации Telegram: {e}{W}")

async def main():
    print("\n")
    print(f"{C}================================================={W}")
    print(f"{C}   Autonomous Agent Framework - Initial Setup    {W}")
    print(f"{C}================================================={W}\n")
    time.sleep(2)
    
    # 0.5 Проверка Docker
    if not check_docker():
        return

    # 1. Сначала конфиги
    if not check_configs():
        return
        
    # 2. Сразу личность (чтобы пользователь мог её править, пока качаются модели)
    setup_personality()
    
    # 3. Модели (самый долгий шаг)
    download_models()
    
    # 4. Телеграм
    await auth_telegram()
    
    print(f"\n{G}================================================={W}")
    print(f"{G}  УСТАНОВКА ЗАВЕРШЕНА! Система готова.          {W}")
    print(f"{G}================================================={W}")
    
    print(f"\n{Y}⚠️  ПОСЛЕДНИЙ ШАГ: Откройте файл {C}config/settings.yaml{Y} и найдите/заполните:{W}")
    print(f" 1. {C}agent_name{W}      - Имя вашего ИИ-агента.")
    print(f" 2. {C}admin_name{W}      - Ваше имя (как агент будет вас называть).")
    print(f" 3. {C}admin_tg_id{W}     - Узнать свой ID можно в ботах: @userinfobot или @getmyid_bot {W}")
    print(f" 4. {C}model_name{W}      - Выберите рабочую модель (напр. {G}gemini-3.1-flash-lite-preview{W}).")

    print(f"\n{Y}После этого запустите систему командой:{W}")
    print(f"{G}docker-compose up -d --build{W}\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{R}Установка прервана пользователем.{W}")