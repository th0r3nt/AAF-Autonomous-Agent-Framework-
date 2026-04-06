from datetime import datetime
from typing import Any, Optional
from sqlalchemy import String, DateTime, func, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from src.l01_databases.sql.db import Base


# ----------------------------------------------------------------------------------------------
# Таблица, куда агент может записывать все долгосрочные задачи, которые нужно выполнить


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_description: Mapped[str] = mapped_column(String(3000))  # Описание задачи
    status: Mapped[str] = mapped_column(String(30), default="pending")  # Статус задачи
    term: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Срок или периодичность
    context: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Рабочие заметки агента (когда выполнено, прогресс и т.д.)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self):
        return f"<Task(id={self.id}, term='{self.term}', status='{self.status}')>"

    # __repr__ - это магический метод в Python, сокращение от representation (представление).
    # Он определяет, как будет выглядеть объект, когда выводят его на экран через print(), смотрят на него в консоли или когда он попадает в логи.


# ----------------------------------------------------------------------------------------------
# Таблица состояния сущностей


class MentalStateEntity(Base):
    __tablename__ = "mental_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)  # Имя сущности

    # subject, object, artifact, system
    category: Mapped[str] = mapped_column(String(100), default="subject")
    # critical, high, medium, low
    tier: Mapped[str] = mapped_column(String(20), default="medium")

    # Жесткие текстовые колонки
    description: Mapped[str] = mapped_column(String(2000))  # Фундаментальное описание
    status: Mapped[str] = mapped_column(Text, default="Неизвестно")
    context: Mapped[str] = mapped_column(Text, default="[Нет]")

    # Гибкое досье (JSON) для связей, аккаунтов, предпочтений и алиасов
    related_information: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<MentalStateEntity(name='{self.name}', cat='{self.category}', tier='{self.tier}')>"


# ----------------------------------------------------------------------------------------------
# Таблица для хранения приобретенных черт характера главного агента


class PersonalityTrait(Base):
    __tablename__ = "personality_traits"

    id: Mapped[int] = mapped_column(primary_key=True)
    trait: Mapped[str] = mapped_column(
        String(1000)
    )  # Само правило (например: "Игнорируй глупые вопросы")
    reason: Mapped[str] = mapped_column(String(1000))  # Причина (почему агент это решил)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self):
        return f"<PersonalityTrait(id={self.id}, trait='{self.trait[:30]}...')>"


# ----------------------------------------------------------------------------------------------
# Таблица, в которой хранится история "тиков" агента: цикла ReAct.
# Каждый тик состоит из:
# 1. Мыслей агента при текущем цикле (как он пришел к выводу и действиям);
# 2. Вызываемых  функций;
# 3. Результатов вызова функций.


class AgentTick(Base):
    __tablename__ = "agent_ticks"

    id: Mapped[int] = mapped_column(primary_key=True)

    # UUID события из RabbitMQ (nullable=True на случай, если тик инициирован не внешним событием)
    trigger_event_id: Mapped[Optional[str]] = mapped_column(
        String(36), index=True, nullable=True
    )

    # Статус обработки: 'processing', 'success', 'failed'
    status: Mapped[str] = mapped_column(String(20), default="processing", index=True)

    # Сюда запишем traceback, если докер или LLM упали с ошибкой
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Мысли агента
    thoughts: Mapped[str] = mapped_column(Text, default="")

    # Вызываемые функции
    called_functions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    # Результаты вызова функций
    function_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    def __repr__(self):
        return f"<AgentTick(id={self.id}, status='{self.status}', event_id='{self.trigger_event_id}')>"


# ----------------------------------------------------------------------------------------------


class ScheduledEvent(Base):
    __tablename__ = "scheduled_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_type: Mapped[str] = mapped_column(String(20))  # "timer" или "cron"

    # Время, когда задача должна сработать
    execution_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Крон-выражение (только для task_type="cron")
    cron_expression: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Заметка/задача, которую агент написал сам себе
    note: Mapped[str] = mapped_column(Text)

    # "pending", "completed", "cancelled"
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self):
        return f"<ScheduledEvent(id={self.id}, type='{self.task_type}', time='{self.execution_time}', status='{self.status}')>"
