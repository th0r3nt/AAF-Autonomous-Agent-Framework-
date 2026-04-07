import os
import asyncio
import smtplib
from pathlib import Path
from collections import deque
from imap_tools import MailBox, errors
from dotenv import load_dotenv

from src.l00_utils.managers.logger import system_logger

from src.l00_utils.managers.event_bus import EventBus

# Родители
from src.l03_interfaces.type.base import BaseClient

# Поллинг
from src.l03_interfaces.type.email.events import EmailEvents

# Инструменты
from src.l03_interfaces.type.email.instruments.reader import EmailReader
from src.l03_interfaces.type.email.instruments.sender import EmailSender

load_dotenv()


class EmailClient(BaseClient):
    """Клиент для работы агента с электронной почтой (IMAP/SMTP)."""

    name = "email"  # Имя для маппинга

    def __init__(self, event_bus: EventBus, sandbox_dir: Path):
        self.event_bus = event_bus

        self.sandbox_dir = sandbox_dir

        self.email_address = os.getenv("EMAIL_ADDRESS")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.imap_server = os.getenv("EMAIL_IMAP_SERVER")
        self.imap_port = int(os.getenv("EMAIL_IMAP_PORT", 993))
        self.smtp_server = os.getenv("EMAIL_SMTP_SERVER")
        self.smtp_port = int(os.getenv("EMAIL_SMTP_PORT", 465))

        self.is_ready = all(
            [self.email_address, self.email_password, self.imap_server, self.smtp_server]
        )

        if not self.is_ready:
            system_logger.warning("[Email] Неполные данные в .env. Интерфейс отключен.")

        self.recent_activity = deque(maxlen=50)

    def register_instruments(self):
        EmailReader(self)
        EmailSender(self, sandbox_dir=self.sandbox_dir)
        system_logger.debug("[Email] Инструменты успешно зарегистрированы.")

    async def start_background_polling(self) -> None:
        events = EmailEvents(event_bus=self.event_bus, client=self)
        events.start_polling()

    def get_passive_context(self) -> dict:
        status = "🟢 ONLINE" if self.is_ready else "🔴 OFFLINE"
        return {
            "name": "email",
            "status": status,
            "recent_activity": list(self.recent_activity),
        }

    async def check_connection(self) -> bool:
        if not self.is_ready:
            return False
        system_logger.debug("[Email] Проверка подключения к серверам.")
        imap_ok, smtp_ok = await asyncio.gather(
            asyncio.to_thread(self._sync_check_imap),
            asyncio.to_thread(self._sync_check_smtp),
        )
        if imap_ok and smtp_ok:
            system_logger.info(f"[Email] Подключение успешно. Ящик: {self.email_address}")
            return True
        self.is_ready = False
        return False

    async def close(self):
        pass

    def _sync_check_imap(self) -> bool:
        try:
            with MailBox(self.imap_server, port=self.imap_port).login(
                self.email_address, self.email_password
            ):
                return True

        except errors.MailboxLoginError:
            system_logger.error("[Email IMAP] Ошибка авторизации: Неверный логин или пароль.")
            return False

        except Exception:
            return False

    def _sync_check_smtp(self) -> bool:
        try:
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
                server.starttls()
            server.login(self.email_address, self.email_password)
            server.quit()
            return True
        except smtplib.SMTPAuthenticationError:
            system_logger.error("[Email SMTP] Ошибка авторизации SMTP.")
            return False
        except Exception:
            return False
