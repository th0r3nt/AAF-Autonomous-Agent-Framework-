import smtplib
import asyncio
from pathlib import Path
from email.message import EmailMessage
from imap_tools import MailBox, A

from src.l03_interfaces.type.base import BaseInstrument
from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.email.client import EmailClient
from src.l03_interfaces.models import ToolResult

from src.l04_agency.skills.registry import skill


class EmailSender(BaseInstrument):
    """Сервис для отправки и ответа на электронные письма."""

    def __init__(self, client: EmailClient, sandbox_dir: str):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.smtp_server = client.smtp_server
        self.smtp_port = client.smtp_port

        self.imap_server = client.imap_server
        self.imap_port = client.imap_port

        self.user = client.email_address
        self.password = client.email_password

        self.sandbox_dir = sandbox_dir

    # ==========================================
    # ВНУТРЕННИЕ СИНХРОННЫЕ ФУНКЦИИ
    # ==========================================

    def _sync_send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        attachments: list[str] = None,
        reply_to_uid: str = None,
    ) -> ToolResult:
        """
        Синхронная функция отправки письма.
        Умеет прикреплять файлы и отвечать в тред (если передан reply_to_uid).
        """
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.user
        msg["To"] = to_email
        msg.set_content(body)

        # Если это ответ на письмо (Reply), нужно подставить правильные заголовки
        if reply_to_uid:
            try:
                # Подключаемся по IMAP, чтобы вытащить Message-ID оригинального письма
                with MailBox(self.imap_server, port=self.imap_port).login(
                    self.user, self.password
                ) as mailbox:
                    for orig_msg in mailbox.fetch(A(uid=reply_to_uid)):
                        orig_message_id = orig_msg.headers.get("message-id", [""])[0]
                        orig_references = orig_msg.headers.get("references", [""])[0]

                        if orig_message_id:
                            msg["In-Reply-To"] = orig_message_id

                            # Формируем цепочку ответов (References)
                            if orig_references:
                                msg["References"] = f"{orig_references} {orig_message_id}"
                            else:
                                msg["References"] = orig_message_id

                            # Добавляем "Re: " к теме, если агент забыл это сделать
                            if not subject.lower().startswith("re:"):
                                msg.replace_header("Subject", f"Re: {orig_msg.subject}")

                            # Важно: берем адрес отправителя оригинала, если мы не знаем точного To
                            if not to_email:
                                msg.replace_header("To", orig_msg.from_)

            except Exception as e:
                system_logger.error(
                    f"[Email Sender] Не удалось вытащить Message-ID для ответа: {e}"
                )
                return ToolResult.fail(
                    msg=f"Ошибка при попытке ответить на письмо (UID {reply_to_uid}): {e}",
                    error=str(e),
                )

        # Обработка вложений (если агент передал список путей)
        if attachments:
            for filepath in attachments:
                # Безопасность: Разрешаем брать файлы только из папки sandbox/
                try:
                    # Превращаем путь в абсолютный и проверяем, лежит ли он внутри SANDBOX_DIR
                    abs_path = Path(filepath).resolve()
                    if not str(abs_path).startswith(str(self.sandbox_dir)):
                        system_logger.warning(
                            f"[Email Sender] Попытка прикрепить файл вне песочницы: {filepath}"
                        )
                        return ToolResult.fail(
                            msg="Ошибка безопасности: Разрешено прикреплять файлы только из директории sandbox/."
                        )

                    if not abs_path.exists() or not abs_path.is_file():
                        return ToolResult.fail(
                            msg=f"Ошибка: Файл '{filepath}' не найден или это директория."
                        )

                    # Читаем бинарно и прикрепляем
                    with open(abs_path, "rb") as f:
                        file_data = f.read()

                    # Определяем имя файла
                    file_name = abs_path.name

                    # Простой способ прикрепить файл без сложного определения MIME-типа (определится как application/octet-stream)
                    msg.add_attachment(
                        file_data,
                        maintype="application",
                        subtype="octet-stream",
                        filename=file_name,
                    )

                except Exception as e:
                    system_logger.error(f"[Email Sender] Ошибка прикрепления файла {filepath}: {e}")
                    return ToolResult.fail(
                        msg=f"Ошибка при обработке вложения '{filepath}': {e}",
                        error=str(e),
                    )

        # Отправка через SMTP
        try:
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
                server.starttls()

            server.login(self.user, self.password)
            server.send_message(msg)
            server.quit()

            action = "Ответ на письмо" if reply_to_uid else "Письмо"
            attach_info = f" (Вложений: {len(attachments)})" if attachments else ""

            system_logger.info(
                f"[Email Sender] {action} успешно отправлено на {msg['To']}{attach_info}."
            )
            return ToolResult.ok(
                msg=f"{action} успешно отправлено на адрес {msg['To']}.",
                data={"to": str(msg["To"]), "subject": str(msg["Subject"])},
            )

        except smtplib.SMTPAuthenticationError:
            system_logger.error("[Email Sender] Ошибка авторизации SMTP.")
            return ToolResult.fail(
                msg="Ошибка авторизации SMTP (неверный пароль).",
                error="SMTPAuthenticationError",
            )
        except Exception as e:
            system_logger.error(f"[Email Sender] Ошибка отправки: {e}")
            return ToolResult.fail(msg=f"Ошибка при отправке письма: {e}", error=str(e))

    # ==========================================
    # АСИНХРОННЫЕ ФАСАДЫ
    # ==========================================

    @skill()
    async def send_email(
        self, to_email: str, subject: str, body: str, attachments: list[str] = None
    ) -> ToolResult:
        """
        Отправляет новое электронное письмо.
        """
        if not to_email or not subject or not body:
            return ToolResult.fail(
                msg="Ошибка: Для отправки нового письма обязательны параметры to_email, subject и body."
            )

        return await asyncio.to_thread(self._sync_send_email, to_email, subject, body, attachments)

    @skill()
    async def reply_to_email(
        self, uid: str, body: str, attachments: list[str] = None
    ) -> ToolResult:
        """
        Отправляет ответ на существующее письмо (создает красивую цепочку/тред ответов).
        Автоматически берет адрес отправителя и тему из оригинального письма.
        """
        if not uid or not body:
            return ToolResult.fail(msg="Ошибка: Для ответа обязательны параметры uid и body.")

        # Передаем to_email=None и subject="Re:", они перезапишутся автоматически из оригинального письма
        return await asyncio.to_thread(
            self._sync_send_email, None, "Re:", body, attachments, reply_to_uid=uid
        )
