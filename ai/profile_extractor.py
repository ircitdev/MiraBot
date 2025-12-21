"""
Profile Extractor.
Извлекает информацию о пользователе из сообщений.
"""

import re
from typing import Dict, Any, Optional, List
from loguru import logger


class ProfileExtractor:
    """
    Извлекает профильную информацию из сообщений пользователя.

    Собирает:
    - Локация (страна, город)
    - Работа/профессия
    - Возраст
    - Партнёр (имя, возраст, профессия, увлечения)
    - Отношения (как познакомились, даты)
    - Дети (имена, пол, возраст, увлечения)
    - Музыкальные предпочтения (жанры, исполнители, песни)
    - Кинопредпочтения (фильмы, сериалы, актёры)
    """

    # Паттерны для извлечения локации
    CITY_PATTERNS = [
        r"(?:живу|переехал[аи]?|родом|из|в)\s+(?:городе?\s+)?([А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?)",
        r"я из ([А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?)",
        r"в ([А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?) живу",
    ]

    COUNTRY_PATTERNS = [
        r"(?:живу|переехал[аи]?|родом|из)\s+(?:в\s+)?([А-ЯЁ][а-яё]+(?:ии|ии|ах|ии))",  # России, Украине
        r"я из ([А-ЯЁ][а-яё]+(?:ии|ии|ии))",  # Россия, Украина, Беларусь
    ]

    # Паттерны для профессии
    OCCUPATION_PATTERNS = [
        r"(?:работаю|я)\s+([а-яё]+(?:ом|ей|ой|ицей|истом|ником|чиком))",  # работаю врачом, я учительницей
        r"я\s+(?:по профессии\s+)?([а-яё]+(?:ор|ер|ист|ник|чик|ец))",  # я программист, я врач
        r"(?:работаю|тружусь)\s+(?:в|на)\s+([а-яё\s]+?)(?:\.|,|$)",  # работаю в школе, в больнице
    ]

    # Паттерны для возраста
    AGE_PATTERNS = [
        r"мне\s+(\d{1,2})\s+(?:лет|год[а]?)",
        r"(?:в|мои)\s+(\d{1,2})\s+(?:лет|год[а]?)",
        r"(\d{1,2})\s+лет(?:няя)?",
    ]

    # Паттерны для партнёра
    PARTNER_NAME_PATTERNS = [
        r"муж(?:а|у)?\s+(?:зовут\s+)?([А-ЯЁ][а-яё]+)",
        r"(?:с\s+)?мужем\s+([А-ЯЁ][а-яё]+)(?:\s|,|\.|$)",
        r"([А-ЯЁ][а-яё]+)\s+—?\s?мой муж",
        r"парн[яю]\s+(?:зовут\s+)?([А-ЯЁ][а-яё]+)",
    ]

    PARTNER_AGE_PATTERNS = [
        r"муж(?:у|а)?\s+(\d{1,2})\s+(?:лет|год)",
        r"ему\s+(\d{1,2})\s+(?:лет|год)",  # Осторожно: только если контекст про партнёра
    ]

    PARTNER_OCCUPATION_PATTERNS = [
        r"муж\s+(?:работает\s+)?([а-яё]+(?:ом|ем|ником|щиком|чиком|истом))",
        r"он\s+(?:работает\s+)?([а-яё]+(?:ор|ер|ист|ник|чик))",
    ]

    # Паттерны для детей
    CHILDREN_PATTERNS = [
        r"(?:дочь|дочк[ауе]|дочери)\s+(?:зовут\s+)?([А-ЯЁ][а-яё]+)",
        r"([А-ЯЁ][а-яё]+)\s+—?\s?(?:моя\s+)?дочь",
        r"(?:сын(?:а|у)?|сыночек)\s+(?:зовут\s+)?([А-ЯЁ][а-яё]+)",
        r"([А-ЯЁ][а-яё]+)\s+—?\s?мой сын",
        r"у\s+(?:меня|нас)\s+([а-яё]+)\s+(?:дет[еиья]|ребёнок|ребенок)",  # "у нас двое детей"
    ]

    CHILD_AGE_PATTERNS = [
        r"(?:дочь|дочк[ауе]|сын[ау]?)\s+(\d{1,2})\s+(?:лет|год)",
        r"ей\s+(\d{1,2})\s+(?:лет|год)",  # Осторожно: нужен контекст
        r"ему\s+(\d{1,2})\s+(?:лет|год)",  # Осторожно: нужен контекст
    ]

    # Паттерны для отношений
    RELATIONSHIP_PATTERNS = [
        r"(?:познакомились|встретились)\s+(?:на|в|через)\s+([а-яё\s]+)",
        r"(?:женаты|вместе|в браке)\s+(?:уже\s+)?(\d+)\s+(?:лет|год)",
    ]

    # === Паттерны для музыкальных предпочтений ===
    MUSIC_GENRE_PATTERNS = [
        r"(?:люблю|нравится|обожаю|слушаю)\s+([а-яё]+(?:\s+музык[ау])?)",  # люблю джаз, слушаю рок
        r"(?:любимый\s+жанр|любимая\s+музыка)[:\s]+([а-яё\s,]+)",  # любимый жанр: джаз
        r"(?:под\s+настроение)\s+(?:слушаю\s+)?([а-яё]+)",  # под настроение слушаю классику
    ]

    MUSIC_ARTIST_PATTERNS = [
        r"(?:люблю|нравится|обожаю|слушаю)\s+([A-Za-zА-ЯЁа-яё\s&]+?)(?:\s*[-–—]\s*|,|\.|$)",  # люблю Queen
        r"(?:любим(?:ая|ый)\s+(?:группа|исполнитель|певец|певица))[:\s]+([A-Za-zА-ЯЁа-яё\s&]+)",
        r"(?:фанат(?:ка)?|поклонни(?:к|ца))\s+([A-Za-zА-ЯЁа-яё\s&]+)",  # фанат Queen
    ]

    MUSIC_SONG_PATTERNS = [
        r"(?:любимая\s+песня)[:\s]+[«\"]?([^»\"]+)[»\"]?",  # любимая песня: "Bohemian Rhapsody"
        r"(?:обожаю\s+песню|нравится\s+песня)\s+[«\"]?([^»\"]+)[»\"]?",
    ]

    # Известные жанры музыки
    KNOWN_MUSIC_GENRES = {
        "рок", "поп", "джаз", "классика", "классическ", "электронн", "хип-хоп", "рэп",
        "металл", "панк", "блюз", "кантри", "регги", "соул", "r&b", "диско",
        "инди", "альтернатив", "фолк", "шансон", "романс", "этно", "лаунж",
        "ambient", "эмбиент", "транс", "хаус", "техно", "дабстеп",
    }

    # === Паттерны для кинопредпочтений ===
    MOVIE_PATTERNS = [
        r"(?:люблю|нравится|обожаю)\s+(?:фильм\s+)?[«\"]([^»\"]+)[»\"]",  # люблю фильм "Интерстеллар"
        r"(?:любимый\s+фильм)[:\s]+[«\"]?([^»\",]+)[»\"]?",  # любимый фильм: Интерстеллар
        r"(?:смотрел[аи]?\s+)?[«\"]([^»\"]+)[»\"][\s—–-]+(?:классн|круто|супер|отличн|понравил)",  # "Интерстеллар" — классный
    ]

    SERIES_PATTERNS = [
        r"(?:люблю|нравится|обожаю)\s+(?:сериал\s+)?[«\"]([^»\"]+)[»\"]",
        r"(?:любимый\s+сериал)[:\s]+[«\"]?([^»\",]+)[»\"]?",
        r"(?:смотрю|пересматриваю)\s+[«\"]([^»\"]+)[»\"]",
    ]

    ACTOR_PATTERNS = [
        r"(?:люблю|нравится|обожаю)\s+([А-ЯЁA-Z][а-яёa-z]+\s+[А-ЯЁA-Z][а-яёa-z]+)(?:\s+как\s+актёр|\s+актёр)?",
        r"(?:любимый\s+актёр)[:\s]+([А-ЯЁA-Z][а-яёa-z]+(?:\s+[А-ЯЁA-Z][а-яёa-z]+)?)",
        r"([А-ЯЁA-Z][а-яёa-z]+\s+[А-ЯЁA-Z][а-яёa-z]+)\s+—?\s*(?:гениальн|лучший\s+актёр|классный\s+актёр)",
    ]

    ACTRESS_PATTERNS = [
        r"(?:люблю|нравится|обожаю)\s+([А-ЯЁA-Z][а-яёa-z]+\s+[А-ЯЁA-Z][а-яёa-z]+)(?:\s+как\s+актрис|\s+актрис)?",
        r"(?:любимая\s+актриса)[:\s]+([А-ЯЁA-Z][а-яёa-z]+(?:\s+[А-ЯЁA-Z][а-яёa-z]+)?)",
        r"([А-ЯЁA-Z][а-яёa-z]+\s+[А-ЯЁA-Z][а-яёa-z]+)\s+—?\s*(?:гениальн|лучшая\s+актриса|классная\s+актриса)",
    ]

    MOVIE_GENRE_PATTERNS = [
        r"(?:люблю|нравится|обожаю)\s+([а-яё]+(?:ы|и)?)\s*(?:фильм|кино)",  # люблю драмы, комедии
        r"(?:люблю\s+смотреть|предпочитаю)\s+([а-яё]+(?:ы|и)?)",  # люблю смотреть триллеры
    ]

    KNOWN_MOVIE_GENRES = {
        "драм", "комеди", "триллер", "ужас", "боевик", "фантастик", "фэнтези",
        "мелодрам", "детектив", "приключен", "мультфильм", "анимац", "докуменатльн",
        "биографи", "историческ", "военн", "криминал", "мюзикл", "вестерн",
    }

    # Известные города России и СНГ (топ)
    KNOWN_CITIES = {
        "москва", "москве", "санкт-петербург", "петербург", "питер", "питере",
        "новосибирск", "екатеринбург", "казань", "нижний новгород", "челябинск",
        "самара", "уфа", "ростов", "ростов-на-дону", "краснодар", "воронеж",
        "пермь", "красноярск", "волгоград", "саратов", "тюмень", "тольятти",
        "киев", "киеве", "харьков", "одесса", "днепр", "львов",
        "минск", "минске", "брест", "гомель",
        "алматы", "астана", "нур-султан", "бишкек", "ташкент",
    }

    # Нормализация городов
    CITY_NORMALIZATIONS = {
        "москве": "Москва",
        "питере": "Санкт-Петербург",
        "питер": "Санкт-Петербург",
        "петербург": "Санкт-Петербург",
        "киеве": "Киев",
        "минске": "Минск",
    }

    # Известные страны
    KNOWN_COUNTRIES = {
        "россия", "россию", "россией", "рф",
        "украина", "украину", "украине",
        "беларусь", "белоруссия", "белоруссию",
        "казахстан", "казахстане",
        "грузия", "армения", "азербайджан",
    }

    COUNTRY_NORMALIZATIONS = {
        "россию": "Россия",
        "россией": "Россия",
        "рф": "Россия",
        "украину": "Украина",
        "украине": "Украина",
        "белоруссию": "Беларусь",
        "белоруссия": "Беларусь",
        "казахстане": "Казахстан",
    }

    def extract(
        self,
        user_message: str,
        assistant_response: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Извлекает профильную информацию из сообщения.

        Args:
            user_message: Сообщение пользователя
            assistant_response: Ответ бота (для контекста)

        Returns:
            Словарь с извлечёнными данными или None
        """
        text = user_message.lower()
        extracted = {}

        # Извлекаем локацию
        location = self._extract_location(text, user_message)
        if location:
            extracted["location"] = location

        # Извлекаем профессию
        occupation = self._extract_occupation(text)
        if occupation:
            extracted["occupation"] = occupation

        # Извлекаем возраст
        age = self._extract_age(text)
        if age:
            extracted["age"] = age

        # Извлекаем информацию о партнёре
        partner = self._extract_partner(text, user_message)
        if partner:
            extracted["partner"] = partner

        # Извлекаем информацию о детях
        children = self._extract_children(text, user_message)
        if children:
            extracted["children"] = children
            extracted["children_confidence"] = 7  # Средняя уверенность

        # Извлекаем информацию об отношениях
        relationship = self._extract_relationship(text)
        if relationship:
            extracted["relationship"] = relationship

        # Извлекаем музыкальные предпочтения
        music = self._extract_music_preferences(text, user_message)
        if music:
            extracted["music_preferences"] = music

        # Извлекаем кинопредпочтения
        movies = self._extract_movie_preferences(text, user_message)
        if movies:
            extracted["movie_preferences"] = movies

        if not extracted:
            return None

        logger.debug(f"Extracted profile data: {extracted}")
        return extracted

    def _extract_location(self, text: str, original: str) -> Optional[Dict[str, Any]]:
        """Извлекает информацию о локации."""
        result = {}

        # Ищем город
        for pattern in self.CITY_PATTERNS:
            match = re.search(pattern, original, re.IGNORECASE)
            if match:
                city = match.group(1).strip()
                city_lower = city.lower()

                # Проверяем что это известный город
                if city_lower in self.KNOWN_CITIES:
                    # Нормализуем
                    city = self.CITY_NORMALIZATIONS.get(city_lower, city.capitalize())
                    result["city"] = city
                    result["confidence"] = 8
                    break

        # Ищем страну
        for pattern in self.COUNTRY_PATTERNS:
            match = re.search(pattern, original, re.IGNORECASE)
            if match:
                country = match.group(1).strip().lower()
                if country in self.KNOWN_COUNTRIES:
                    country = self.COUNTRY_NORMALIZATIONS.get(country, country.capitalize())
                    result["country"] = country
                    break

        # Если не нашли страну но нашли город — предполагаем Россию
        if result.get("city") and not result.get("country"):
            result["country"] = "Россия"

        return result if result else None

    def _extract_occupation(self, text: str) -> Optional[Dict[str, Any]]:
        """Извлекает профессию."""
        for pattern in self.OCCUPATION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                occupation = match.group(1).strip()
                # Фильтруем слишком короткие результаты
                if len(occupation) >= 3:
                    return {
                        "value": occupation,
                        "confidence": 7,
                    }
        return None

    def _extract_age(self, text: str) -> Optional[Dict[str, Any]]:
        """Извлекает возраст."""
        for pattern in self.AGE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                age = int(match.group(1))
                # Проверяем что возраст разумный
                if 18 <= age <= 80:
                    return {
                        "value": age,
                        "confidence": 9,
                    }
        return None

    def _extract_partner(self, text: str, original: str) -> Optional[Dict[str, Any]]:
        """Извлекает информацию о партнёре."""
        result = {}

        # Ищем имя партнёра
        for pattern in self.PARTNER_NAME_PATTERNS:
            match = re.search(pattern, original, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Проверяем что это похоже на имя (с большой буквы, разумной длины)
                if len(name) >= 2 and name[0].isupper():
                    result["name"] = name
                    break

        # Ищем возраст партнёра
        for pattern in self.PARTNER_AGE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                age = int(match.group(1))
                if 18 <= age <= 80:
                    result["age"] = age
                    break

        # Ищем профессию партнёра
        for pattern in self.PARTNER_OCCUPATION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                occupation = match.group(1).strip()
                if len(occupation) >= 3:
                    result["occupation"] = occupation
                    break

        if result:
            result["confidence"] = 7

        return result if result else None

    def _extract_children(self, text: str, original: str) -> Optional[List[Dict[str, Any]]]:
        """Извлекает информацию о детях."""
        children = []

        # Ищем дочерей
        daughter_patterns = [
            r"(?:дочь|дочк[ауе]|дочери)\s+(?:зовут\s+)?([А-ЯЁ][а-яё]+)",
            r"([А-ЯЁ][а-яё]+)\s+—?\s?(?:моя\s+)?дочь",
        ]
        for pattern in daughter_patterns:
            for match in re.finditer(pattern, original, re.IGNORECASE):
                name = match.group(1).strip()
                if len(name) >= 2 and name[0].isupper():
                    # Проверяем что это имя ещё не добавлено
                    if not any(c.get("name", "").lower() == name.lower() for c in children):
                        children.append({
                            "name": name,
                            "gender": "female",
                        })

        # Ищем сыновей
        son_patterns = [
            r"(?:сын(?:а|у)?|сыночек)\s+(?:зовут\s+)?([А-ЯЁ][а-яё]+)",
            r"([А-ЯЁ][а-яё]+)\s+—?\s?мой сын",
        ]
        for pattern in son_patterns:
            for match in re.finditer(pattern, original, re.IGNORECASE):
                name = match.group(1).strip()
                if len(name) >= 2 and name[0].isupper():
                    if not any(c.get("name", "").lower() == name.lower() for c in children):
                        children.append({
                            "name": name,
                            "gender": "male",
                        })

        # Пытаемся найти возраст для каждого ребёнка
        # Это сложная задача, пока упрощённо
        age_match = re.search(r"(\d{1,2})\s+(?:лет|год)", text)
        if age_match and children:
            age = int(age_match.group(1))
            if 0 <= age <= 25:
                # Присваиваем первому найденному ребёнку
                children[0]["age"] = age

        return children if children else None

    def _extract_relationship(self, text: str) -> Optional[Dict[str, Any]]:
        """Извлекает информацию об отношениях."""
        result = {}

        # Как познакомились
        how_met_patterns = [
            (r"познакомились\s+(?:на|в|через)\s+([а-яё\s]+?)(?:\.|,|$)", None),
            (r"встретились\s+(?:на|в)\s+([а-яё\s]+?)(?:\.|,|$)", None),
        ]
        for pattern, _ in how_met_patterns:
            match = re.search(pattern, text)
            if match:
                how_met = match.group(1).strip()
                if len(how_met) >= 3:
                    result["how_met"] = how_met
                    break

        # Сколько лет вместе
        years_match = re.search(r"(?:женаты|вместе|в браке)\s+(?:уже\s+)?(\d+)\s+(?:лет|год)", text)
        if years_match:
            result["years_together"] = int(years_match.group(1))

        if result:
            result["confidence"] = 6

        return result if result else None

    def _extract_music_preferences(self, text: str, original: str) -> Optional[Dict[str, Any]]:
        """Извлекает музыкальные предпочтения."""
        result = {
            "genres": [],
            "artists": [],
            "songs": [],
        }

        # Извлекаем жанры музыки
        for pattern in self.MUSIC_GENRE_PATTERNS:
            for match in re.finditer(pattern, text):
                genre = match.group(1).strip().lower()
                # Проверяем что это известный жанр
                for known_genre in self.KNOWN_MUSIC_GENRES:
                    if known_genre in genre and genre not in result["genres"]:
                        result["genres"].append(genre)
                        break

        # Извлекаем исполнителей
        for pattern in self.MUSIC_ARTIST_PATTERNS:
            for match in re.finditer(pattern, original, re.IGNORECASE):
                artist = match.group(1).strip()
                # Фильтруем слишком короткие и общие слова
                if len(artist) >= 2 and artist.lower() not in {"музыку", "песни", "треки"}:
                    if artist not in result["artists"]:
                        result["artists"].append(artist)

        # Извлекаем песни
        for pattern in self.MUSIC_SONG_PATTERNS:
            for match in re.finditer(pattern, original, re.IGNORECASE):
                song = match.group(1).strip()
                if len(song) >= 2 and song not in result["songs"]:
                    result["songs"].append(song)

        # Проверяем что что-то нашли
        has_data = result["genres"] or result["artists"] or result["songs"]
        if not has_data:
            return None

        result["confidence"] = 7
        return result

    def _extract_movie_preferences(self, text: str, original: str) -> Optional[Dict[str, Any]]:
        """Извлекает кинопредпочтения."""
        result = {
            "genres": [],
            "movies": [],
            "series": [],
            "actors": [],
            "actresses": [],
        }

        # Извлекаем жанры кино
        for pattern in self.MOVIE_GENRE_PATTERNS:
            for match in re.finditer(pattern, text):
                genre = match.group(1).strip().lower()
                # Проверяем что это известный жанр
                for known_genre in self.KNOWN_MOVIE_GENRES:
                    if known_genre in genre and genre not in result["genres"]:
                        result["genres"].append(genre)
                        break

        # Извлекаем фильмы
        for pattern in self.MOVIE_PATTERNS:
            for match in re.finditer(pattern, original, re.IGNORECASE):
                movie = match.group(1).strip()
                if len(movie) >= 2 and movie not in result["movies"]:
                    result["movies"].append(movie)

        # Извлекаем сериалы
        for pattern in self.SERIES_PATTERNS:
            for match in re.finditer(pattern, original, re.IGNORECASE):
                series = match.group(1).strip()
                if len(series) >= 2 and series not in result["series"]:
                    result["series"].append(series)

        # Извлекаем актёров
        for pattern in self.ACTOR_PATTERNS:
            for match in re.finditer(pattern, original, re.IGNORECASE):
                actor = match.group(1).strip()
                if len(actor) >= 4 and actor not in result["actors"]:
                    result["actors"].append(actor)

        # Извлекаем актрис
        for pattern in self.ACTRESS_PATTERNS:
            for match in re.finditer(pattern, original, re.IGNORECASE):
                actress = match.group(1).strip()
                if len(actress) >= 4 and actress not in result["actresses"]:
                    result["actresses"].append(actress)

        # Проверяем что что-то нашли
        has_data = (
            result["genres"] or result["movies"] or result["series"]
            or result["actors"] or result["actresses"]
        )
        if not has_data:
            return None

        result["confidence"] = 7
        return result


# Глобальный экземпляр
profile_extractor = ProfileExtractor()
