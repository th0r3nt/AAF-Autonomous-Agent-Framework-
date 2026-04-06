from telethon import TelegramClient


class TelethonMedia:
    """Сервис для удобной работы с медиа в Telegram."""

    def __init__(self, client: TelegramClient):
        self.client = client
