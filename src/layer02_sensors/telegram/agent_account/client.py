import os
from telethon import TelegramClient
from dotenv import load_dotenv
from pathlib import Path
from config.config_manager import config

load_dotenv()

TG_API_ID_AGENT = int(os.getenv("TG_API_ID_AGENT"))
TG_API_HASH_AGENT = os.getenv("TG_API_HASH_AGENT")

SESSION_DIR = Path("src/layer00_utils/telegram_sessions")
SESSION_DIR.mkdir(parents=True, exist_ok=True) # parents=True создаст всю цепочку папок, если нужно

TG_AGENT_SESSION_NAME = config.telegram.agent_session_name

# Формируем полный путь к файлу сессии
session_path = os.path.join(SESSION_DIR, TG_AGENT_SESSION_NAME)

agent_client = TelegramClient(session_path, TG_API_ID_AGENT, TG_API_HASH_AGENT)