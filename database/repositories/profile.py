"""
UserProfile Repository.
Репозиторий для работы с расширенными профилями пользователей.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import UserProfile
from database.session import async_session


class UserProfileRepository:
    """Репозиторий для работы с профилями пользователей."""

    async def get_by_user_id(self, user_id: int) -> Optional[UserProfile]:
        """Получает профиль по user_id."""
        async with async_session() as session:
            result = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            return result.scalar_one_or_none()

    async def get_or_create(self, user_id: int) -> UserProfile:
        """Получает или создаёт профиль пользователя."""
        profile = await self.get_by_user_id(user_id)
        if profile:
            return profile

        async with async_session() as session:
            profile = UserProfile(user_id=user_id)
            session.add(profile)
            await session.commit()
            await session.refresh(profile)
            return profile

    async def update_profile(
        self,
        user_id: int,
        **kwargs
    ) -> Optional[UserProfile]:
        """
        Обновляет поля профиля.

        Args:
            user_id: ID пользователя
            **kwargs: Поля для обновления
        """
        # Сначала убедимся что профиль существует
        profile = await self.get_or_create(user_id)

        # Фильтруем только допустимые поля
        allowed_fields = {
            'country', 'city', 'occupation', 'age', 'birth_year',
            'has_partner', 'partner_name', 'partner_age', 'partner_occupation',
            'partner_hobbies', 'relationship_start_date', 'wedding_date', 'how_met',
            'has_children', 'children_count', 'children',
            'hobbies', 'pets', 'living_situation', 'health_notes', 'important_dates',
            'confidence_location', 'confidence_occupation',
            'confidence_partner', 'confidence_children',
        }

        update_data = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}

        if not update_data:
            return profile

        async with async_session() as session:
            await session.execute(
                update(UserProfile)
                .where(UserProfile.user_id == user_id)
                .values(**update_data, updated_at=datetime.utcnow())
            )
            await session.commit()

        return await self.get_by_user_id(user_id)

    async def update_from_extracted_data(
        self,
        user_id: int,
        extracted_data: Dict[str, Any]
    ) -> Optional[UserProfile]:
        """
        Обновляет профиль на основе извлечённых данных.
        Увеличивает уверенность при подтверждении существующих данных.

        Args:
            user_id: ID пользователя
            extracted_data: Словарь с извлечёнными данными

        Структура extracted_data:
        {
            "location": {"country": "Россия", "city": "Москва", "confidence": 8},
            "occupation": {"value": "дизайнер", "confidence": 7},
            "age": {"value": 32, "confidence": 9},
            "partner": {
                "name": "Андрей",
                "age": 35,
                "occupation": "программист",
                "hobbies": "футбол, рыбалка",
                "confidence": 8
            },
            "relationship": {
                "how_met": "на работе",
                "relationship_start_date": "2015-03-15",
                "wedding_date": "2018-07-20",
                "confidence": 6
            },
            "children": [
                {"name": "Маша", "gender": "female", "age": 5, "hobbies": "рисование"}
            ],
            "children_confidence": 9
        }
        """
        profile = await self.get_or_create(user_id)

        update_kwargs = {}

        # Локация
        if 'location' in extracted_data:
            loc = extracted_data['location']
            if loc.get('country'):
                update_kwargs['country'] = loc['country']
            if loc.get('city'):
                update_kwargs['city'] = loc['city']
            if loc.get('confidence'):
                update_kwargs['confidence_location'] = max(
                    profile.confidence_location or 0,
                    loc['confidence']
                )

        # Работа
        if 'occupation' in extracted_data:
            occ = extracted_data['occupation']
            if occ.get('value'):
                update_kwargs['occupation'] = occ['value']
            if occ.get('confidence'):
                update_kwargs['confidence_occupation'] = max(
                    profile.confidence_occupation or 0,
                    occ['confidence']
                )

        # Возраст
        if 'age' in extracted_data:
            age_data = extracted_data['age']
            if age_data.get('value'):
                update_kwargs['age'] = age_data['value']
                # Вычисляем год рождения
                update_kwargs['birth_year'] = datetime.now().year - age_data['value']

        # Партнёр
        if 'partner' in extracted_data:
            partner = extracted_data['partner']
            update_kwargs['has_partner'] = True
            if partner.get('name'):
                update_kwargs['partner_name'] = partner['name']
            if partner.get('age'):
                update_kwargs['partner_age'] = partner['age']
            if partner.get('occupation'):
                update_kwargs['partner_occupation'] = partner['occupation']
            if partner.get('hobbies'):
                update_kwargs['partner_hobbies'] = partner['hobbies']
            if partner.get('confidence'):
                update_kwargs['confidence_partner'] = max(
                    profile.confidence_partner or 0,
                    partner['confidence']
                )

        # Отношения
        if 'relationship' in extracted_data:
            rel = extracted_data['relationship']
            if rel.get('how_met'):
                update_kwargs['how_met'] = rel['how_met']
            if rel.get('relationship_start_date'):
                try:
                    update_kwargs['relationship_start_date'] = datetime.strptime(
                        rel['relationship_start_date'], '%Y-%m-%d'
                    ).date()
                except ValueError:
                    pass
            if rel.get('wedding_date'):
                try:
                    update_kwargs['wedding_date'] = datetime.strptime(
                        rel['wedding_date'], '%Y-%m-%d'
                    ).date()
                except ValueError:
                    pass

        # Дети
        if 'children' in extracted_data:
            children = extracted_data['children']
            if children:
                update_kwargs['has_children'] = True
                update_kwargs['children_count'] = len(children)
                update_kwargs['children'] = children
            if extracted_data.get('children_confidence'):
                update_kwargs['confidence_children'] = max(
                    profile.confidence_children or 0,
                    extracted_data['children_confidence']
                )

        # Увлечения пользователя
        if 'hobbies' in extracted_data:
            update_kwargs['hobbies'] = extracted_data['hobbies']

        # Питомцы
        if 'pets' in extracted_data:
            update_kwargs['pets'] = extracted_data['pets']

        # С кем живёт
        if 'living_situation' in extracted_data:
            update_kwargs['living_situation'] = extracted_data['living_situation']

        return await self.update_profile(user_id, **update_kwargs)

    async def add_child(
        self,
        user_id: int,
        name: str,
        gender: Optional[str] = None,
        age: Optional[int] = None,
        hobbies: Optional[str] = None,
    ) -> Optional[UserProfile]:
        """Добавляет ребёнка в профиль."""
        profile = await self.get_or_create(user_id)

        children = profile.children or []

        # Проверяем, есть ли уже ребёнок с таким именем
        existing_names = [c.get('name', '').lower() for c in children]
        if name.lower() in existing_names:
            # Обновляем существующего ребёнка
            for child in children:
                if child.get('name', '').lower() == name.lower():
                    if gender:
                        child['gender'] = gender
                    if age:
                        child['age'] = age
                        child['birth_year'] = datetime.now().year - age
                    if hobbies:
                        child['hobbies'] = hobbies
                    break
        else:
            # Добавляем нового
            child_data = {'name': name}
            if gender:
                child_data['gender'] = gender
            if age:
                child_data['age'] = age
                child_data['birth_year'] = datetime.now().year - age
            if hobbies:
                child_data['hobbies'] = hobbies
            children.append(child_data)

        return await self.update_profile(
            user_id,
            has_children=True,
            children_count=len(children),
            children=children
        )

    async def add_important_date(
        self,
        user_id: int,
        date: str,  # YYYY-MM-DD
        description: str,
        date_type: str = 'other'  # birthday, anniversary, other
    ) -> Optional[UserProfile]:
        """Добавляет важную дату в профиль."""
        profile = await self.get_or_create(user_id)

        important_dates = profile.important_dates or []

        # Проверяем, есть ли уже такая дата
        existing_dates = [d.get('date') for d in important_dates]
        if date not in existing_dates:
            important_dates.append({
                'date': date,
                'description': description,
                'type': date_type
            })

        return await self.update_profile(user_id, important_dates=important_dates)

    async def get_profile_summary(self, user_id: int) -> Dict[str, Any]:
        """Возвращает краткое резюме профиля для промпта."""
        profile = await self.get_by_user_id(user_id)

        if not profile:
            return {}

        summary = {}

        # Локация
        location_parts = []
        if profile.city:
            location_parts.append(profile.city)
        if profile.country:
            location_parts.append(profile.country)
        if location_parts:
            summary['location'] = ', '.join(location_parts)

        # Возраст и работа
        if profile.age:
            summary['age'] = profile.age
        if profile.occupation:
            summary['occupation'] = profile.occupation

        # Партнёр
        if profile.has_partner and profile.partner_name:
            partner_info = f"{profile.partner_name}"
            if profile.partner_age:
                partner_info += f", {profile.partner_age} лет"
            if profile.partner_occupation:
                partner_info += f", {profile.partner_occupation}"
            summary['partner'] = partner_info

            if profile.how_met:
                summary['how_met'] = profile.how_met

        # Дети
        if profile.has_children and profile.children:
            children_info = []
            for child in profile.children:
                child_str = child.get('name', 'ребёнок')
                if child.get('age'):
                    child_str += f" ({child['age']} лет)"
                children_info.append(child_str)
            summary['children'] = ', '.join(children_info)

        # Увлечения
        if profile.hobbies:
            summary['hobbies'] = profile.hobbies

        return summary


# Глобальный экземпляр
profile_repo = UserProfileRepository()
