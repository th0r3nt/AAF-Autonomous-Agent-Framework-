import os
from collections import deque
import httpx
from dotenv import load_dotenv

from src.l00_utils.managers.event_bus import EventBus
from src.l00_utils.managers.logger import system_logger

# Родители
from src.l03_interfaces.type.base import BaseClient

# Поллинг
from src.l03_interfaces.type.api.github.events import GitHubEvents

# Инструменты
from src.l03_interfaces.type.api.github.instruments.files_and_code import GithubFilesAndCode
from src.l03_interfaces.type.api.github.instruments.issues import GithubIssue
from src.l03_interfaces.type.api.github.instruments.profile import GithubProfile
from src.l03_interfaces.type.api.github.instruments.pull_requests import GithubPullRequest
from src.l03_interfaces.type.api.github.instruments.repositories import GithubRepository

load_dotenv()


class GithubClient(BaseClient):
    """Асинхронный клиент для работы ИИ-агента с GitHub API."""

    name = "github"  # Имя для маппинга

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.token = os.getenv("GITHUB_TOKEN_AGENT")

        if not self.token:
            system_logger.warning(
                "[GitHub] Токен не найден. API будет работать с лимитами (~60 запросов/час)."
            )

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AAF-Agent",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self.client = httpx.AsyncClient(
            base_url="https://api.github.com", headers=headers, timeout=15.0
        )

        self.recent_activity = deque(maxlen=50)

    def register_instruments(self):
        GithubFilesAndCode(self)
        GithubIssue(self)
        GithubProfile(self)
        GithubPullRequest(self)
        GithubRepository(self)
        system_logger.debug("[GitHub] Инструменты успешно зарегистрированы.")

    async def start_background_polling(self) -> None:
        events = GitHubEvents(event_bus=self.event_bus, client=self)
        events.start_polling()

    def get_passive_context(self) -> dict:
        # Указываем LLM, есть ли у нас права на запись
        status = "🟢 ONLINE" if self.token else "🟡 READ-ONLY"
        return {
            "name": "github",
            "status": status,
            "recent_activity": list(self.recent_activity),
        }

    async def check_connection(self) -> bool:
        try:
            if self.token:
                response = await self.client.get("/user")
                if response.status_code == 200:
                    login = response.json().get("login")
                    system_logger.info(
                        f"[GitHub] Авторизация успешна. Агент подключен как: @{login}"
                    )
                    return True
                elif response.status_code == 401:
                    system_logger.error(
                        "[GitHub] Ошибка 401: Неверный или просроченный токен."
                    )
                    return False  # Токен явно битый, лучше вырубить интерфейс и заставить юзера поправить .env
            else:
                # В Read-Only режиме просто пингуем публичный эндпоинт, не требующий токена
                response = await self.client.get("/zen")
                # 403 может быть лимитом (Rate Limit), но API живо
                if response.status_code in [200, 403]:
                    system_logger.info("[GitHub] Анонимное подключение (Read-Only) успешно.")
                    return True

            return True
        except httpx.RequestError as e:
            system_logger.warning(
                f"[GitHub] Скачок сети при старте: {e}. Навыки будут зарегистрированы."
            )
            return True

    async def close(self):
        await self.client.aclose()
        system_logger.info("[GitHub] Сессия клиента закрыта.")
