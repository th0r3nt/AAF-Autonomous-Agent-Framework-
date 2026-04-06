import asyncio
from pathlib import Path
from imap_tools import MailBox, A, MailMessageFlags

from src.l00_utils.managers.logger import system_logger
from src.l00_utils._tools import clean_html_to_md
from src.l03_interfaces.type.base import BaseInstrument
from src.l03_interfaces.type.email.client import EmailClient
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill

# Определяем путь к папке загрузок
current_dir = Path(__file__).resolve()
src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
project_root = src_dir.parent if src_dir else current_dir.parents[4]

DOWNLOADS_DIR = project_root / "agent" / "sandbox" / "email_downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


class EmailReader(BaseInstrument):
    """Сервис для чтения почты, поиска писем и загрузки вложений."""

    def __init__(self, client: EmailClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.server = client.imap_server
        self.port = client.imap_port
        self.user = client.email_address
        self.password = client.email_password

    # ==========================================
    # ВНУТРЕННИЕ СИНХРОННЫЕ ФУНКЦИИ (ДЛЯ ПОТОКОВ)
    # ==========================================

    def _sync_get_recent(self, limit: int, unread_only: bool) -> ToolResult:
        try:
            with MailBox(self.server, port=self.port).login(self.user, self.password) as mailbox:
                criteria = A(seen=False) if unread_only else A(all=True)

                emails = []
                raw_data = []
                for msg in mailbox.fetch(criteria, limit=limit, reverse=True):
                    attach_count = len(msg.attachments)
                    attach_str = f" | Вложений: {attach_count}" if attach_count > 0 else ""

                    emails.append(
                        f"UID: {msg.uid} | [{msg.date.strftime('%Y-%m-%d %H:%M')}]\n"
                        f"От: {msg.from_}\n"
                        f"Тема: {msg.subject or 'Без темы'}{attach_str}\n"
                        f"{'-'*30}"
                    )
                    raw_data.append(
                        {
                            "uid": msg.uid,
                            "subject": msg.subject,
                            "from": msg.from_,
                            "date": str(msg.date),
                        }
                    )

                if not emails:
                    return ToolResult.fail(msg="Писем не найдено.")

                status = "НЕПРОЧИТАННЫЕ" if unread_only else "ПОСЛЕДНИЕ"
                return ToolResult.ok(
                    msg=f"--- {status} ПИСЬМА ({len(emails)} шт.) ---\n" + "\n".join(emails),
                    data=raw_data,
                )
        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка IMAP: {e}", error=str(e))

    def _sync_read_email(self, uid: str) -> ToolResult:
        """
        Синхронно читает почту.
        """
        try:
            with MailBox(self.server, port=self.port).login(self.user, self.password) as mailbox:
                for msg in mailbox.fetch(A(uid=uid)):
                    raw_text = clean_html_to_md(msg.html) if msg.html else msg.text

                    if not raw_text.strip():
                        raw_text = "*Письмо пустое или содержит только медиафайлы.*"

                    max_len = 20000
                    if len(raw_text) > max_len:
                        raw_text = (
                            raw_text[:max_len]
                            + f"\n\n...[ПИСЬМО ОБРЕЗАНО: ПРЕВЫШЕН СИСТЕМНЫЙ ЛИМИТ В {max_len} СИМВОЛОВ]..."
                        )

                    attachments = []
                    for att in msg.attachments:
                        size_kb = len(att.payload) / 1024
                        attachments.append(f"- {att.filename} ({size_kb:.1f} KB)")

                    attach_str = (
                        "\n--- ВЛОЖЕНИЯ ---\n" + "\n".join(attachments) if attachments else ""
                    )

                    res_msg = (
                        f"--- ПИСЬМО UID: {uid} ---\n"
                        f"От: {msg.from_}\n"
                        f"Кому: {', '.join(msg.to)}\n"
                        f"Дата: {msg.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"Тема: {msg.subject or 'Без темы'}\n"
                        f"--- ТЕКСТ ---\n"
                        f"{raw_text.strip()}\n"
                        f"{attach_str}"
                    )
                    return ToolResult.ok(
                        msg=res_msg,
                        data={"uid": uid, "subject": msg.subject, "from": msg.from_},
                    )
                return ToolResult.fail(msg=f"Письмо с UID {uid} не найдено.")
        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка IMAP: {e}", error=str(e))

    def _sync_download_attachment(self, uid: str, filename: str) -> ToolResult:
        """
        Синхронно скачивает вложение.
        """
        try:
            with MailBox(self.server, port=self.port).login(self.user, self.password) as mailbox:
                for msg in mailbox.fetch(A(uid=uid)):
                    for att in msg.attachments:
                        if att.filename == filename:
                            safe_name = "".join(
                                [c for c in filename if c.isalpha() or c.isdigit() or c in " ._-"]
                            ).rstrip()
                            if not safe_name:
                                safe_name = "unnamed_attachment.bin"

                            file_path = DOWNLOADS_DIR / safe_name
                            with open(file_path, "wb") as f:
                                f.write(att.payload)

                            system_logger.info(f"[Email] Вложение скачано: {file_path}")
                            return ToolResult.ok(
                                msg=f"Вложение успешно сохранено в песочницу.\nПуть для дальнейшей работы: {file_path}",
                                data={"path": str(file_path)},
                            )

                    return ToolResult.fail(
                        msg=f"Вложение с именем '{filename}' не найдено в письме UID {uid}."
                    )
                return ToolResult.fail(msg=f"Письмо с UID {uid} не найдено.")
        except Exception as e:
            system_logger.error(f"[Email] Ошибка скачивания вложения: {e}")
            return ToolResult.fail(msg=f"Ошибка при скачивании: {e}", error=str(e))

    def _sync_change_status(self, uid: str, is_read: bool) -> ToolResult:
        """
        Помечает письмо прочитанным (True) или непрочитанным (False).
        """
        try:
            with MailBox(self.server, port=self.port).login(self.user, self.password) as mailbox:
                mailbox.flag(uid, MailMessageFlags.SEEN, is_read)
                status = "прочитанным" if is_read else "непрочитанным"
                return ToolResult.ok(msg=f"Письмо UID {uid} успешно помечено {status}.")
        except Exception as e:
            return ToolResult.fail(msg=f"Ошибка изменения статуса: {e}", error=str(e))

    # ==========================================
    # АСИНХРОННЫЕ ФАСАДЫ
    # ==========================================

    @skill()
    async def get_recent_emails(self, limit: int = 5, unread_only: bool = False) -> ToolResult:
        """
        Получает список последних писем (сводку).
        Полезно для оценки ситуации в почтовом ящике.
        """
        return await asyncio.to_thread(self._sync_get_recent, limit, unread_only)

    @skill()
    async def read_email(self, uid: str) -> ToolResult:
        """
        Открывает конкретное письмо по UID и читает его полное содержимое.
        """
        return await asyncio.to_thread(self._sync_read_email, uid)

    @skill()
    async def download_attachment(self, uid: str, filename: str) -> ToolResult:
        """
        Скачивает прикрепленный файл из письма в папку Sandbox.
        """
        return await asyncio.to_thread(self._sync_download_attachment, uid, filename)

    @skill()
    async def mark_email_read(self, uid: str) -> ToolResult:
        """
        Помечает письмо прочитанным, чтобы оно больше не светилось как новое.
        """
        return await asyncio.to_thread(self._sync_change_status, uid, True)

    @skill()
    async def mark_email_unread(self, uid: str) -> ToolResult:
        """
        Помечает письмо непрочитанным.
        """
        return await asyncio.to_thread(self._sync_change_status, uid, False)
