import random
from telethon import TelegramClient
from telethon.tl.functions.messages import SendVoteRequest
from telethon.tl.types import InputMediaPoll, Poll, PollAnswer, TextWithEntities

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.telegram.telethon.instruments._helpers import clean_peer_id
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class TelethonPolls(BaseInstrument):
    """Сервис для удобной работы с опросами в Telegram."""

    def __init__(self, client: TelegramClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.client = client

    @skill()
    async def create_poll(self, chat_id: str | int, question: str, options: list) -> ToolResult:
        """
        Создает опрос в чате/канале.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            answers = [
                PollAnswer(
                    text=TextWithEntities(text=str(opt), entities=[]),
                    option=str(i).encode("utf-8"),
                )
                for i, opt in enumerate(options)
            ]
            poll_media = InputMediaPoll(
                poll=Poll(
                    id=random.getrandbits(62),
                    question=TextWithEntities(text=question, entities=[]),
                    answers=answers,
                    closed=False,
                    multiple_choice=False,
                    quiz=False,
                )
            )
            msg = await self.client.send_message(chat_id, file=poll_media)

            return ToolResult.ok(msg=f"Опрос '{question}' успешно создан. ID: {msg.id}", data=msg)

        except Exception as e:
            system_logger.error(f"[Telegram Telethon] Ошибка создания опроса в {chat_id}: {e}")
            return ToolResult.fail(msg=f"Ошибка при создании опроса: {e}", error=str(e))

    @skill()
    async def get_poll_results(self, chat_id: str | int, message_id: int) -> ToolResult:
        """
        Получает результаты опроса.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            messages = await self.client.get_messages(chat_id, ids=[message_id])
            if not messages or not getattr(messages[0], "poll", None):
                return ToolResult.fail(msg="Сообщение не найдено или это не опрос.")

            message = messages[0]
            msg_time = message.date.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            poll = message.poll.poll
            results = message.poll.results
            question_text = getattr(poll.question, "text", str(poll.question))
            total_voters = getattr(results, "total_voters", 0)

            if total_voters == 0:
                return ToolResult.ok(
                    msg=f"[{msg_time}] Опрос '{question_text}'. Голосов пока нет.",
                    data=message.poll,
                )

            summary = [
                f"[{msg_time}] Опрос: {question_text}\nВсего голосов: {total_voters}\nРезультаты:"
            ]
            votes_map = (
                {r.option: r.voters for r in results.results}
                if getattr(results, "results", None)
                else {}
            )

            for answer in poll.answers:
                answer_text = getattr(answer.text, "text", str(answer.text))
                count = votes_map.get(answer.option, 0)
                percent = round((count / total_voters) * 100, 1) if total_voters > 0 else 0
                summary.append(f"- {answer_text}: {count} ({percent}%)")

            return ToolResult.ok(msg="\n".join(summary), data=message.poll)

        except Exception as e:
            system_logger.error(
                f"[Telegram Telethon] Ошибка результатов опроса {message_id} в {chat_id}: {e}"
            )
            return ToolResult.fail(msg=f"Ошибка получения результатов опроса: {e}", error=str(e))

    @skill()
    async def vote_in_poll(self, chat_id: str | int, message_id: int, options: list) -> ToolResult:
        """
        Голосует в опросе.
        """
        chat_id = clean_peer_id(chat_id)
        try:
            messages = await self.client.get_messages(chat_id, ids=[message_id])
            if not messages or not messages[0].poll:
                return ToolResult.fail(msg="Ошибка: Сообщение не найдено или это не опрос.")

            poll_answers = messages[0].poll.poll.answers
            options_to_send = []

            for opt in options:
                opt_str = str(opt)
                for answer in poll_answers:
                    if opt_str.lower() in getattr(answer.text, "text", str(answer.text)).lower():
                        options_to_send.append(answer.option)
                        break
                else:
                    if opt_str.isdigit() and int(opt_str) < len(poll_answers):
                        options_to_send.append(poll_answers[int(opt_str)].option)

            if not options_to_send:
                return ToolResult.fail(
                    msg=f"Ошибка: Не удалось найти вариант ответа '{options}' в опросе."
                )

            await self.client(
                SendVoteRequest(peer=chat_id, msg_id=message_id, options=options_to_send)
            )
            return ToolResult.ok(
                msg=f"Голос за вариант(ы) '{options}' успешно отправлен.",
                data=options_to_send,
            )

        except Exception as e:
            system_logger.error(
                f"[Telegram Telethon] Ошибка голосования {message_id} в {chat_id}: {e}"
            )
            return ToolResult.fail(msg=f"Ошибка при голосовании: {e}", error=str(e))
