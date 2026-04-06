from pydantic import BaseModel
from enum import Enum


# ============================================
# ENUMS
# ============================================


class EventLevel(int, Enum):
    CRITICAL = 50
    HIGH = 40
    MEDIUM = 30
    LOW = 20
    BACKGROUND = 10
    INFO = 0


class EventDomain(str, Enum):
    GITHUB = "github"
    REDDIT = "reddit"
    HABR = "habr"
    TELEGRAM = "telegram"
    EMAIL = "email"
    SYSTEM = "system"
    SANDBOX = "sandbox"
    WEB = "web"


class EventEntity(str, Enum):
    MENTION = "mention"
    REPO = "repo"
    MESSAGE = "message"
    COMMENT = "comment"
    GROUP = "group"
    BOT = "bot"
    TIMER = "timer"
    CORE = "core"
    CALENDAR = "calendar"
    SCRIPT = "script"
    HOOK = "hook"
    DEPLOYMENT = "deployment"
    ARTICLE = "article"


class EventAction(str, Enum):
    INCOMING = "incoming"
    ACTIVITY = "activity"
    MENTION = "mention"
    REPLY = "reply"
    REACTION = "reaction"
    MESSAGE = "message"
    CALLBACK = "callback"
    PROACTIVITY = "proactivity"
    CONSOLIDATION = "consolidation"
    START = "start"
    STOP = "stop"
    ALARM = "alarm"
    NOTIFICATION = "notification"
    CRASH = "crash"


# ============================================
# МОДЕЛЬ КОНФИГА СОБЫТИЯ
# ============================================


class EventConfig(BaseModel):
    description: str
    domain: EventDomain
    entity: EventEntity
    action: EventAction
    level: EventLevel
    requires_attention: bool = True

    @property
    def name(self) -> str:
        """
        Автогенерация имени (например: GITHUB_MESSAGE_INCOMING)
        Берет названия атрибутов из Enum (капсом).
        """
        return f"{self.domain.name}_{self.entity.name}_{self.action.name}"

    @property
    def routing_key(self) -> str:
        """
        Автогенерация строки для RabbitMQ (например: github.message.incoming.high)
        Берет значения атрибутов из Enum (строчные).
        """
        return f"{self.domain.value}.{self.entity.value}.{self.action.value}.{self.level.name.lower()}"

    def __str__(self):
        return self.name


# ============================================
# РЕЕСТР СОБЫТИЙ
# ============================================


class Events:

    # --------------------------------------------
    # GitHub
    # --------------------------------------------

    GITHUB_MENTION_INCOMING = EventConfig(
        description="Упоминание в GitHub.",
        domain=EventDomain.GITHUB,
        entity=EventEntity.MENTION,
        action=EventAction.INCOMING,
        level=EventLevel.HIGH,
    )

    GITHUB_REPO_ACTIVITY = EventConfig(
        description="Активность в отслеживаемом репозитории.",
        domain=EventDomain.GITHUB,
        entity=EventEntity.REPO,
        action=EventAction.ACTIVITY,
        level=EventLevel.BACKGROUND,
    )

    # --------------------------------------------
    # Reddit
    # --------------------------------------------

    REDDIT_MESSAGE_INCOMING = EventConfig(
        description="Входящее сообщение в Reddit.",
        domain=EventDomain.REDDIT,
        entity=EventEntity.MESSAGE,
        action=EventAction.INCOMING,
        level=EventLevel.HIGH,
    )

    REDDIT_COMMENT_MENTION = EventConfig(
        description="Упоминание в Reddit комментарии/посте.",
        domain=EventDomain.REDDIT,
        entity=EventEntity.COMMENT,
        action=EventAction.MENTION,
        level=EventLevel.HIGH,
    )

    REDDIT_COMMENT_REPLY = EventConfig(
        description="Ответ на комментарий в Reddit.",
        domain=EventDomain.REDDIT,
        entity=EventEntity.COMMENT,
        action=EventAction.REPLY,
        level=EventLevel.MEDIUM,
    )

    # --------------------------------------------
    # Habr
    # --------------------------------------------

    HABR_MENTION_INCOMING = EventConfig(
        description="Упоминание на Хабре.",
        domain=EventDomain.HABR,
        entity=EventEntity.MENTION,
        action=EventAction.INCOMING,
        level=EventLevel.HIGH,
    )

    HABR_COMMENT_REPLY = EventConfig(
        description="Ответ на комментарий на Хабре.",
        domain=EventDomain.HABR,
        entity=EventEntity.COMMENT,
        action=EventAction.REPLY,
        level=EventLevel.MEDIUM,
    )

    HABR_ARTICLE_PUBLISHED = EventConfig(
        description="Вышла новая статья в отслеживаемом хабе на Хабре.",
        domain=EventDomain.HABR,
        entity=EventEntity.ARTICLE,
        action=EventAction.INCOMING,
        level=EventLevel.BACKGROUND,  # Это фоновый шум, агент почитает, когда будет проактивен
    )

    # --------------------------------------------
    # Telegram
    # --------------------------------------------

    TELEGRAM_MESSAGE_INCOMING = EventConfig(
        description="Входящее сообщение в Telegram.",
        domain=EventDomain.TELEGRAM,
        entity=EventEntity.MESSAGE,
        action=EventAction.INCOMING,
        level=EventLevel.HIGH,
    )

    TELEGRAM_GROUP_MENTION = EventConfig(
        description="Упоминание в Telegram.",
        domain=EventDomain.TELEGRAM,
        entity=EventEntity.GROUP,
        action=EventAction.MENTION,
        level=EventLevel.MEDIUM,
    )

    TELEGRAM_MESSAGE_REACTION = EventConfig(
        description="Входящее эмодзи-реакция на сообщение в Telegram.",
        domain=EventDomain.TELEGRAM,
        entity=EventEntity.MESSAGE,
        action=EventAction.REACTION,
        level=EventLevel.LOW,
    )

    TELEGRAM_GROUP_MESSAGE = EventConfig(
        description="Обычное сообщение в чате.",
        domain=EventDomain.TELEGRAM,
        entity=EventEntity.GROUP,
        action=EventAction.MESSAGE,
        level=EventLevel.BACKGROUND,
    )

    TELEGRAM_BOT_CALLBACK = EventConfig(
        description="Пользователь нажал на Inline-кнопку в интерфейсе бота.",
        domain=EventDomain.TELEGRAM,
        entity=EventEntity.BOT,
        action=EventAction.CALLBACK,
        level=EventLevel.HIGH,
    )

    # --------------------------------------------
    # Email
    # --------------------------------------------

    EMAIL_MESSAGE_INCOMING = EventConfig(
        description="Входящее письмо на электронной почте.",
        domain=EventDomain.EMAIL,
        entity=EventEntity.MESSAGE,
        action=EventAction.INCOMING,
        level=EventLevel.HIGH,
    )

    # --------------------------------------------
    # Общие системные события
    # --------------------------------------------

    SYSTEM_TIMER_PROACTIVITY = EventConfig(
        description="Сработал внутренний таймер проактивности.",
        domain=EventDomain.SYSTEM,
        entity=EventEntity.TIMER,
        action=EventAction.PROACTIVITY,
        level=EventLevel.BACKGROUND,
    )

    SYSTEM_TIMER_CONSOLIDATION = EventConfig(
        description="Сработал внутренний таймер консолидации.",
        domain=EventDomain.SYSTEM,
        entity=EventEntity.TIMER,
        action=EventAction.CONSOLIDATION,
        level=EventLevel.BACKGROUND,
    )

    SYSTEM_CORE_START = EventConfig(
        description="Запуск всей системы.",
        domain=EventDomain.SYSTEM,
        entity=EventEntity.CORE,
        action=EventAction.START,
        level=EventLevel.HIGH,
    )

    SYSTEM_CORE_STOP = EventConfig(
        description="Отключение всей системы.",
        domain=EventDomain.SYSTEM,
        entity=EventEntity.CORE,
        action=EventAction.STOP,
        level=EventLevel.HIGH,
        requires_attention=False,
    )

    SYSTEM_CALENDAR_ALARM = EventConfig(
        description="Сработал таймер или регулярная задача из календаря.",
        domain=EventDomain.SYSTEM,
        entity=EventEntity.CALENDAR,
        action=EventAction.ALARM,
        level=EventLevel.MEDIUM,
    )

    # --------------------------------------------
    # Sandbox & Web
    # --------------------------------------------

    SANDBOX_SCRIPT_NOTIFICATION = EventConfig(
        description="Скрипт из Sandbox прислал уведомление.",
        domain=EventDomain.SANDBOX,
        entity=EventEntity.SCRIPT,
        action=EventAction.NOTIFICATION,
        level=EventLevel.HIGH,
    )

    WEB_HOOK_INCOMING = EventConfig(
        description="Внешняя система прислала данные на Webhook.",
        domain=EventDomain.WEB,
        entity=EventEntity.HOOK,
        action=EventAction.INCOMING,
        level=EventLevel.HIGH,
    )

    SANDBOX_DEPLOYMENT_CRASH = EventConfig(
        description="Запущенный микросервис упал с ошибкой.",
        domain=EventDomain.SANDBOX,
        entity=EventEntity.DEPLOYMENT,
        action=EventAction.CRASH,
        level=EventLevel.CRITICAL,
    )

    @classmethod
    def all(cls) -> list[EventConfig]:
        """Возвращает список всех зарегистрированных событий."""
        events = []
        for attr_name, attr_value in vars(cls).items():
            if isinstance(attr_value, EventConfig):
                events.append(attr_value)
        return events


ALL_EVENTS = Events.all()
