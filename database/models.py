"""
SQLAlchemy Models.
Определение всех таблиц базы данных.
Поддерживает PostgreSQL и SQLite.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    Float,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Time,
    Date,
    Enum as SQLEnum,
    Index,
    func,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property

# Используем JSON вместо JSONB для совместимости с SQLite
# При работе с PostgreSQL можно заменить на JSONB для лучшей производительности
JSONB = JSON


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class User(Base):
    """Модель пользователя."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Персонализация
    display_name: Mapped[Optional[str]] = mapped_column(String(100))
    persona: Mapped[Optional[str]] = mapped_column(String(20))  # 'mira' или 'mark'
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    
    # Семейный контекст
    partner_name: Mapped[Optional[str]] = mapped_column(String(100))
    partner_gender: Mapped[Optional[str]] = mapped_column(String(10))  # 'male' или 'female'
    children_info: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    marriage_years: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Настройки
    rituals_enabled: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    preferred_time_morning: Mapped[Optional[str]] = mapped_column(String(5))  # "09:00"
    preferred_time_evening: Mapped[Optional[str]] = mapped_column(String(5))  # "21:00"
    proactive_messages: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Онбординг
    onboarding_step: Mapped[int] = mapped_column(Integer, default=0)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Статус
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    block_reason: Mapped[Optional[str]] = mapped_column(Text)
    special_status: Mapped[Optional[str]] = mapped_column(String(50))  # 'guardian' и т.д.

    # Отправленные фото (для отслеживания)
    sent_photos: Mapped[Optional[list]] = mapped_column(JSONB, default=list)

    # Аватар пользователя (URL в GCS)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Праздничные даты
    birthday: Mapped[Optional[datetime]] = mapped_column(Date)  # День рождения пользователя
    anniversary: Mapped[Optional[datetime]] = mapped_column(Date)  # Годовщина свадьбы

    # Персонализация стиля общения (выводится автоматически из диалогов)
    communication_style: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Структура communication_style:
    # {
    #   "formality": "informal" | "neutral" | "formal",  # уровень формальности
    #   "emoji_preference": "none" | "few" | "many",     # использование эмодзи
    #   "message_length": "short" | "medium" | "long",   # предпочтительная длина
    #   "response_depth": "surface" | "medium" | "deep", # глубина проработки тем
    #   "humor_level": "none" | "light" | "frequent",    # юмор в общении
    #   "support_style": "gentle" | "direct" | "tough",  # стиль поддержки
    #   "topics_avoided": [],                             # темы, которые избегает
    #   "triggers": [],                                   # чувствительные темы
    #   "updated_at": "2024-12-14T..."                   # дата обновления
    # }

    # Предпочтения по контенту
    content_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Структура content_preferences:
    # {
    #   "meditation_enabled": bool,                       # присылать медитации
    #   "meditation_types": ["morning", "sleep", ...],   # типы медитаций
    #   "meditation_frequency": "daily" | "3_per_week" | "weekly",
    #   "exercises_enabled": bool                         # присылать упражнения
    # }

    # Тихие часы (когда не беспокоить)
    quiet_hours_start: Mapped[Optional[datetime]] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[Optional[datetime]] = mapped_column(Time, nullable=True)

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Связи
    subscription: Mapped[Optional["Subscription"]] = relationship(
        "Subscription",
        back_populates="user",
        uselist=False,
        lazy="selectin"
    )
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="user",
        lazy="selectin"
    )
    memory_entries: Mapped[List["MemoryEntry"]] = relationship(
        "MemoryEntry",
        back_populates="user",
        lazy="selectin"
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="user",
        lazy="selectin"
    )
    reports: Mapped[List["UserReport"]] = relationship(
        "UserReport",
        back_populates="user",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, name={self.display_name})>"


class Subscription(Base):
    """Модель подписки."""
    
    __tablename__ = "subscriptions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    
    plan: Mapped[str] = mapped_column(String(20), nullable=False)  # 'free', 'premium', 'trial'
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    
    # Лимиты
    messages_today: Mapped[int] = mapped_column(Integer, default=0)
    messages_reset_at: Mapped[datetime] = mapped_column(Date, default=func.current_date())
    
    # Сроки
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Автоплатёж
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_method_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Платёжная информация
    payment_provider: Mapped[Optional[str]] = mapped_column(String(50))
    external_subscription_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="subscription")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="subscription")
    
    @hybrid_property
    def is_active(self) -> bool:
        """Проверяет активна ли подписка."""
        if self.status != "active":
            return False
        if self.expires_at and self.expires_at < datetime.now():
            return False
        return True
    
    @hybrid_property
    def is_premium(self) -> bool:
        """Проверяет премиум ли подписка."""
        return self.plan == "premium" and self.is_active
    
    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, user_id={self.user_id}, plan={self.plan})>"


class Message(Base):
    """Модель сообщения (история диалогов)."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)

    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' или 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), default="text")  # 'text' или 'voice'

    # Метаданные
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Теги для поиска и аналитики
    tags: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="messages")
    
    # Индексы
    __table_args__ = (
        Index("idx_messages_user_created", "user_id", "created_at"),
        # GIN индекс для tags только в PostgreSQL, в SQLite не поддерживается
    )
    
    def __repr__(self) -> str:
        return f"<Message(id={self.id}, user_id={self.user_id}, role={self.role})>"


class MemoryEntry(Base):
    """Модель долговременной памяти."""
    
    __tablename__ = "memory_entries"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, default=5)  # 1-10
    
    source_message_ids: Mapped[Optional[list]] = mapped_column(JSON)  # Список ID сообщений
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="memory_entries")
    
    # Индексы
    __table_args__ = (
        Index("idx_memory_user_category", "user_id", "category"),
    )
    
    def __repr__(self) -> str:
        return f"<MemoryEntry(id={self.id}, user_id={self.user_id}, category={self.category})>"


class Referral(Base):
    """Модель реферала."""
    
    __tablename__ = "referrals"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    referred_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    
    reward_given_referrer: Mapped[bool] = mapped_column(Boolean, default=False)
    reward_given_referred: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Связи
    referrer: Mapped["User"] = relationship("User", foreign_keys=[referrer_id])
    referred: Mapped[Optional["User"]] = relationship("User", foreign_keys=[referred_id])
    
    def __repr__(self) -> str:
        return f"<Referral(id={self.id}, code={self.code}, status={self.status})>"


class Payment(Base):
    """Модель платежа."""
    
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    subscription_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("subscriptions.id"))
    
    # ЮKassa
    yookassa_payment_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    yookassa_status: Mapped[Optional[str]] = mapped_column(String(20))
    
    # Детали
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # в копейках
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    description: Mapped[Optional[str]] = mapped_column(String(255))
    
    plan: Mapped[Optional[str]] = mapped_column(String(20))  # monthly, quarterly, yearly
    
    # Метод оплаты
    payment_method_type: Mapped[Optional[str]] = mapped_column(String(50))
    payment_method_id: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Автоплатёж
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurring_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Статус
    status: Mapped[str] = mapped_column(String(20), default="pending")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="payments")
    subscription: Mapped[Optional["Subscription"]] = relationship("Subscription", back_populates="payments")
    
    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount})>"


class ScheduledMessage(Base):
    """Модель запланированного сообщения (ритуалы)."""
    
    __tablename__ = "scheduled_messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    content: Mapped[Optional[str]] = mapped_column(Text)
    context: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    status: Mapped[str] = mapped_column(String(20), default="pending")
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    
    # Индексы (partial index только в PostgreSQL)
    __table_args__ = (
        Index("idx_scheduled_pending", "scheduled_for", "status"),
    )
    
    def __repr__(self) -> str:
        return f"<ScheduledMessage(id={self.id}, type={self.type}, status={self.status})>"


class MoodEntry(Base):
    """Модель записи настроения пользователя."""

    __tablename__ = "mood_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("messages.id"))

    # Основные метрики настроения
    mood_score: Mapped[int] = mapped_column(Integer, nullable=False)  # -5 до +5
    energy_level: Mapped[Optional[int]] = mapped_column(Integer)  # 1-10
    anxiety_level: Mapped[Optional[int]] = mapped_column(Integer)  # 1-10

    # Детали
    primary_emotion: Mapped[str] = mapped_column(String(50), nullable=False)  # sad, anxious, angry, happy, neutral
    secondary_emotions: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    triggers: Mapped[Optional[list]] = mapped_column(JSONB, default=list)  # Триггеры настроения

    # Контекст
    context_tags: Mapped[Optional[list]] = mapped_column(JSONB, default=list)  # topic:husband, etc.

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Индексы
    __table_args__ = (
        Index("idx_mood_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<MoodEntry(id={self.id}, user_id={self.user_id}, mood={self.mood_score}, emotion={self.primary_emotion})>"


class PromoCode(Base):
    """Модель промокода."""

    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Код и описание
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))

    # Тип промокода
    promo_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Типы:
    #   - 'discount_percent' — скидка в процентах (value = 10 означает 10%)
    #   - 'discount_amount' — скидка в рублях (value = 100 означает 100₽)
    #   - 'free_days' — бесплатные дни Premium (value = 7 означает 7 дней)
    #   - 'free_trial' — активация trial подписки (value = кол-во дней)

    # Значение промокода (зависит от типа)
    value: Mapped[int] = mapped_column(Integer, nullable=False)

    # Ограничения
    max_uses: Mapped[Optional[int]] = mapped_column(Integer)  # Макс. количество активаций (NULL = безлимит)
    current_uses: Mapped[int] = mapped_column(Integer, default=0)  # Текущее количество активаций
    max_uses_per_user: Mapped[int] = mapped_column(Integer, default=1)  # Макс. на одного пользователя

    # Срок действия
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Начало действия (NULL = сразу)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Окончание (NULL = бессрочно)

    # Применимость
    applicable_plans: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    # Список планов, к которым применим: ['monthly', 'quarterly', 'yearly']
    # Пустой список = применим ко всем

    # Для кого доступен
    only_new_users: Mapped[bool] = mapped_column(Boolean, default=False)  # Только для новых
    only_for_user_ids: Mapped[Optional[list]] = mapped_column(JSONB)  # Только для конкретных user_id

    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Создатель
    created_by_admin_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Связи
    usages: Mapped[List["PromoCodeUsage"]] = relationship(
        "PromoCodeUsage",
        back_populates="promo_code",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<PromoCode(id={self.id}, code={self.code}, type={self.promo_type})>"


class PromoCodeUsage(Base):
    """Модель использования промокода."""

    __tablename__ = "promo_code_usages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promo_code_id: Mapped[int] = mapped_column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)

    # Результат применения
    applied_to_payment_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("payments.id"))
    discount_amount: Mapped[Optional[int]] = mapped_column(Integer)  # Размер скидки в рублях
    free_days_granted: Mapped[Optional[int]] = mapped_column(Integer)  # Выданные бесплатные дни

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Связи
    promo_code: Mapped["PromoCode"] = relationship("PromoCode", back_populates="usages")
    user: Mapped["User"] = relationship("User")
    payment: Mapped[Optional["Payment"]] = relationship("Payment")

    # Индексы
    __table_args__ = (
        Index("idx_promo_usage_user", "user_id"),
        Index("idx_promo_usage_code", "promo_code_id"),
    )

    def __repr__(self) -> str:
        return f"<PromoCodeUsage(id={self.id}, promo_code_id={self.promo_code_id}, user_id={self.user_id})>"


class UserTrigger(Base):
    """Модель для хранения чувствительных тем (триггеров) пользователя."""

    __tablename__ = "user_triggers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)

    # Тема триггера
    topic: Mapped[str] = mapped_column(String(100), nullable=False)  # Например: "свекровь", "развод", "здоровье"

    # Описание (опционально)
    description: Mapped[Optional[str]] = mapped_column(Text)  # Контекст почему это триггер

    # Степень чувствительности (1-10)
    severity: Mapped[int] = mapped_column(Integer, default=5)  # 1=мягко избегать, 10=критично не поднимать

    # Когда последний раз упоминалась тема
    last_mentioned_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Активен ли триггер
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Связи
    user: Mapped["User"] = relationship("User")

    # Индексы
    __table_args__ = (
        Index("idx_user_triggers_user", "user_id"),
        Index("idx_user_triggers_active", "user_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<UserTrigger(id={self.id}, user_id={self.user_id}, topic={self.topic}, severity={self.severity})>"


class UserGoal(Base):
    """Модель для отслеживания целей пользователя (SMART goals)."""

    __tablename__ = "user_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)

    # Цель
    original_goal: Mapped[str] = mapped_column(Text, nullable=False)  # Исходная формулировка от пользователя
    smart_goal: Mapped[Optional[str]] = mapped_column(Text)  # SMART-версия цели

    # SMART компоненты
    specific: Mapped[Optional[str]] = mapped_column(Text)  # Что конкретно
    measurable: Mapped[Optional[str]] = mapped_column(String(255))  # Как измерить
    achievable: Mapped[Optional[str]] = mapped_column(Text)  # Почему достижимо
    relevant: Mapped[Optional[str]] = mapped_column(Text)  # Почему важно
    time_bound: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Дедлайн

    # Статус
    status: Mapped[str] = mapped_column(String(20), default="active")
    # Статусы: 'active', 'completed', 'abandoned', 'on_hold'

    # Прогресс (0-100%)
    progress: Mapped[int] = mapped_column(Integer, default=0)

    # Категория цели
    category: Mapped[Optional[str]] = mapped_column(String(50))
    # Категории: 'health', 'relationships', 'work', 'personal_growth', 'habits', 'other'

    # Заметки и обновления
    notes: Mapped[Optional[str]] = mapped_column(Text)  # Заметки о прогрессе

    # Подцели / шаги
    milestones: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    # Структура milestones:
    # [
    #   {"title": "Шаг 1", "completed": false, "completed_at": null},
    #   {"title": "Шаг 2", "completed": true, "completed_at": "2025-01-15T..."}
    # ]

    # Напоминания
    reminder_frequency: Mapped[Optional[str]] = mapped_column(String(20))
    # 'daily', 'weekly', 'biweekly', 'none'

    last_check_in: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Последний раз спросили про прогресс
    next_check_in: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Следующее напоминание

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    abandoned_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Связи
    user: Mapped["User"] = relationship("User")

    # Индексы
    __table_args__ = (
        Index("idx_user_goals_user", "user_id"),
        Index("idx_user_goals_status", "user_id", "status"),
        Index("idx_user_goals_next_checkin", "next_check_in", "status"),
    )

    def __repr__(self) -> str:
        return f"<UserGoal(id={self.id}, user_id={self.user_id}, status={self.status}, progress={self.progress}%)>"


class UserFollowUp(Base):
    """Модель для отслеживания обещаний и планов пользователя (follow-ups)."""

    __tablename__ = "user_followups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)

    # Что пользователь планирует/обещал
    action: Mapped[str] = mapped_column(Text, nullable=False)  # "Поговорить с мужем о переезде"

    # Контекст (почему это важно)
    context: Mapped[Optional[str]] = mapped_column(Text)  # "Хотела обсудить давно, накопилось много"

    # Категория действия
    category: Mapped[Optional[str]] = mapped_column(String(50))
    # Категории: 'conversation', 'task', 'appointment', 'decision', 'habit', 'other'

    # Временные рамки
    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Когда планировалось
    followup_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # Когда спросить "Как прошло?"

    # Статус
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # Статусы: 'pending', 'completed', 'postponed', 'cancelled', 'asked'

    # Результат (заполняется после follow-up)
    outcome: Mapped[Optional[str]] = mapped_column(Text)  # Что произошло в итоге
    outcome_sentiment: Mapped[Optional[str]] = mapped_column(String(20))  # 'positive', 'negative', 'neutral', 'mixed'

    # Приоритет (насколько важно для пользователя)
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    # 'low', 'medium', 'high', 'urgent'

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    asked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Когда задали follow-up вопрос

    # Связь с сообщением где упоминалось
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("conversations.id"))

    # Связи
    user: Mapped["User"] = relationship("User")

    # Индексы
    __table_args__ = (
        Index("idx_user_followups_user", "user_id"),
        Index("idx_user_followups_status", "user_id", "status"),
        Index("idx_user_followups_followup_date", "followup_date", "status"),
        Index("idx_user_followups_priority", "user_id", "priority", "status"),
    )

    def __repr__(self) -> str:
        return f"<UserFollowUp(id={self.id}, user_id={self.user_id}, action={self.action[:30]}..., status={self.status})>"


class UserProgram(Base):
    """Модель участия пользователя в структурированной программе."""

    __tablename__ = "user_programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)

    # Какая программа
    program_id: Mapped[str] = mapped_column(String(50), nullable=False)  # "7_days_self_care", "anxiety_course"
    program_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Прогресс
    current_day: Mapped[int] = mapped_column(Integer, default=1)  # Какой день программы
    total_days: Mapped[int] = mapped_column(Integer, nullable=False)  # Всего дней в программе

    # Статус
    status: Mapped[str] = mapped_column(String(20), default="active")
    # 'active', 'paused', 'completed', 'abandoned'

    # История выполнения дней
    completed_days: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    # Структура: [
    #   {"day": 1, "completed_at": "2025-12-20T10:00:00", "feedback": "понравилось"},
    #   {"day": 2, "completed_at": "2025-12-21T09:30:00", "feedback": null}
    # ]

    # Настройки напоминаний
    reminder_time: Mapped[Optional[str]] = mapped_column(String(5))  # "09:00"
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Когда последний раз отправили задание
    last_task_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Когда следующее задание
    next_task_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Метаданные
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Связи
    user: Mapped["User"] = relationship("User")

    # Индексы
    __table_args__ = (
        Index("idx_user_programs_user", "user_id"),
        Index("idx_user_programs_status", "user_id", "status"),
        Index("idx_user_programs_next_task", "next_task_at", "status"),
    )

    def __repr__(self) -> str:
        return f"<UserProgram(id={self.id}, user_id={self.user_id}, program={self.program_id}, day={self.current_day}/{self.total_days})>"


class SystemSettings(Base):
    """Системные настройки (ключ-значение)."""

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(String(20), default="string")  # string, int, float, bool, json
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)  # Скрывать значение в UI

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<SystemSettings(key={self.key})>"


class Promotion(Base):
    """Модель акций и скидок."""

    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Название и описание
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Тип акции
    promo_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Типы: 'discount_percent', 'discount_amount', 'free_days', 'special_price'

    # Значение (скидка в % или рублях, дни, спец. цена)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    # К каким планам применяется (пусто = ко всем)
    applicable_plans: Mapped[Optional[list]] = mapped_column(JSONB, default=list)

    # Даты действия
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Ограничения
    max_uses: Mapped[Optional[int]] = mapped_column(Integer)  # Макс. использований
    current_uses: Mapped[int] = mapped_column(Integer, default=0)
    min_purchase_amount: Mapped[Optional[int]] = mapped_column(Integer)  # Мин. сумма покупки

    # Отображение
    banner_text: Mapped[Optional[str]] = mapped_column(String(200))  # Текст для баннера
    show_in_subscription: Mapped[bool] = mapped_column(Boolean, default=True)

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Индексы
    __table_args__ = (
        Index("idx_promotions_dates", "start_date", "end_date", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Promotion(id={self.id}, name={self.name}, type={self.promo_type})>"


class UserFile(Base):
    """Модель для хранения информации о файлах пользователей в GCS."""

    __tablename__ = "user_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)

    # Информация о файле
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Типы: 'photo', 'voice', 'video', 'document', 'sticker'

    # Telegram file_id (для повторного доступа)
    telegram_file_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # GCS данные
    gcs_path: Mapped[str] = mapped_column(String(500), nullable=False)  # Полный путь в бакете
    gcs_url: Mapped[Optional[str]] = mapped_column(String(1000))  # Публичный URL (если есть)

    # Метаданные файла
    file_name: Mapped[Optional[str]] = mapped_column(String(255))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)  # В байтах
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))

    # Контекст
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # ID сообщения в Telegram

    # Retention
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # Когда удалить
    is_premium_at_upload: Mapped[bool] = mapped_column(Boolean, default=False)  # Premium на момент загрузки

    # Статус
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)  # Помечен как удалённый
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Связи
    user: Mapped["User"] = relationship("User")

    # Индексы
    __table_args__ = (
        Index("idx_user_files_user", "user_id"),
        Index("idx_user_files_expires", "expires_at", "is_deleted"),
        Index("idx_user_files_type", "user_id", "file_type"),
    )

    def __repr__(self) -> str:
        return f"<UserFile(id={self.id}, user_id={self.user_id}, type={self.file_type}, path={self.gcs_path})>"


class UserProfile(Base):
    """Расширенный профиль пользователя — собирается в процессе общения."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False)

    # === Основная информация о пользователе ===
    country: Mapped[Optional[str]] = mapped_column(String(100))  # Россия
    city: Mapped[Optional[str]] = mapped_column(String(100))  # Москва
    occupation: Mapped[Optional[str]] = mapped_column(String(200))  # Кем работает
    age: Mapped[Optional[int]] = mapped_column(Integer)  # Возраст
    birth_year: Mapped[Optional[int]] = mapped_column(Integer)  # Год рождения (для расчёта возраста)

    # === Информация о партнёре/муже ===
    has_partner: Mapped[Optional[bool]] = mapped_column(Boolean)  # Есть партнёр/муж
    partner_name: Mapped[Optional[str]] = mapped_column(String(100))  # Имя партнёра
    partner_age: Mapped[Optional[int]] = mapped_column(Integer)  # Возраст партнёра
    partner_occupation: Mapped[Optional[str]] = mapped_column(String(200))  # Кем работает партнёр
    partner_hobbies: Mapped[Optional[str]] = mapped_column(Text)  # Увлечения партнёра

    # Даты отношений
    relationship_start_date: Mapped[Optional[datetime]] = mapped_column(Date)  # Дата знакомства
    wedding_date: Mapped[Optional[datetime]] = mapped_column(Date)  # Дата свадьбы
    how_met: Mapped[Optional[str]] = mapped_column(Text)  # Где/как познакомились

    # === Информация о детях ===
    has_children: Mapped[Optional[bool]] = mapped_column(Boolean)  # Есть дети
    children_count: Mapped[Optional[int]] = mapped_column(Integer)  # Количество детей
    children: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    # Структура children:
    # [
    #   {
    #     "name": "Маша",
    #     "gender": "female",  # male/female
    #     "age": 5,
    #     "birth_year": 2019,
    #     "hobbies": "рисование, танцы"
    #   },
    #   ...
    # ]

    # === Дополнительная информация ===
    hobbies: Mapped[Optional[str]] = mapped_column(Text)  # Увлечения пользователя
    pets: Mapped[Optional[str]] = mapped_column(Text)  # Домашние животные
    living_situation: Mapped[Optional[str]] = mapped_column(String(200))  # С кем живёт (с мужем, с родителями, одна)

    # Здоровье (деликатно)
    health_notes: Mapped[Optional[str]] = mapped_column(Text)  # Заметки о здоровье (хронические, беременность)

    # === Предпочтения в музыке ===
    music_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Структура music_preferences:
    # {
    #   "genres": ["джаз", "классика", "поп"],  # Любимые жанры
    #   "artists": ["Queen", "Ludovico Einaudi"],  # Любимые исполнители/группы
    #   "songs": ["Bohemian Rhapsody", "Nuvole Bianche"],  # Любимые песни
    #   "dislikes": ["рэп", "тяжёлый рок"],  # Не нравится
    #   "mood_music": {  # Музыка под настроение
    #       "relax": "классика",
    #       "energy": "рок",
    #       "sad": "джаз"
    #   }
    # }

    # === Предпочтения в фильмах/сериалах ===
    movie_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Структура movie_preferences:
    # {
    #   "genres": ["драма", "комедия", "триллер"],  # Любимые жанры
    #   "movies": ["Интерстеллар", "Форест Гамп"],  # Любимые фильмы
    #   "series": ["Друзья", "Во все тяжкие"],  # Любимые сериалы
    #   "actors": ["Том Хэнкс", "Леонардо Ди Каприо"],  # Любимые актёры
    #   "actresses": ["Эмма Стоун", "Натали Портман"],  # Любимые актрисы
    #   "directors": ["Кристофер Нолан"],  # Любимые режиссёры
    #   "dislikes": ["ужасы", "боевики"]  # Не нравится
    # }

    # Важные даты
    important_dates: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    # Структура important_dates:
    # [
    #   {"date": "2024-03-15", "description": "День рождения мамы", "type": "birthday"},
    #   {"date": "2024-06-20", "description": "Годовщина свадьбы", "type": "anniversary"},
    # ]

    # === Уверенность в данных (1-10) ===
    # Насколько мы уверены в этой информации
    confidence_location: Mapped[int] = mapped_column(Integer, default=0)  # Страна/город
    confidence_occupation: Mapped[int] = mapped_column(Integer, default=0)
    confidence_partner: Mapped[int] = mapped_column(Integer, default=0)
    confidence_children: Mapped[int] = mapped_column(Integer, default=0)

    # === Метаданные ===
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Связи
    user: Mapped["User"] = relationship("User", backref="profile")

    def __repr__(self) -> str:
        return f"<UserProfile(id={self.id}, user_id={self.user_id}, city={self.city})>"


class PaymentStats(Base):
    """Статистика платежей по дням (для отчётов)."""

    __tablename__ = "payment_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Дата
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, unique=True)

    # YooKassa
    yookassa_count: Mapped[int] = mapped_column(Integer, default=0)
    yookassa_amount: Mapped[int] = mapped_column(Integer, default=0)  # В копейках
    yookassa_successful: Mapped[int] = mapped_column(Integer, default=0)
    yookassa_failed: Mapped[int] = mapped_column(Integer, default=0)

    # CryptoBot
    crypto_count: Mapped[int] = mapped_column(Integer, default=0)
    crypto_amount: Mapped[int] = mapped_column(Integer, default=0)  # В копейках (конвертировано)
    crypto_successful: Mapped[int] = mapped_column(Integer, default=0)
    crypto_failed: Mapped[int] = mapped_column(Integer, default=0)

    # Telegram Stars
    stars_count: Mapped[int] = mapped_column(Integer, default=0)
    stars_amount: Mapped[int] = mapped_column(Integer, default=0)  # В звёздах

    # Промо-коды
    promo_uses: Mapped[int] = mapped_column(Integer, default=0)
    promo_discount_total: Mapped[int] = mapped_column(Integer, default=0)

    # Подписки
    new_subscriptions: Mapped[int] = mapped_column(Integer, default=0)
    renewals: Mapped[int] = mapped_column(Integer, default=0)
    cancellations: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<PaymentStats(date={self.date})>"


class AdminUser(Base):
    """Администраторы и модераторы админ-панели."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Роль: 'admin' или 'moderator'
    role: Mapped[str] = mapped_column(String(50), nullable=False, default='moderator', index=True)

    # Персонализация
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))  # URL фото профиля
    accent_color: Mapped[str] = mapped_column(String(7), default='#1976d2')  # HEX цвет

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('admin_users.id'))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Связи
    created_by: Mapped[Optional["AdminUser"]] = relationship("AdminUser", remote_side=[id], foreign_keys=[created_by_id])
    logs: Mapped[List["AdminLog"]] = relationship("AdminLog", back_populates="admin_user", cascade="all, delete-orphan")

    # Индексы
    __table_args__ = (
        Index("idx_admin_user_telegram_id", "telegram_id"),
        Index("idx_admin_user_role", "role"),
        Index("idx_admin_user_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<AdminUser(id={self.id}, telegram_id={self.telegram_id}, role={self.role})>"


class AdminLog(Base):
    """Лог действий администраторов и модераторов."""

    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(Integer, ForeignKey('admin_users.id'), nullable=False)

    # Действие
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # 'user_block', 'user_unblock', etc.
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), index=True)  # 'user', 'subscription', 'message'
    resource_id: Mapped[Optional[int]] = mapped_column(Integer)  # ID объекта

    # Детали
    details: Mapped[Optional[dict]] = mapped_column(JSONB)  # Дополнительные данные
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))  # IPv4/IPv6
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))

    # Результат
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Время
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)

    # Связи
    admin_user: Mapped["AdminUser"] = relationship("AdminUser", back_populates="logs")

    # Индексы
    __table_args__ = (
        Index("idx_admin_log_user", "admin_user_id"),
        Index("idx_admin_log_action", "action"),
        Index("idx_admin_log_resource", "resource_type", "resource_id"),
        Index("idx_admin_log_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AdminLog(id={self.id}, action={self.action}, admin_user_id={self.admin_user_id})>"


class UserReport(Base):
    """
    AI-отчёты о переписке с пользователем.
    Генерируются администраторами для анализа общения.
    """
    __tablename__ = "user_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Текст AI-сводки
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("admin_users.telegram_id"), nullable=True)  # Кто создал
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="reports")
    creator: Mapped[Optional["AdminUser"]] = relationship("AdminUser", foreign_keys=[created_by])

    # Индексы
    __table_args__ = (
        Index("idx_report_telegram_id", "telegram_id"),
        Index("idx_report_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UserReport(id={self.id}, telegram_id={self.telegram_id}, created_at={self.created_at})>"
