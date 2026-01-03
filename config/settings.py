"""
Конфигурация приложения.
Загружает переменные окружения и предоставляет типизированный доступ.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Основные настройки приложения."""
    
    # =====================================
    # TELEGRAM
    # =====================================
    TELEGRAM_BOT_TOKEN: str = Field(..., description="Токен бота от BotFather")
    
    # =====================================
    # ANTHROPIC (Claude API)
    # =====================================
    ANTHROPIC_API_KEY: str = Field(..., description="API ключ Anthropic")
    CLAUDE_MODEL: str = Field(
        default="claude-sonnet-4-20250514",
        description="Модель Claude для использования"
    )
    CLAUDE_MAX_TOKENS: int = Field(default=1024, description="Макс. токенов в ответе")

    # =====================================
    # OPENAI (Whisper API)
    # =====================================
    OPENAI_API_KEY: str = Field(default="", description="API ключ OpenAI для Whisper")
    WHISPER_MODEL: str = Field(default="whisper-1", description="Модель Whisper")

    # =====================================
    # YANDEX SPEECHKIT (TTS)
    # =====================================
    YANDEX_API_KEY: str = Field(default="", description="API ключ Yandex Cloud")
    YANDEX_FOLDER_ID: str = Field(default="", description="ID каталога Yandex Cloud")
    YANDEX_API_KEY_ID: str = Field(default="", description="ID API ключа Yandex Cloud")
    YANDEX_API_KEY_SECRET: str = Field(default="", description="Секрет API ключа Yandex Cloud")
    TTS_VOICE: str = Field(default="alena", description="Голос TTS (alena, jane, omazh)")
    TTS_EMOTION: str = Field(default="good", description="Эмоция TTS (neutral, good)")
    TTS_SPEED: float = Field(default=1.0, description="Скорость речи TTS (0.1-3.0)")
    
    # =====================================
    # DATABASE
    # =====================================
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://mira:mira_password@localhost:5432/mira_bot",
        description="URL подключения к PostgreSQL"
    )
    DB_POOL_SIZE: int = Field(
        default=5,
        description="Базовый размер пула соединений"
    )
    DB_MAX_OVERFLOW: int = Field(
        default=10,
        description="Максимум дополнительных соединений сверх pool_size"
    )
    DB_POOL_TIMEOUT: int = Field(
        default=30,
        description="Таймаут ожидания соединения из пула (секунды)"
    )
    DB_POOL_RECYCLE: int = Field(
        default=1800,
        description="Время жизни соединения (секунды), после которого оно пересоздаётся"
    )
    
    # =====================================
    # REDIS
    # =====================================
    REDIS_URL: str = Field(
        default="redis://localhost:6379",
        description="URL подключения к Redis"
    )
    
    # =====================================
    # ЮKASSA
    # =====================================
    YOOKASSA_SHOP_ID: str = Field(default="", description="ID магазина ЮKassa")
    YOOKASSA_SECRET_KEY: str = Field(default="", description="Секретный ключ ЮKassa")
    YOOKASSA_RETURN_URL: str = Field(
        default="https://t.me/mira_support_bot",
        description="URL возврата после оплаты"
    )
    
    # =====================================
    # ЦЕНЫ (в рублях)
    # =====================================
    PRICE_MONTHLY: int = Field(default=999, description="Цена месячной подписки")
    PRICE_QUARTERLY: int = Field(default=2549, description="Цена квартальной подписки (экономия 15%)")
    PRICE_YEARLY: int = Field(default=8399, description="Цена годовой подписки (экономия 30%)")
    
    # =====================================
    # ЛИМИТЫ
    # =====================================
    FREE_MESSAGES_PER_DAY: int = Field(
        default=10,
        description="Лимит сообщений в день для free"
    )
    FREE_MEMORY_DEPTH: int = Field(
        default=10,
        description="Глубина памяти для free (кол-во сообщений)"
    )
    PREMIUM_MEMORY_DEPTH: int = Field(
        default=50,
        description="Глубина памяти для premium"
    )
    
    # =====================================
    # РЕФЕРАЛЬНАЯ ПРОГРАММА
    # =====================================
    REFERRAL_BONUS_DAYS: int = Field(
        default=7,
        description="Бонусные дни за реферала"
    )
    REFERRAL_MILESTONE_3: int = Field(
        default=30,
        description="Бонус за 3 рефералов (дней)"
    )
    
    # =====================================
    # ADMIN PANEL
    # =====================================
    ADMIN_SECRET_KEY: str = Field(
        default="change-this-secret-key-in-production",
        description="Секретный ключ для JWT"
    )
    ADMIN_DEFAULT_EMAIL: str = Field(
        default="admin@mira-bot.ru",
        description="Email админа по умолчанию"
    )
    ADMIN_DEFAULT_PASSWORD: str = Field(
        default="change_me",
        description="Пароль админа по умолчанию"
    )
    ADMIN_TELEGRAM_ID: int = Field(
        default=65876198,
        description="Telegram ID администратора"
    )
    ADMIN_TOKEN: str = Field(
        default="NJCZ8rYTNuFfLrNRwTIiSyutyql_EprB_K2jURF7HAw",
        description="Токен для доступа к админ-панели"
    )

    # =====================================
    # РИТУАЛЫ
    # =====================================
    RITUAL_MORNING_DEFAULT: str = Field(
        default="09:00",
        description="Время утреннего check-in по умолчанию"
    )
    RITUAL_EVENING_DEFAULT: str = Field(
        default="21:00",
        description="Время вечернего check-in по умолчанию"
    )
    
    # =====================================
    # БЕЗОПАСНОСТЬ
    # =====================================
    CRISIS_KEYWORDS: List[str] = Field(
        default=[
            "не хочу жить",
            "суицид",
            "убить себя",
            "покончить с собой",
            "конец всему",
            "бьёт",
            "бьет",
            "насилие",
            "боюсь за свою жизнь",
            "порезать себя",
            "самоповреждение"
        ],
        description="Ключевые слова для детекции кризиса"
    )
    CRISIS_HOTLINE: str = Field(
        default="8-800-2000-122",
        description="Телефон кризисной линии"
    )
    
    # =====================================
    # HEALTH CHECK
    # =====================================
    HEALTH_CHECK_PORT: int = Field(
        default=8080,
        description="Порт для health check endpoint"
    )

    # =====================================
    # WEBAPP
    # =====================================
    WEBAPP_DOMAIN: str = Field(
        default="",
        description="Домен для WebApp (например: webapp.mirabot.com)"
    )
    WEBAPP_PORT: int = Field(
        default=8081,
        description="Порт для WebApp сервера"
    )

    # =====================================
    # GOOGLE CLOUD STORAGE
    # =====================================
    USE_GCS: bool = Field(
        default=False,
        description="Использовать GCS для хранения файлов"
    )
    GCS_BUCKET_NAME: str = Field(
        default="",
        description="Имя бакета GCS"
    )
    GCS_CREDENTIALS_PATH: str = Field(
        default="",
        description="Путь к файлу credentials GCS"
    )
    GCS_RETENTION_FREE_DAYS: int = Field(
        default=90,
        description="Срок хранения файлов для бесплатных пользователей (дни)"
    )
    GCS_RETENTION_PREMIUM_DAYS: int = Field(
        default=365,
        description="Срок хранения файлов для premium пользователей (дни)"
    )

    # =====================================
    # SUPPORT BOT
    # =====================================
    SUPPORT_BOT_TOKEN: str = Field(
        default="",
        description="Токен бота технической поддержки @MiraDrugSupport_bot"
    )
    SUPPORT_GROUP_ID: int = Field(
        default=0,
        description="ID супергруппы MiraBotEvents для топиков поддержки"
    )
    SUPPORT_TOPIC_ID: int = Field(
        default=2,
        description="ID топика для обращений в поддержку"
    )
    REVIEWS_TOPIC_ID: int = Field(
        default=4,
        description="ID топика для отзывов пользователей"
    )
    SUPPORT_AUTO_REPLY: str = Field(
        default="✅ Сообщение получено. Ожидайте ответа от специалиста.",
        description="Автоматический ответ после получения сообщения"
    )
    SUPPORT_ENABLED: bool = Field(
        default=True,
        description="Включить/выключить бота поддержки"
    )
    SUPPORT_RATE_LIMIT: int = Field(
        default=10,
        description="Лимит сообщений в минуту от одного пользователя"
    )

    # =====================================
    # ЛОГИРОВАНИЕ
    # =====================================
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Возвращает кэшированный экземпляр настроек."""
    return Settings()


# Глобальный экземпляр настроек
settings = get_settings()
