import datetime
from typing import Any, Optional
from sqlalchemy import String, DateTime, func, Text 
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.layer01_datastate.sql_db.sql_db import Base

# ----------------------------------------------------------------------------------------------
# Таблица, в которой хранится история всех действий агента

class AgentAction(Base):
    __tablename__ = "agent_actions"

    id: Mapped[int] = mapped_column(primary_key=True) # primary_key=True означает, что это поле будет уникальным идентификатором для каждой записи в таблице
    action_type: Mapped[str] = mapped_column(String(100)) # Что сделал (какую функцию вызвал). Например: "add_entry_in_db", "send_tg_message", "read_tg_chat" и т.д.
    # String(...) - это тип данных и максимальная длина строки. Если мы попытаемся записать строку длиннее n символов, база данных выдаст ошибку
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)  # Детали действия (например, если действие - "отправил сообщение в Telegram", то в details может быть {"username": "ivan123", "text": "Привет!"})
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    ) # Время создания. func.now() использует время сервера БД
    def __repr__(self):
        return f"<AgentAction(id={self.id}, created_at={self.created_at})>"
    
    # __repr__ - это магический метод в Python, сокращение от representation (представление). 
    # Он определяет, как будет выглядеть ваш объект, когда вы выводите его на экран через print(), смотрите в консоли или когда он попадает в логи.

# ----------------------------------------------------------------------------------------------
# Таблица, в которую записывается история диалогов пользователя с агентом

class Dialogue(Base):
    __tablename__ = "dialogue"

    id: Mapped[int] = mapped_column(primary_key=True) # Уникальный идентификатор для каждой записи в таблице
    actor: Mapped[str] = mapped_column(String(50))    # Кто говорит (user, agent, кто угодно)
    message: Mapped[str] = mapped_column(Text)        # Содержание сообщения
    source: Mapped[str] = mapped_column(String(100))  # Откуда пришло сообщение. Например: "telegram", "web", "terminal"
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    def __repr__(self):
        return f"<Dialogue(id={self.id}, actor='{self.actor}', message='{self.message[:50]}...')>"

# ----------------------------------------------------------------------------------------------
# Таблица, куда агент может записывать все долгосрочные задачи, которые нужно выполнить

class LongTermTask(Base):
    __tablename__ = "long-term_tasks"

    id: Mapped[int] = mapped_column(primary_key=True) 
    task_description: Mapped[str] = mapped_column(String(3000))             # Описание задачи
    status: Mapped[str] = mapped_column(String(30), default="pending")      # Статус задачи
    term: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # Срок или периодичность
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)     # Рабочие заметки агента (когда выполнено, прогресс и т.д.)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    def __repr__(self):
        return f"<LongTermTasks(id={self.id}, term='{self.term}', status='{self.status}')>"

# ----------------------------------------------------------------------------------------------
# Таблица состояния разных сущностей

class MentalStateEntity(Base):
    __tablename__ = "mental_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True) # Имя сущности
    
    # Новые поля для сортировки памяти
    category: Mapped[str] = mapped_column(String(50), default="subject") # subject, place, artifact, system
    tier: Mapped[str] = mapped_column(String(20), default="medium")      # critical, high, medium, low
    
    description: Mapped[str] = mapped_column(String(1000)) # Фундаментальное описание
    
    # Специально делаем жесткие колонки вместор JSONB
    # Используем Text, чтобы не ограничивать длину (особенно для context)
    status: Mapped[str] = mapped_column(Text, default="Неизвестно")
    context: Mapped[str] = mapped_column(Text, default="[Нет]")
    rules: Mapped[str] = mapped_column(Text, default="[Нет]") 
    
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<MentalStateEntity(name='{self.name}', cat='{self.category}', tier='{self.tier}')>"
    
# ----------------------------------------------------------------------------------------------
# Таблица для хранения приобретенных черт характера главного агента

class PersonalityTrait(Base):
    __tablename__ = "personality_traits"

    id: Mapped[int] = mapped_column(primary_key=True)
    trait: Mapped[str] = mapped_column(String(500))  # Само правило (например: "Игнорируй глупые вопросы")
    reason: Mapped[str] = mapped_column(String(1000)) # Причина (почему агент это решил)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self):
        return f"<PersonalityTrait(id={self.id}, trait='{self.trait[:30]}...')>"
    

# ----------------------------------------------------------------------------------------------
# Таблица для хранения состояния субагентов (Swarm System 2.0)

class SubagentState(Base):
    __tablename__ = "swarm_subagents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)          # Имя субагента (уникальное)
    role: Mapped[str] = mapped_column(String(50))                        # 'Researcher', 'WebMonitor' и т.д.
    instructions: Mapped[str] = mapped_column(Text)                      # Инструкция от главного агента
    
    # Специфично для Демонов
    trigger_condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True) 
    interval_sec: Mapped[Optional[int]] = mapped_column(nullable=True)   
    
    # Состояние
    status: Mapped[str] = mapped_column(String(50), default="running")   # running, sleeping, completed, killed, error
    memory_state: Mapped[dict] = mapped_column(JSONB, default=dict)      # JSON-блокнот (ключ-значение)

    parent_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # Корень цепочки (кто всё начал)
    chain_depth: Mapped[int] = mapped_column(default=0)                            # Глубина цепочки
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<SubagentState(name='{self.name}', role='{self.role}', status='{self.status}')>"