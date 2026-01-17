"""
Personality Analysis API endpoints.
"""

import io
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from webapp.api.auth import get_current_user
from database.repositories.user import UserRepository
from database.repositories.conversation import ConversationRepository
from database.repositories.user_report import UserReportRepository
from database.repositories.api_cost import ApiCostRepository
from config.settings import settings


router = APIRouter()
user_repo = UserRepository()
conv_repo = ConversationRepository()
report_repo = UserReportRepository()
api_cost_repo = ApiCostRepository()


@router.post("/analysis")
async def generate_personality_analysis(current_user: dict = Depends(get_current_user)):
    """
    Генерирует анализ личности пользователя на основе всей переписки.

    Требования:
    - Premium подписка
    - Минимум 20 сообщений
    - Можно использовать 1 раз в месяц
    """
    user = await user_repo.get_by_telegram_id(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Проверка Premium статуса
    if not user.premium_until or user.premium_until < datetime.utcnow():
        raise HTTPException(
            status_code=403,
            detail="Анализ личности доступен только для Premium пользователей"
        )

    # Проверка минимального количества сообщений
    messages, total = await conv_repo.get_paginated(user.id, page=1, per_page=20)

    if total < 20:
        raise HTTPException(
            status_code=400,
            detail="Недостаточно данных для анализа. Пообщайся со мной больше! (минимум 20 сообщений)"
        )

    # Проверка последнего анализа (раз в месяц)
    from database.models import UserReport
    from database.base import get_session_context
    from sqlalchemy import select, and_

    async with get_session_context() as session:
        one_month_ago = datetime.utcnow() - timedelta(days=30)
        query = select(UserReport).where(
            and_(
                UserReport.telegram_id == user.telegram_id,
                UserReport.created_at >= one_month_ago
            )
        ).order_by(UserReport.created_at.desc())

        result = await session.execute(query)
        recent_report = result.scalar_one_or_none()

        if recent_report:
            days_left = 30 - (datetime.utcnow() - recent_report.created_at).days
            raise HTTPException(
                status_code=429,
                detail=f"Анализ личности доступен раз в месяц. Следующий анализ будет доступен через {days_left} дней."
            )

    # Получаем ВСЕ сообщения пользователя
    all_messages, total_count = await conv_repo.get_paginated(user.id, page=1, per_page=5000)

    if not all_messages:
        raise HTTPException(status_code=400, detail="Нет сообщений для анализа")

    # Формируем текст переписки
    conversation_text = []
    for msg in reversed(all_messages):  # От старых к новым
        role = "Пользователь" if msg.role == "user" else "Мира"
        date = msg.created_at.strftime("%d.%m.%Y %H:%M")
        conversation_text.append(f"[{date}] {role}: {msg.content}")

    # Ограничиваем размер (макс 100K символов)
    full_text = "\n".join(conversation_text)
    if len(full_text) > 100000:
        full_text = full_text[-100000:]

    # Имя пользователя
    user_name = user.display_name or user.first_name or f"ID:{user.telegram_id}"

    # Промпт для анализа личности
    analysis_prompt = f"""Проанализируй переписку пользователя с AI-подругой Мирой и создай глубокий психологический профиль.

Пользователь: {user_name}

Создай детальный отчёт в Markdown формате:

# Анализ личности: {user_name}

## 🎭 Кто я?
[Глубинная характеристика личности, ценности, мотивация, жизненная позиция]

## 💭 О чём я думаю
[Основные темы переживаний, волнующие вопросы, интересы]

## 😊 Мой эмоциональный мир
[Эмоциональный паттерн, как реагирую на события, что меня радует/расстраивает]

## ⚡ Мои сильные стороны
[Качества, ресурсы, то в чём я хорош/хороша]

## 🔍 Точки роста
[Что стоит развить, над чем поработать - деликатно и с заботой]

## 🌱 Мой прогресс
[Как менялась с начала общения, какие есть позитивные сдвиги]

## 💡 Рекомендации для себя
[Практические советы для улучшения жизни, основанные на выявленных паттернах]

## 📊 Статистика
- Дата первого сообщения: [дата]
- Всего сообщений: {total_count}
- Период общения: [количество дней]

---
*Этот анализ создан на основе вашей переписки с Мирой. Он отражает ваш внутренний мир таким, каким вы его показали.*

Пиши от лица пользователя ("я", "мне"), тепло и с заботой. Используй конкретные примеры из переписки.

ПЕРЕПИСКА:
{full_text}"""

    try:
        # Создаём клиент Anthropic
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Запрос к Claude
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[
                {"role": "user", "content": analysis_prompt}
            ]
        )

        analysis_text = response.content[0].text

        # Извлекаем информацию о токенах
        tokens_used = response.usage.input_tokens + response.usage.output_tokens

        # Рассчитываем стоимость
        input_cost = (response.usage.input_tokens / 1_000_000) * 3.0
        output_cost = (response.usage.output_tokens / 1_000_000) * 15.0
        cost_usd = round(input_cost + output_cost, 6)

        # Трекаем стоимость API
        await api_cost_repo.create(
            user_id=user.id,
            provider='claude',
            operation='personality_analysis',
            cost_usd=cost_usd,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=tokens_used,
            model="claude-sonnet-4-20250514",
        )

        # Сохраняем отчёт в базу данных
        await report_repo.create(
            telegram_id=user.telegram_id,
            content=analysis_text,
            created_by=None,  # Сгенерирован пользователем
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        )

        logger.info(f"Personality analysis generated for user {user.telegram_id}, cost: ${cost_usd}")

    except Exception as e:
        logger.error(f"Failed to generate personality analysis: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка генерации анализа: {str(e)}"
        )

    # Возвращаем Markdown файл
    output = io.BytesIO(analysis_text.encode('utf-8'))

    return StreamingResponse(
        output,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename=mira_personality_analysis_{user.telegram_id}.md"
        }
    )
