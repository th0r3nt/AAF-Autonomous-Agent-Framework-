import asyncio
from cachetools import LRUCache
from imap_tools import MailBox, A

from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.event.registry import Events
from src.l00_utils._tools import clean_html_to_md

from src.l03_interfaces.type.email.client import EmailClient


class EmailEvents:
    def __init__(self, event_bus: EventBus, client: EmailClient):
        self.event_bus = event_bus
        self.client = client

        self.PROCESSED_EMAILS = LRUCache(
            maxsize=1000
        )  # Кэш для UID обработанных писем, чтобы не кидать их в шину дважды

    def _sync_fetch_unread(self):
        """
        Синхронная блокирующая функция для парсинга новых писем.
        """
        new_emails = []
        try:
            with MailBox(self.client.imap_server, port=self.client.imap_port).login(
                self.client.email_address, self.client.email_password
            ) as mailbox:

                # Ищем непрочитанные письма (UNSEEN).
                # mark_seen=False означает, что мы не помечаем их прочитанными на сервере,
                # чтобы агент мог потом сам это сделать через инструменты, если захочет
                for msg in mailbox.fetch(A(seen=False), mark_seen=False, limit=10, reverse=True):
                    if msg.uid in self.PROCESSED_EMAILS:
                        continue

                    self.PROCESSED_EMAILS[msg.uid] = True

                    # Достаем текст. Если есть HTML - чистим его в Markdown, иначе берем сырой текст
                    raw_text = clean_html_to_md(msg.html) if msg.html else msg.text

                    # Ограничиваем длину письма для шины событий, чтобы не взорвать контекст LLM
                    # (Полное письмо агент сможет прочитать позже через инструмент)
                    snippet = raw_text.strip()
                    if len(snippet) > 800:
                        snippet = snippet[:797] + "... [ОБРЕЗАНО]"

                    # Собираем инфу о вложениях (названия файлов)
                    attachments = [att.filename for att in msg.attachments if att.filename]
                    attach_str = f"\n[Вложения: {', '.join(attachments)}]" if attachments else ""

                    new_emails.append(
                        {
                            "uid": msg.uid,
                            "sender": msg.from_,
                            "subject": msg.subject or "Без темы",
                            "snippet": snippet + attach_str,
                            "date": msg.date.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )

        except Exception as e:
            system_logger.error(f"[Email Polling] Ошибка при чтении ящика: {e}")

        return new_emails

    async def email_event_loop(self, interval_seconds: int = 180):
        """
        Бесконечный цикл поллинга новых писем.
        Проверяем почту раз в 3 минуты (180 секунд).
        """
        system_logger.info(f"[Email] Запуск фонового поллинга (интервал: {interval_seconds} сек.)")

        if not await self.client.check_connection():
            system_logger.warning("[Email] Агент не авторизован. Поллинг отменен.")
            return

        while True:
            try:
                # Запускаем тяжелый парсинг писем в фоне, не блокируя Event Loop
                new_emails = await asyncio.to_thread(self._sync_fetch_unread)

                for email in new_emails:
                    system_logger.info(
                        f"[Email] Новое письмо от {email['sender']}: {email['subject']}"
                    )

                    log_str = f"[{email['date']}] letter from {email['sender']}: {email['subject']}"
                    self.client.recent_activity.append(log_str)

                    await self.event_bus.publish(
                        Events.EMAIL_MESSAGE_INCOMING,
                        uid=email["uid"],
                        sender=email["sender"],
                        subject=email["subject"],
                        snippet=email["snippet"],
                        date=email["date"],
                    )

            except Exception as e:
                system_logger.error(f"[Email Polling] Критическая ошибка в цикле: {e}")

            await asyncio.sleep(interval_seconds)

    def start_polling(self):
        """Синхронная обертка для менеджера интерфейсов."""
        asyncio.create_task(self.email_event_loop())
