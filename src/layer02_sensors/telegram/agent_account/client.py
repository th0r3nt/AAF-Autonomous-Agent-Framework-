import os
from telethon import TelegramClient
from dotenv import load_dotenv
from pathlib import Path
from src.layer00_utils.config_manager import config
from src.layer00_utils.logger import system_logger

load_dotenv()

raw_api_id = os.getenv("TG_API_ID_AGENT")
TG_API_HASH_AGENT = os.getenv("TG_API_HASH_AGENT", "")

# Безопасный парсинг ID, чтобы не ронять весь проект при импорте
try:
    TG_API_ID_AGENT = int(raw_api_id) if raw_api_id else 0
except ValueError:
    system_logger.critical("[Telegram Telethon] Ошибка: TG_API_ID_AGENT должен состоять только из цифр!")
    TG_API_ID_AGENT = 0

SESSION_DIR = Path("workspace/_data/telegram_sessions")
SESSION_DIR.mkdir(parents=True, exist_ok=True)

TG_AGENT_SESSION_NAME = config.telegram.agent_session_name

# Формируем полный путь к файлу сессии
session_path = os.path.join(SESSION_DIR, TG_AGENT_SESSION_NAME)

agent_client = TelegramClient(session_path, TG_API_ID_AGENT, TG_API_HASH_AGENT)