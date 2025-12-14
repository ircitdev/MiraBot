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


class AdminUser(Base):
    """Модель администратора."""
    
    __tablename__ = "admin_users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    name: Mapped[Optional[str]] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="admin")  # admin, superadmin
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    def __repr__(self) -> str:
        return f"<AdminUser(id={self.id}, email={self.email}, role={self.role})>"


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


class AdminLog(Base):
    """Лог действий администраторов."""

    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Telegram ID админа

    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_user_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    details: Mapped[Optional[dict]] = mapped_column(JSONB)

    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    def __repr__(self) -> str:
        return f"<AdminLog(id={self.id}, admin_id={self.admin_id}, action={self.action})>"


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
