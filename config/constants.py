"""
Константы приложения.
"""

# =====================================
# ПЕРСОНЫ БОТА
# =====================================
PERSONA_MIRA = "mira"
PERSONA_MARK = "mark"

PERSONAS = {
    PERSONA_MIRA: {
        "name": "Мира",
        "age": 42,
        "description": "Замужем 18 лет, двое детей. Прошла через кризис в браке и нашла путь обратно.",
    },
    PERSONA_MARK: {
        "name": "Марк",
        "age": 45,
        "description": "Женат 20 лет, отец троих детей. Научился понимать женскую душу.",
    },
}

# =====================================
# ПЛАНЫ ПОДПИСКИ
# =====================================
PLAN_FREE = "free"
PLAN_PREMIUM = "premium"
PLAN_TRIAL = "trial"

SUBSCRIPTION_PLANS = {
    "monthly": {
        "code": "monthly",
        "name": "1 месяц",
        "duration_days": 30,
        "description": "Подписка Mira Premium — 1 месяц",
    },
    "quarterly": {
        "code": "quarterly",
        "name": "3 месяца",
        "duration_days": 90,
        "description": "Подписка Mira Premium — 3 месяца (экономия 15%)",
    },
    "yearly": {
        "code": "yearly",
        "name": "1 год",
        "duration_days": 365,
        "description": "Подписка Mira Premium — 1 год (экономия 30%)",
    },
}

# =====================================
# СТАТУСЫ
# =====================================
# Подписки
SUBSCRIPTION_STATUS_ACTIVE = "active"
SUBSCRIPTION_STATUS_CANCELLED = "cancelled"
SUBSCRIPTION_STATUS_EXPIRED = "expired"

# Платежи
PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_COMPLETED = "completed"
PAYMENT_STATUS_FAILED = "failed"
PAYMENT_STATUS_REFUNDED = "refunded"

# Рефералы
REFERRAL_STATUS_PENDING = "pending"
REFERRAL_STATUS_ACTIVATED = "activated"
REFERRAL_STATUS_REWARDED = "rewarded"

# =====================================
# ТЕГИ СООБЩЕНИЙ
# =====================================
TAG_CRISIS = "crisis"
TAG_INSIGHT = "insight"
TAG_TOPIC_HUSBAND = "topic:husband"
TAG_TOPIC_CHILDREN = "topic:children"
TAG_TOPIC_SELF = "topic:self"
TAG_TOPIC_RELATIVES = "topic:relatives"
TAG_TOPIC_INTIMACY = "topic:intimacy"
TAG_TOPIC_WORK = "topic:work"

# =====================================
# КАТЕГОРИИ ПАМЯТИ
# =====================================
MEMORY_CATEGORY_FAMILY = "family"
MEMORY_CATEGORY_PROBLEMS = "problems"
MEMORY_CATEGORY_INSIGHTS = "insights"
MEMORY_CATEGORY_PATTERNS = "patterns"
MEMORY_CATEGORY_PROGRESS = "progress"
MEMORY_CATEGORY_ATTEMPTS = "attempts"  # Попытки решения проблем

# =====================================
# ТИПЫ РИТУАЛОВ
# =====================================
RITUAL_MORNING_CHECKIN = "morning_checkin"
RITUAL_EVENING_CHECKIN = "evening_checkin"
RITUAL_FOLLOWUP = "followup"
RITUAL_GRATITUDE = "ritual_gratitude"
RITUAL_LETTER = "ritual_letter"
RITUAL_THERMOMETER = "ritual_thermometer"

# =====================================
# ШАГИ ОНБОРДИНГА
# =====================================
ONBOARDING_STEP_START = 0
ONBOARDING_STEP_PERSONA_CHOSEN = 1
ONBOARDING_STEP_NAME_PROVIDED = 2
ONBOARDING_COMPLETED = 3

# =====================================
# РОЛИ АДМИНОВ
# =====================================
ADMIN_ROLE_ADMIN = "admin"
ADMIN_ROLE_SUPERADMIN = "superadmin"

# =====================================
# ЛИМИТЫ
# =====================================
MAX_MESSAGE_LENGTH = 4000
MAX_REFERRAL_CODE_LENGTH = 8
MAX_MEMORY_ENTRIES = 100
MAX_SCHEDULED_MESSAGES_PER_USER = 10

# =====================================
# ВРЕМЕННЫЕ ИНТЕРВАЛЫ (в секундах)
# =====================================
CACHE_TTL_SHORT = 60  # 1 минута
CACHE_TTL_MEDIUM = 300  # 5 минут
CACHE_TTL_LONG = 3600  # 1 час
CACHE_TTL_DAY = 86400  # 1 день

# =====================================
# ЭМОДЗИ
# =====================================
EMOJI_HEART = "💛"
EMOJI_SUN = "☀️"
EMOJI_STAR = "⭐"
EMOJI_SPARKLE = "✨"
EMOJI_WARNING = "⚠️"
EMOJI_CHECK = "✅"
EMOJI_CROSS = "❌"
EMOJI_CLOCK = "⏰"
EMOJI_GIFT = "🎁"
EMOJI_CROWN = "👑"
